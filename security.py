from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import discord

import config
from database import log_db


# In-memory spam tracking. This resets when the bot restarts.
message_history = defaultdict(deque)
image_history = defaultdict(deque)


SCAM_KEYWORDS = (
    "bonus",
    "activate code",
    "withdrawal",
    "withdraw",
    "rakeback",
    "crypto",
    "usdt",
    "tether",
    "deposit",
    "casino",
    "reward",
    "promo code",
    "free gift",
    "airdrop",
    "claim",
    "giveaway",
)

SUSPICIOUS_LINK_TERMS = (
    "bit.ly",
    "tinyurl",
    "t.me",
    "telegram",
    "discord.gg",
    "free",
    "bonus",
    "claim",
    "giveaway",
)

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff")


def clean_content(message):
    """Keep logs readable and avoid giant embeds from long spam messages."""
    content = (message.content or "").strip()
    return content[:1000] if content else "[No text content]"


def attachment_summary(message):
    """Show useful attachment details without making embeds too large."""
    if not message.attachments:
        return "0"

    lines = []
    for index, attachment in enumerate(message.attachments[:5], start=1):
        filename = attachment.filename or "attachment"
        lines.append(f"{index}. [{filename}]({attachment.url})")

    if len(message.attachments) > 5:
        lines.append(f"...and {len(message.attachments) - 5} more")

    return "\n".join(lines)


def first_image_url(message):
    for attachment in message.attachments:
        content_type = (attachment.content_type or "").lower()
        filename = (attachment.filename or "").lower()

        if content_type.startswith("image/") or filename.endswith(IMAGE_EXTENSIONS):
            return attachment.url

    return None


def is_exempt_user(member):
    """Skip trusted users and users Discord already allows to moderate messages."""
    if not member or not getattr(member, "guild", None):
        return True

    if member.bot:
        return True

    if member.guild_permissions.administrator:
        return True

    if member.guild_permissions.manage_messages:
        return True

    return any(role.id == config.PRESIDENT_ROLE_ID for role in member.roles)


def has_image_attachment(message):
    """Detect image-like attachments without depending only on Discord content type."""
    for attachment in message.attachments:
        content_type = (attachment.content_type or "").lower()
        filename = (attachment.filename or "").lower()

        if content_type.startswith("image/") or filename.endswith(IMAGE_EXTENSIONS):
            return True

    return False


def prune_history(history, now, seconds):
    """Keep only messages inside the active spam window."""
    while history and now - history[0][0] > seconds:
        history.popleft()


def timeout_duration_text():
    """Format the configured mute duration for staff-facing messages."""
    seconds = config.SECURITY_TIMEOUT_SECONDS
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    minutes = seconds // 60
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


def build_user_dm_embed(message, reason):
    embed = discord.Embed(
        title="🛡️ Message Removed",
        description=(
            "Your message looked like scam/spam content, so Windy removed it "
            "and muted you while staff review what happened."
        ),
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="📍 Server", value=message.guild.name, inline=False)
    embed.add_field(name="🧾 Reason", value=reason, inline=False)
    embed.add_field(name="🔇 Mute Duration", value=timeout_duration_text(), inline=False)
    embed.add_field(name="✅ What to do", value="Please wait for staff review. Do not repost the same content.", inline=False)
    embed.set_footer(text="No kick was performed.")
    return embed


def build_staff_embed(message, reason, action_taken, timeout_status, deleted_count=1):
    embed = discord.Embed(
        title="🛡️ Security Alert",
        description=f"Suspicious activity was detected in **{message.guild.name}**.",
        color=discord.Color.from_rgb(255, 90, 90),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="👤 User", value=f"{message.author.mention}\n`{message.author}`", inline=True)
    embed.add_field(name="🆔 User ID", value=f"`{message.author.id}`", inline=True)
    embed.add_field(name="📍 Channel", value=message.channel.mention, inline=True)
    embed.add_field(name="🚨 Reason", value=reason, inline=False)
    embed.add_field(name="💬 Message Content", value=clean_content(message), inline=False)
    embed.add_field(name="🖼️ Attachments", value=attachment_summary(message), inline=False)
    embed.add_field(name="🧹 Messages Deleted", value=str(deleted_count), inline=True)
    embed.add_field(name="🔇 Timeout Duration", value=f"{timeout_duration_text()} ({timeout_status})", inline=True)
    embed.add_field(name="⚙️ Action Taken", value=action_taken, inline=False)
    if message.guild.icon:
        embed.set_author(name="Windy Security", icon_url=message.guild.icon.url)
    else:
        embed.set_author(name="Windy Security")
    embed.set_footer(text=f"Message ID: {message.id}")

    image_url = first_image_url(message)
    if image_url:
        embed.set_image(url=image_url)

    return embed


async def delete_message(message):
    try:
        await message.delete()
        return True
    except Exception:
        return False


async def delete_messages(messages):
    deleted_count = 0
    seen_message_ids = set()

    for message in messages:
        if message.id in seen_message_ids:
            continue

        seen_message_ids.add(message.id)
        if await delete_message(message):
            deleted_count += 1

    return deleted_count


async def dm_user(message, reason):
    try:
        await message.author.send(embed=build_user_dm_embed(message, reason))
        return True
    except Exception:
        return False


async def timeout_user(message):
    """Apply a Discord timeout. If this fails, the rest of security still logs."""
    until = datetime.now(timezone.utc) + timedelta(seconds=config.SECURITY_TIMEOUT_SECONDS)
    try:
        await message.author.timeout(until, reason="Security system: suspected scam/spam content")
        return True
    except Exception:
        return False


async def dm_owner_or_president(bot, message, reason, action_taken, timeout_status, deleted_count):
    owner_id = config.SECURITY_DM_OWNER_ID
    recipient = None

    try:
        if owner_id:
            recipient = bot.get_user(owner_id) or await bot.fetch_user(owner_id)

        if not recipient:
            president_role = message.guild.get_role(config.PRESIDENT_ROLE_ID)
            if president_role and president_role.members:
                recipient = president_role.members[0]

        if not recipient:
            return False

        view = discord.ui.View()
        try:
            from dashboard import create_dashboard_url
            view.add_item(
                discord.ui.Button(
                    label="Open Dashboard",
                    style=discord.ButtonStyle.link,
                    emoji="📊",
                    url=create_dashboard_url(message.guild.id, recipient.id),
                )
            )
        except Exception:
            pass

        await recipient.send(
            embed=build_staff_embed(message, reason, action_taken, timeout_status, deleted_count),
            view=view if view.children else None,
        )
        return True
    except Exception:
        return False


async def send_security_log(bot, message, reason, action_taken, timeout_status, deleted_count=1):
    channel = bot.get_channel(config.SECURITY_LOG_CHANNEL_ID)
    if not channel:
        try:
            channel = await bot.fetch_channel(config.SECURITY_LOG_CHANNEL_ID)
        except Exception:
            channel = None

    if not channel:
        return False

    embed = build_staff_embed(message, reason, action_taken, timeout_status, deleted_count)

    try:
        view = discord.ui.View()
        try:
            from dashboard import create_dashboard_url

            owner_id = config.SECURITY_DM_OWNER_ID
            if owner_id:
                view.add_item(
                    discord.ui.Button(
                        label="Open Dashboard",
                        style=discord.ButtonStyle.link,
                        emoji="📊",
                        url=create_dashboard_url(message.guild.id, owner_id),
                    )
                )
        except Exception:
            pass

        await channel.send(
            embed=embed,
            view=view if view.children else None,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return True
    except Exception:
        return False


async def handle_security_violation(bot, message, reason, messages_to_delete=None):
    """Delete, notify, timeout, DM staff, and log a suspected scam/spam message."""
    messages_to_delete = messages_to_delete or [message]
    deleted_count = await delete_messages(messages_to_delete)
    dm_sent = await dm_user(message, reason)
    timed_out = await timeout_user(message)

    timeout_status = "applied" if timed_out else "failed - check bot role permissions"
    action_taken = (
        f"🧹 Deleted **{deleted_count}** recent message(s).\n"
        f"📩 User DM: **{'sent' if dm_sent else 'failed'}**\n"
        f"🔇 Timeout: **{timeout_status}**\n"
        "🚫 Kick: **not performed**"
    )

    await dm_owner_or_president(bot, message, reason, action_taken, timeout_status, deleted_count)
    await send_security_log(bot, message, reason, action_taken, timeout_status, deleted_count)
    log_db(
        "Windy Security",
        "SECURITY_TIMEOUT",
        str(message.author),
        (
            f"Reason: {reason} | Channel: #{message.channel} | "
            f"Deleted: {deleted_count} | Timeout: {timeout_status} | "
            f"Content: {clean_content(message)}"
        ),
    )


async def handle_message_security(bot, message):
    """Return True when a message was handled by security and should not continue."""
    if not config.SECURITY_ENABLED:
        return False

    if not message.guild or is_exempt_user(message.author):
        return False

    content = (message.content or "").lower()
    now = message.created_at.timestamp()
    history_key = (message.guild.id, message.author.id)

    if any(keyword in content for keyword in SCAM_KEYWORDS):
        await handle_security_violation(bot, message, "Scam keyword detected")
        return True

    if any(term in content for term in SUSPICIOUS_LINK_TERMS):
        await handle_security_violation(bot, message, "Suspicious link or promo text detected")
        return True

    messages = message_history[history_key]
    messages.append((now, message))
    prune_history(messages, now, 10)

    if len(messages) >= 4:
        spam_messages = [stored_message for _, stored_message in messages]
        messages.clear()
        await handle_security_violation(bot, message, "Message spam detected", spam_messages)
        return True

    if has_image_attachment(message):
        images = image_history[history_key]
        images.append((now, message))
        prune_history(images, now, 20)

        if len(images) >= 3:
            spam_images = [stored_message for _, stored_message in images]
            images.clear()
            messages.clear()
            await handle_security_violation(bot, message, "Image spam detected", spam_images)
            return True

    return False
