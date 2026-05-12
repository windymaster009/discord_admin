from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import discord

import config


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
USER_DM_MESSAGE = (
    "Your message was removed because it looked like scam/spam content. "
    "You have been muted for 2 hours while staff review this."
)


def clean_content(message):
    """Keep logs readable and avoid giant embeds from long spam messages."""
    content = (message.content or "").strip()
    return content[:1000] if content else "[No text content]"


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
    """Keep only timestamps inside the active spam window."""
    while history and now - history[0] > seconds:
        history.popleft()


def timeout_duration_text():
    """Format the configured mute duration for staff-facing messages."""
    seconds = config.SECURITY_TIMEOUT_SECONDS
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    minutes = seconds // 60
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


def build_staff_details(message, reason, timeout_status):
    return (
        f"Security alert in **{message.guild.name}**\n"
        f"User: {message.author.mention} / {message.author} / `{message.author.id}`\n"
        f"Channel: {message.channel.mention} (`{message.channel.id}`)\n"
        f"Reason: {reason}\n"
        f"Message Content: {clean_content(message)}\n"
        f"Attachments: {len(message.attachments)}\n"
        f"Timeout: {timeout_duration_text()} ({timeout_status})"
    )


async def delete_message(message):
    try:
        await message.delete()
        return True
    except Exception:
        return False


async def dm_user(message):
    try:
        await message.author.send(USER_DM_MESSAGE)
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


async def dm_owner_or_president(bot, message, reason, timeout_status):
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

        await recipient.send(build_staff_details(message, reason, timeout_status))
        return True
    except Exception:
        return False


async def send_security_log(bot, message, reason, action_taken, timeout_status):
    channel = bot.get_channel(config.SECURITY_LOG_CHANNEL_ID)
    if not channel:
        try:
            channel = await bot.fetch_channel(config.SECURITY_LOG_CHANNEL_ID)
        except Exception:
            channel = None

    if not channel:
        return False

    embed = discord.Embed(
        title="Security Alert",
        color=discord.Color.red(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="User", value=f"{message.author.mention} / {message.author}", inline=False)
    embed.add_field(name="User ID", value=str(message.author.id), inline=False)
    embed.add_field(name="Channel", value=message.channel.mention, inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Message Content", value=clean_content(message), inline=False)
    embed.add_field(name="Attachments", value=str(len(message.attachments)), inline=False)
    embed.add_field(name="Action Taken", value=action_taken, inline=False)
    embed.add_field(name="Timeout Duration", value=f"{timeout_duration_text()} ({timeout_status})", inline=False)
    embed.set_footer(text=f"Message ID: {message.id}")

    try:
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        return True
    except Exception:
        return False


async def handle_security_violation(bot, message, reason):
    """Delete, notify, timeout, DM staff, and log a suspected scam/spam message."""
    deleted = await delete_message(message)
    dm_sent = await dm_user(message)
    timed_out = await timeout_user(message)

    timeout_status = "applied" if timed_out else "failed - check bot role permissions"
    action_taken = (
        f"Message deleted: {'yes' if deleted else 'no'}; "
        f"user DM sent: {'yes' if dm_sent else 'no'}; "
        f"timeout: {timeout_status}; no kick performed."
    )

    await dm_owner_or_president(bot, message, reason, timeout_status)
    await send_security_log(bot, message, reason, action_taken, timeout_status)


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
    messages.append(now)
    prune_history(messages, now, 10)

    if len(messages) >= 4:
        messages.clear()
        await handle_security_violation(bot, message, "Message spam detected")
        return True

    if has_image_attachment(message):
        images = image_history[history_key]
        images.append(now)
        prune_history(images, now, 20)

        if len(images) >= 3:
            images.clear()
            await handle_security_violation(bot, message, "Image spam detected")
            return True

    return False
