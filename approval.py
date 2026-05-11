import discord
from discord.ui import View, Button
from discord import ButtonStyle

from database import get_guild_settings, log_db

human_votes = {}
bot_votes = {}
pending_messages = {}


def is_president(member: discord.Member):
    settings = get_guild_settings(member.guild.id)
    return any(role.id == settings["president_role_id"] for role in member.roles)


def approval_channel(bot, guild_id):
    settings = get_guild_settings(guild_id)
    return bot.get_channel(settings["approval_channel_id"])


async def safe_dm(member, message):
    try:
        await member.send(message)
    except Exception:
        pass


async def delete_pending_message(bot, member_id):
    pending = pending_messages.pop(member_id, None)
    if not pending:
        return

    guild_id, msg_id = pending

    ch = approval_channel(bot, guild_id)
    if not ch:
        return

    try:
        msg = await ch.fetch_message(msg_id)
        await msg.delete()
    except Exception:
        pass


async def approve_member(bot, member: discord.Member, approved_by: discord.Member):
    guild = member.guild
    settings = get_guild_settings(guild.id)

    if member.bot:
        role = guild.get_role(settings["bot_role_id"])
    else:
        role = guild.get_role(settings["comrade_role_id"])
        pending = guild.get_role(settings["pending_role_id"])

        if pending and pending in member.roles:
            await member.remove_roles(pending)

    if role:
        await member.add_roles(role)

    ch = approval_channel(bot, guild.id)
    if ch:
        await ch.send(f"✅ {member.mention} was approved by {approved_by.mention}.")

    await safe_dm(member, f"✅ You have been approved to join **{guild.name}**. Welcome!")
    log_db(str(approved_by), "APPROVED", str(member))
    await delete_pending_message(bot, member.id)


async def deny_member(bot, member: discord.Member, denied_by: discord.Member):
    ch = approval_channel(bot, member.guild.id)
    if ch:
        await ch.send(f"🚫 {member.mention} was denied by {denied_by.mention} and kicked.")

    await safe_dm(
        member,
        "❌ You have been kicked because the President or community did not approve your stay."
    )

    log_db(str(denied_by), "DENIED", str(member))

    try:
        await member.kick(reason="Denied by President/community")
    except Exception as e:
        print("Kick failed:", e)

    await delete_pending_message(bot, member.id)


class ApprovalView(View):
    def __init__(self, bot, member: discord.Member):
        super().__init__(timeout=None)
        self.bot = bot
        self.member = member
        self.count = 0

        self.approve_button = Button(
            label="Approve (0)",
            style=ButtonStyle.success,
            emoji="👍"
        )
        self.deny_button = Button(
            label="Deny",
            style=ButtonStyle.danger,
            emoji="❌"
        )

        self.approve_button.callback = self.approve
        self.deny_button.callback = self.deny

        self.add_item(self.approve_button)
        self.add_item(self.deny_button)

        if member.bot:
            bot_votes[member.id] = set()
        else:
            human_votes[member.id] = set()

    async def approve(self, interaction: discord.Interaction):
        voter = interaction.user

        if voter.bot:
            return await interaction.response.send_message("Bots cannot vote.", ephemeral=True)

        if is_president(voter):
            await interaction.response.send_message("👑 President approved instantly.", ephemeral=True)
            await approve_member(self.bot, self.member, voter)
            return

        if voter.id == self.member.id:
            return await interaction.response.send_message("You cannot vote for yourself.", ephemeral=True)

        if self.member.bot:
            votes = bot_votes.setdefault(self.member.id, set())
            required = get_guild_settings(self.member.guild.id)["bot_approve_required"]
        else:
            votes = human_votes.setdefault(self.member.id, set())
            required = get_guild_settings(self.member.guild.id)["human_approve_required"]

        if voter.id in votes:
            return await interaction.response.send_message("You already voted.", ephemeral=True)

        votes.add(voter.id)
        self.count = len(votes)
        self.approve_button.label = f"Approve ({self.count})"

        await interaction.response.edit_message(view=self)

        ch = approval_channel(self.bot, self.member.guild.id)
        if ch:
            await ch.send(
                f"👍 {voter.mention} voted for {self.member.mention}. "
                f"Votes: **{self.count}/{required}**"
            )

        log_db(str(voter), "VOTE", str(self.member), f"{self.count}/{required}")

        if self.count >= required:
            await approve_member(self.bot, self.member, voter)

    async def deny(self, interaction: discord.Interaction):
        voter = interaction.user

        if not is_president(voter):
            return await interaction.response.send_message(
                "❌ You don’t have the ability to decide on that.",
                ephemeral=True
            )

        await interaction.response.send_message("🚫 Denied.", ephemeral=True)
        await deny_member(self.bot, self.member, voter)


async def handle_member_join(bot, member: discord.Member):
    settings = get_guild_settings(member.guild.id)
    ch = approval_channel(bot, member.guild.id)
    if not ch:
        print("Approval channel not found.")
        return

    if not member.bot:
        pending = member.guild.get_role(settings["pending_role_id"])
        if pending:
            try:
                await member.add_roles(pending)
            except Exception as e:
                print("Failed to add pending role:", e)

    embed = discord.Embed(
        title="⚠️ New Recruit Incoming",
        description=(
            f"**User:** {member.mention}\n"
            f"**Username:** `{member}`\n"
            f"**ID:** `{member.id}`\n"
            f"**Type:** {'🤖 Bot' if member.bot else '👤 Human'}"
        ),
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    msg = await ch.send(embed=embed, view=ApprovalView(bot, member))
    pending_messages[member.id] = (member.guild.id, msg.id)

    log_db("SYSTEM", "JOIN", str(member), "bot" if member.bot else "human")
