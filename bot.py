import discord
from discord import app_commands
from discord.ext import commands

from config import BOT_APPROVE_REQUIRED, HUMAN_APPROVE_REQUIRED, REQUEST_INVITE_CHANNEL_ID, TOKEN
from database import get_guild_settings, init_db, log_db, save_guild_settings
from approval import (
    handle_member_join,
    is_president,
)
from dashboard import (
    create_dashboard_url,
    send_dashboard_button,
    setup_dashboard,
    start_dashboard,
)
from security import handle_message_security

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents, help_command=None)
slash_commands_synced = False
pending_invite_requests = set()


def command_prefix_for(ctx):
    return ctx.clean_prefix or "."


def bot_avatar_url(ctx):
    member = ctx.me or bot.user
    return member.display_avatar.url if member else None


def vote_settings_for_guild(guild):
    settings = get_guild_settings(guild.id) if guild else {}
    return (
        settings.get("human_approve_required", HUMAN_APPROVE_REQUIRED),
        settings.get("bot_approve_required", BOT_APPROVE_REQUIRED),
    )


def mention_or_id(discord_object, object_id):
    return discord_object.mention if discord_object else f"`{object_id}`"


def can_manage_invites(member):
    return (
        member.guild_permissions.administrator
        or member.guild_permissions.manage_guild
        or member.guild_permissions.create_instant_invite
        or is_president(member)
    )


def build_setup_embed(guild, prefix="."):
    settings = get_guild_settings(guild.id)
    status = "Configured" if settings["is_configured"] else "Using config.py fallback"
    approval_channel = guild.get_channel(settings["approval_channel_id"])
    pending_role = guild.get_role(settings["pending_role_id"])
    comrade_role = guild.get_role(settings["comrade_role_id"])
    bot_role = guild.get_role(settings["bot_role_id"])
    president_role = guild.get_role(settings["president_role_id"])

    embed = discord.Embed(
        title="🛠️ Server Setup",
        description=(
            f"Status: **{status}**\n"
            "Use `/setup` to save settings for this server."
        ),
        color=discord.Color.from_rgb(87, 242, 135)
    )
    embed.add_field(
        name="📍 Approval Channel",
        value=mention_or_id(approval_channel, settings["approval_channel_id"]),
        inline=False
    )
    embed.add_field(
        name="🎭 Roles",
        value=(
            f"Pending: {mention_or_id(pending_role, settings['pending_role_id'])}\n"
            f"Comrade: {mention_or_id(comrade_role, settings['comrade_role_id'])}\n"
            f"Bot: {mention_or_id(bot_role, settings['bot_role_id'])}\n"
            f"President: {mention_or_id(president_role, settings['president_role_id'])}"
        ),
        inline=False
    )
    embed.add_field(
        name="✅ Vote Requirements",
        value=(
            f"Humans: **{settings['human_approve_required']}**\n"
            f"Bots: **{settings['bot_approve_required']}**"
        ),
        inline=False
    )
    embed.add_field(
        name="🚀 Setup Command",
        value=(
            "`/setup approval_channel:#channel pending_role:@role "
            "comrade_role:@role bot_role:@role president_role:@role`"
        ),
        inline=False
    )
    embed.add_field(
        name="🔗 Invite Request Channel",
        value=f"<#{REQUEST_INVITE_CHANNEL_ID}>",
        inline=False
    )
    embed.set_footer(text=f"Text helper: {prefix}setup")
    return embed


def build_main_help_embed(ctx, prefix):
    human_votes, bot_votes = vote_settings_for_guild(ctx.guild)
    embed = discord.Embed(
        title="🌙✨ Windy Control Center",
        description=(
            "**Server security, but make it clean.**\n"
            "Approval votes, President tools, member review, role control, and dashboard stats."
        ),
        color=discord.Color.from_rgb(255, 78, 205)
    )
    embed.add_field(
        name="📊 Dashboard Energy",
        value=(
            f"🟣 `{prefix}dashboard`\n"
            "Open the private web panel for members, roles, kicks, charts, and join activity."
        ),
        inline=False
    )
    embed.add_field(
        name="✅ Approval Flow",
        value=(
            "🟢 New joins get an approval card with buttons.\n"
            f"👤 Humans need **{human_votes}** votes\n"
            f"🤖 Bots need **{bot_votes}** votes\n"
            "👑 President can approve or deny instantly."
        ),
        inline=False
    )
    embed.add_field(
        name="🧭 Command Menu",
        value=(
            f"💫 `{prefix}help` - Main help panel\n"
            f"🛠️ `{prefix}setup` - Show server setup\n"
            f"📊 `{prefix}help dashboard` - Dashboard details\n"
            f"✅ `{prefix}help approval` - Approval system details"
        ),
        inline=False
    )
    embed.add_field(
        name="🔥 Quick Buttons",
        value="Use the buttons below for dashboard info, approval info, or command list.",
        inline=False
    )
    embed.set_thumbnail(url=bot_avatar_url(ctx))
    embed.set_footer(
        text=f"Prefix: {prefix} | Requested by {ctx.author}",
        icon_url=ctx.author.display_avatar.url
    )
    return embed


def build_dashboard_help_embed(ctx, prefix):
    embed = discord.Embed(
        title="📊💚 Dashboard Command",
        description=(
            "**Your private command center.**\n"
            "Flask dashboard session for server moderation and role management."
        ),
        color=discord.Color.from_rgb(87, 242, 135)
    )
    embed.add_field(name="🚀 Use It", value=f"`{prefix}dashboard`", inline=False)
    embed.add_field(
        name="🔐 Access Check",
        value=(
            "👑 President role required\n"
            "📍 Must be used in the approval channel\n"
            "⏳ Session expires after 1 hour"
        ),
        inline=False
    )
    embed.add_field(
        name="🛠️ What You Can Do",
        value=(
            "👥 Search members\n"
            "🎭 Add or remove roles\n"
            "🚫 Kick from dashboard\n"
            "📈 View member type, top roles, and 7-day join charts"
        ),
        inline=False
    )
    embed.add_field(
        name="🧠 How It Works",
        value=(
            "Windy creates a temporary link, stores your guild and user session in memory, "
            "then Flask verifies you are still President before showing the dashboard."
        ),
        inline=False
    )
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
    return embed


def build_approval_help_embed(ctx):
    human_votes, bot_votes = vote_settings_for_guild(ctx.guild)
    embed = discord.Embed(
        title="✅⚡ Approval Flow",
        description=(
            "**New member enters. Windy starts the review.**\n"
            "Here is the actual flow from the current codebase."
        ),
        color=discord.Color.from_rgb(250, 166, 26)
    )
    embed.add_field(
        name="1️⃣ New Join",
        value="`on_member_join` calls `handle_member_join`. Humans get the Pending role.",
        inline=False
    )
    embed.add_field(
        name="2️⃣ Approval Card",
        value="Windy posts a recruit embed in the approval channel with Approve and Deny buttons.",
        inline=False
    )
    embed.add_field(
        name="3️⃣ Vote Count",
        value=(
            f"👤 Humans need **{human_votes}** votes\n"
            f"🤖 Bots need **{bot_votes}** votes\n"
            "🚫 Users cannot vote for themselves"
        ),
        inline=False
    )
    embed.add_field(
        name="4️⃣ President Power",
        value="👑 President can approve instantly, or deny and kick instantly.",
        inline=False
    )
    embed.add_field(
        name="5️⃣ Final Result",
        value="Approved humans lose Pending and gain Comrade. Approved bots gain Bot role. Logs are saved.",
        inline=False
    )
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
    return embed


class HelpView(discord.ui.View):
    def __init__(self, prefix):
        super().__init__(timeout=180)
        self.prefix = prefix

    def main_embed(self, interaction):
        human_votes, bot_votes = vote_settings_for_guild(interaction.guild)
        embed = discord.Embed(
            title="🌙✨ Windy Control Center",
            description=(
                "**Server security, but make it clean.**\n"
                "Approval votes, President tools, member review, role control, and dashboard stats."
            ),
            color=discord.Color.from_rgb(255, 78, 205)
        )
        embed.add_field(
            name="📊 Dashboard Energy",
            value=(
                f"🟣 `{self.prefix}dashboard`\n"
                "Open the private web panel for members, roles, kicks, charts, and join activity."
            ),
            inline=False
        )
        embed.add_field(
            name="✅ Approval Flow",
            value=(
                "🟢 New joins get an approval card with buttons.\n"
                f"👤 Humans need **{human_votes}** votes\n"
                f"🤖 Bots need **{bot_votes}** votes\n"
                "👑 President can approve or deny instantly."
            ),
            inline=False
        )
        embed.add_field(
            name="🧭 Command Menu",
            value=(
                f"💫 `{self.prefix}help` - Main help panel\n"
                f"🛠️ `{self.prefix}setup` - Show server setup\n"
                f"📊 `{self.prefix}help dashboard` - Dashboard details\n"
                f"✅ `{self.prefix}help approval` - Approval system details"
            ),
            inline=False
        )
        embed.add_field(
            name="🔥 Quick Buttons",
            value="Use the buttons below like tabs. No message spam, just one clean help panel.",
            inline=False
        )
        if interaction.client.user:
            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
        embed.set_footer(
            text=f"Prefix: {self.prefix} | Requested by {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )
        return embed

    def dashboard_embed(self, interaction):
        embed = discord.Embed(
            title="📊💚 Dashboard Command",
            description=(
                "**Your private command center.**\n"
                "Open the Flask dashboard for moderation, roles, charts, and member actions."
            ),
            color=discord.Color.from_rgb(87, 242, 135)
        )
        embed.add_field(name="🚀 Use It", value=f"`{self.prefix}dashboard`", inline=False)
        embed.add_field(
            name="🔐 Access Check",
            value="👑 President role required\n📍 Approval channel only\n🧠 Flask verifies your session",
            inline=False
        )
        embed.add_field(
            name="🛠️ What You Can Do",
            value="👥 Search members\n🎭 Add or remove roles\n🚫 Kick users\n📈 View dashboard charts",
            inline=False
        )
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        return embed

    def approval_embed(self, interaction):
        human_votes, bot_votes = vote_settings_for_guild(interaction.guild)
        embed = discord.Embed(
            title="✅⚡ Approval Flow",
            description=(
                "**How Windy decides who gets in.**\n"
                "New members trigger an approval card. Votes are counted per member."
            ),
            color=discord.Color.from_rgb(250, 166, 26)
        )
        embed.add_field(
            name="🧮 Vote Requirements",
            value=f"👤 Humans: **{human_votes}** votes\n🤖 Bots: **{bot_votes}** votes",
            inline=False
        )
        embed.add_field(
            name="👑 President Override",
            value="President can approve instantly or deny and kick instantly.",
            inline=False
        )
        embed.add_field(
            name="🎯 Result",
            value="Approved humans gain Comrade. Approved bots gain Bot role. Denied users are kicked. Logs are saved.",
            inline=False
        )
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        return embed

    def commands_embed(self, interaction):
        embed = discord.Embed(
            title="📘✨ Command Cheat Sheet",
            description="Fast menu for the commands you actually need.",
            color=discord.Color.from_rgb(255, 78, 205)
        )
        embed.add_field(
            name="💫 Help",
            value=f"`{self.prefix}help` - Main panel\n`{self.prefix}help approval` - Approval details",
            inline=False
        )
        embed.add_field(
            name="📊 Dashboard",
            value=f"`{self.prefix}dashboard` - Create a dashboard session\n`{self.prefix}help dashboard` - Access rules",
            inline=False
        )
        embed.add_field(
            name="🛠️ Setup",
            value=f"`/setup` - Save server settings\n`{self.prefix}setup` - View current settings",
            inline=False
        )
        embed.add_field(
            name="🔗 Invite Requests",
            value=f"`/request_invite` - Ask owner/admin for a one-use invite\nChannel: <#{REQUEST_INVITE_CHANNEL_ID}>",
            inline=False
        )
        embed.add_field(
            name="✨ Tip",
            value="Use the buttons below like tabs. The same message updates in place.",
            inline=False
        )
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        return embed

    @discord.ui.button(label="Home", style=discord.ButtonStyle.secondary, emoji="🌙")
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.main_embed(interaction), view=self)

    @discord.ui.button(label="Dashboard", style=discord.ButtonStyle.primary, emoji="📊")
    async def open_dashboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.dashboard_embed(interaction), view=self)

    @discord.ui.button(label="Approval Flow", style=discord.ButtonStyle.success, emoji="✅")
    async def approval_flow(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.approval_embed(interaction), view=self)

    @discord.ui.button(label="Commands", style=discord.ButtonStyle.secondary, emoji="📘")
    async def commands_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.commands_embed(interaction), view=self)


class DashboardLaunchView(discord.ui.View):
    def __init__(self, url):
        super().__init__(timeout=300)
        self.add_item(
            discord.ui.Button(
                label="Launch Dashboard",
                style=discord.ButtonStyle.link,
                emoji="🚀",
                url=url
            )
        )


def build_dashboard_ready_embed(user):
    embed = discord.Embed(
        title="📊 Dashboard Link Ready",
        description=(
            "**Access granted.** Your private dashboard session is live.\n"
            "Use it for member search, role updates, kicks, and server charts."
        ),
        color=discord.Color.from_rgb(87, 242, 135)
    )
    embed.add_field(name="⏳ Expires", value="1 hour", inline=True)
    embed.add_field(name="🔐 Visibility", value="Only you can see this", inline=True)
    embed.set_footer(text=f"Requested by {user}", icon_url=user.display_avatar.url)
    return embed


def build_invite_request_embed(requester, note=""):
    embed = discord.Embed(
        title="🔗 Invite Link Request",
        description=(
            f"{requester.mention} is requesting a **one-use invite link**.\n"
            "Owner/Admin/President, please review and approve or deny below."
        ),
        color=discord.Color.from_rgb(88, 101, 242)
    )
    embed.add_field(name="👤 Requester", value=f"{requester} (`{requester.id}`)", inline=False)
    if note:
        embed.add_field(name="📝 Note", value=note[:900], inline=False)
    embed.add_field(
        name="✅ After Approval",
        value=(
            "Windy creates an invite limited to **1 use** and sends it to the requester.\n"
            "When the invited person joins, they still go through the normal server approval vote."
        ),
        inline=False
    )
    embed.set_footer(text="Invite approval does not skip member approval.")
    return embed


def build_invite_decision_embed(requester, approved_by, approved, note=""):
    color = discord.Color.green() if approved else discord.Color.red()
    title = "✅ Invite Request Approved" if approved else "🚫 Invite Request Denied"
    description = (
        f"{requester.mention}'s one-use invite was approved by {approved_by.mention}."
        if approved else
        f"{requester.mention}'s invite request was denied by {approved_by.mention}."
    )
    embed = discord.Embed(title=title, description=description, color=color)
    if note:
        embed.add_field(name="📝 Original Note", value=note[:900], inline=False)
    if approved:
        embed.add_field(
            name="🛂 Next Step",
            value="The invited user must still be approved by server members after joining.",
            inline=False
        )
    embed.set_footer(text="Invite request closed.")
    return embed


class InviteRequestView(discord.ui.View):
    def __init__(self, requester_id, note=""):
        super().__init__(timeout=86400)
        self.requester_id = requester_id
        self.note = note
        self.closed = False

    async def interaction_check(self, interaction):
        if can_manage_invites(interaction.user):
            return True

        await interaction.response.send_message(
            "🔒 Only the owner, admin, President, or invite managers can decide invite requests.",
            ephemeral=True
        )
        return False

    async def close_request(self, interaction, approved):
        if self.closed:
            return await interaction.response.send_message("This invite request is already closed.", ephemeral=True)

        requester = interaction.guild.get_member(self.requester_id)
        if not requester:
            return await interaction.response.send_message("Requester is no longer in this server.", ephemeral=True)

        self.closed = True
        pending_invite_requests.discard((interaction.guild.id, self.requester_id))

        for item in self.children:
            item.disabled = True

        if not approved:
            log_db(str(interaction.user), "INVITE_REQUEST_DENIED", str(requester), self.note)
            await interaction.response.edit_message(
                embed=build_invite_decision_embed(requester, interaction.user, False, self.note),
                view=self
            )
            return

        try:
            invite = await interaction.channel.create_invite(
                max_age=86400,
                max_uses=1,
                unique=True,
                reason=f"Invite request approved by {interaction.user}"
            )
        except discord.Forbidden:
            self.closed = False
            pending_invite_requests.add((interaction.guild.id, self.requester_id))
            for item in self.children:
                item.disabled = False
            return await interaction.response.send_message(
                "❌ I need `Create Invite` permission in this channel.",
                ephemeral=True
            )

        dm_sent = True
        try:
            await requester.send(
                "✅ Your invite request was approved.\n"
                f"Here is a one-use invite link: {invite.url}\n\n"
                "After your guest joins, server members still need to approve them before they get normal access."
            )
        except discord.Forbidden:
            dm_sent = False

        log_db(str(interaction.user), "INVITE_REQUEST_APPROVED", str(requester), invite.url)
        await interaction.response.edit_message(
            embed=build_invite_decision_embed(requester, interaction.user, True, self.note),
            view=self
        )

        if dm_sent:
            await interaction.followup.send(
                f"📨 Invite approved for {requester.mention}. I sent the one-use link by DM. "
                "When their guest joins, please approve them through the normal vote.",
                allowed_mentions=discord.AllowedMentions(users=True)
            )
        else:
            await interaction.followup.send(
                f"⚠️ Invite approved for {requester.mention}, but I could not DM them. "
                f"One-use invite: {invite.url}\n"
                "When their guest joins, please approve them through the normal vote.",
                allowed_mentions=discord.AllowedMentions(users=True)
            )

    @discord.ui.button(label="Approve Invite", style=discord.ButtonStyle.success, emoji="✅")
    async def approve_invite(self, interaction, button):
        await self.close_request(interaction, True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, emoji="🚫")
    async def deny_invite(self, interaction, button):
        await self.close_request(interaction, False)


async def create_invite_request(channel, requester, note=""):
    key = (channel.guild.id, requester.id)
    if key in pending_invite_requests:
        return await channel.send(
            f"{requester.mention}, you already have a pending invite request.",
            allowed_mentions=discord.AllowedMentions(users=True)
        )

    pending_invite_requests.add(key)
    log_db("SYSTEM", "INVITE_REQUEST_CREATED", str(requester), note)
    await channel.send(
        embed=build_invite_request_embed(requester, note),
        view=InviteRequestView(requester.id, note)
    )
    await channel.send(
        f"{requester.mention}, your invite request is waiting for owner/admin approval.",
        allowed_mentions=discord.AllowedMentions(users=True)
    )


@bot.event
async def on_ready():
    global slash_commands_synced

    if not slash_commands_synced:
        global_commands = await bot.tree.sync()

        for guild in bot.guilds:
            guild_object = discord.Object(id=guild.id)
            bot.tree.copy_global_to(guild=guild_object)
            guild_commands = await bot.tree.sync(guild=guild_object)
            print(f"Synced {len(guild_commands)} slash commands to {guild.name}")

        print(f"Synced {len(global_commands)} global slash commands")
        slash_commands_synced = True

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.CustomActivity(name="Moderating approvals • /help")
    )
    print(f"Bot online as {bot.user}")


@bot.event
async def on_member_join(member: discord.Member):
    await handle_member_join(bot, member)


@bot.event
async def on_member_remove(member: discord.Member):
    log_db("SYSTEM", "MEMBER_LEAVE", str(member), f"Guild: {member.guild.name}")


@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    log_db("SYSTEM", "MEMBER_BAN", str(user), f"Guild: {guild.name}")


@bot.event
async def on_member_unban(guild: discord.Guild, user: discord.User):
    log_db("SYSTEM", "MEMBER_UNBAN", str(user), f"Guild: {guild.name}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if await handle_message_security(bot, message):
        return

    if message.guild and message.channel.id == REQUEST_INVITE_CHANNEL_ID:
        prefix = command_prefix_for(await bot.get_context(message))
        if not message.content.startswith(prefix):
            await create_invite_request(message.channel, message.author, message.content.strip())
            return

    await bot.process_commands(message)


@bot.command()
async def dashboard(ctx):
    await send_dashboard_button(ctx)


@bot.command(name="help", aliases=["commands"])
async def help_command(ctx, command_name: str = None):
    prefix = command_prefix_for(ctx)
    topic = command_name.lower() if command_name else None

    if topic == "dashboard":
        return await ctx.reply(
            embed=build_dashboard_help_embed(ctx, prefix),
            view=HelpView(prefix),
            mention_author=False
        )

    if topic in {"approval", "approve", "system"}:
        return await ctx.reply(
            embed=build_approval_help_embed(ctx),
            view=HelpView(prefix),
            mention_author=False
        )

    await ctx.reply(
        embed=build_main_help_embed(ctx, prefix),
        view=HelpView(prefix),
        mention_author=False
    )


@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup_command(ctx):
    await ctx.reply(embed=build_setup_embed(ctx.guild, command_prefix_for(ctx)), mention_author=False)


@bot.command(name="request_invite", aliases=["invite"])
async def request_invite_command(ctx, *, note=""):
    if ctx.channel.id != REQUEST_INVITE_CHANNEL_ID:
        return await ctx.reply(
            f"🔗 Please request invite links in <#{REQUEST_INVITE_CHANNEL_ID}>.",
            mention_author=False
        )

    await create_invite_request(ctx.channel, ctx.author, note)


@bot.tree.command(name="help", description="Open Windy's interactive help panel.")
@app_commands.describe(topic="Optional topic: dashboard, approval, or commands")
async def slash_help(interaction: discord.Interaction, topic: str = None):
    prefix = "."
    view = HelpView(prefix)
    normalized_topic = topic.lower() if topic else None

    if normalized_topic == "dashboard":
        embed = view.dashboard_embed(interaction)
    elif normalized_topic in {"approval", "approve", "system"}:
        embed = view.approval_embed(interaction)
    elif normalized_topic in {"commands", "command"}:
        embed = view.commands_embed(interaction)
    else:
        embed = view.main_embed(interaction)

    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="setup", description="Configure Windy for this server.")
@app_commands.describe(
    approval_channel="Channel where approval cards and dashboard logs are posted.",
    pending_role="Role given to humans while waiting for approval.",
    comrade_role="Role given to approved human members.",
    bot_role="Role given to approved bots.",
    president_role="Role allowed to bypass votes, deny users, and open dashboard.",
    human_votes="Votes required to approve a human.",
    bot_votes="Votes required to approve a bot.",
)
@app_commands.checks.has_permissions(administrator=True)
async def slash_setup(
    interaction: discord.Interaction,
    approval_channel: discord.TextChannel,
    pending_role: discord.Role,
    comrade_role: discord.Role,
    bot_role: discord.Role,
    president_role: discord.Role,
    human_votes: app_commands.Range[int, 1, 20] = HUMAN_APPROVE_REQUIRED,
    bot_votes: app_commands.Range[int, 1, 20] = BOT_APPROVE_REQUIRED,
):
    if not interaction.guild:
        return await interaction.response.send_message(
            "❌ Setup can only be used inside a server.",
            ephemeral=True
        )

    save_guild_settings(
        guild_id=interaction.guild.id,
        approval_channel_id=approval_channel.id,
        pending_role_id=pending_role.id,
        comrade_role_id=comrade_role.id,
        bot_role_id=bot_role.id,
        president_role_id=president_role.id,
        human_approve_required=human_votes,
        bot_approve_required=bot_votes,
    )

    embed = build_setup_embed(interaction.guild)
    embed.title = "✅ Setup Saved"
    embed.description = "Windy is now configured for this server."
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="dashboard", description="Create a private President dashboard session.")
async def slash_dashboard(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message(
            "❌ The dashboard can only be opened inside a server.",
            ephemeral=True
        )

    settings = get_guild_settings(interaction.guild.id)

    if interaction.channel_id != settings["approval_channel_id"]:
        return await interaction.response.send_message(
            "📍 Please open the dashboard from the approval channel.",
            ephemeral=True
        )

    if not is_president(interaction.user):
        return await interaction.response.send_message(
            "🔒 Only the President role can open the dashboard.",
            ephemeral=True
        )

    url = create_dashboard_url(interaction.guild.id, interaction.user.id)
    await interaction.response.send_message(
        embed=build_dashboard_ready_embed(interaction.user),
        view=DashboardLaunchView(url),
        ephemeral=True
    )


@bot.tree.command(name="approval", description="Explain how Windy's approval system works.")
async def slash_approval(interaction: discord.Interaction):
    view = HelpView(".")
    await interaction.response.send_message(
        embed=view.approval_embed(interaction),
        view=view
    )


@bot.tree.command(name="commands", description="Show Windy's command cheat sheet.")
async def slash_commands(interaction: discord.Interaction):
    view = HelpView(".")
    await interaction.response.send_message(
        embed=view.commands_embed(interaction),
        view=view
    )


@bot.tree.command(name="request_invite", description="Request a one-use invite link for admin approval.")
@app_commands.describe(note="Optional note for the owner/admin reviewing this invite request.")
async def slash_request_invite(interaction: discord.Interaction, note: str = ""):
    if not interaction.guild:
        return await interaction.response.send_message(
            "❌ Invite requests can only be used inside a server.",
            ephemeral=True
        )

    if interaction.channel_id != REQUEST_INVITE_CHANNEL_ID:
        return await interaction.response.send_message(
            f"🔗 Please request invite links in <#{REQUEST_INVITE_CHANNEL_ID}>.",
            ephemeral=True
        )

    await interaction.response.send_message(
        "🔗 Invite request submitted for owner/admin approval.",
        ephemeral=True
    )
    await create_invite_request(interaction.channel, interaction.user, note)


@setup_command.error
async def setup_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        return await ctx.reply("🔒 Only server administrators can use `.setup`.", mention_author=False)
    raise error


@slash_setup.error
async def slash_setup_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        return await interaction.response.send_message(
            "🔒 Only server administrators can use `/setup`.",
            ephemeral=True
        )
    raise error


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set. Add it to your .env file.")

    init_db()
    setup_dashboard(bot)
    start_dashboard()
    bot.run(TOKEN)
