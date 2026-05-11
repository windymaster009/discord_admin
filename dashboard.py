import time
import uuid
import asyncio
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone

from flask import Flask, request, render_template, redirect, url_for
from discord.ui import View, Button
from discord import ButtonStyle

from config import (
    DASHBOARD_HOST,
    DASHBOARD_PORT,
    DASHBOARD_OPEN_URL,
)
from approval import is_president, approval_channel
from database import get_guild_settings, log_db

app = Flask(__name__)

dashboard_sessions = {}
bot_ref = None


def setup_dashboard(bot):
    global bot_ref
    bot_ref = bot


def create_dashboard_session(guild_id, user_id):
    session_id = str(uuid.uuid4())
    dashboard_sessions[session_id] = {
        "guild_id": guild_id,
        "user_id": user_id,
        "expires": time.time() + 3600
    }
    return session_id


def create_dashboard_url(guild_id, user_id):
    session_id = create_dashboard_session(guild_id, user_id)
    return f"{DASHBOARD_OPEN_URL}/?session={session_id}"


def get_dashboard_session():
    session_id = request.form.get("session") or request.args.get("session")
    session = dashboard_sessions.get(session_id)

    if not session or time.time() > session["expires"]:
        return None, None, None, None

    guild = bot_ref.get_guild(session["guild_id"])
    actor = guild.get_member(session["user_id"]) if guild else None

    if not guild or not actor or not is_president(actor):
        return None, None, None, None

    return session_id, session, guild, actor


async def send_dashboard_button(ctx):
    settings = get_guild_settings(ctx.guild.id)

    if ctx.channel.id != settings["approval_channel_id"]:
        return

    if not is_president(ctx.author):
        return await ctx.reply("❌ Only the President can open the dashboard.")

    url = create_dashboard_url(ctx.guild.id, ctx.author.id)

    view = View()
    view.add_item(Button(label="Open Dashboard", style=ButtonStyle.link, url=url))

    await ctx.reply("📊 Dashboard ready:", view=view)


@app.route("/")
def dashboard_page():
    session_id, session, guild, actor = get_dashboard_session()

    if not guild:
        return "403 Forbidden: Invalid or expired dashboard session.", 403

    q = (request.args.get("q") or "").lower()
    now = datetime.now(timezone.utc)
    join_day_start = (now - timedelta(days=6)).date()
    join_counts = Counter()

    members = []
    sorted_members = sorted(
        guild.members,
        key=lambda x: x.display_name.lower()
    )

    for m in sorted_members:
        if q and q not in m.name.lower() and q not in str(m.id):
            continue

        members.append({
            "id": m.id,
            "name": str(m),
            "display": m.display_name,
            "avatar": m.avatar.key if m.avatar else "",
            "bot": m.bot,
            "roles": [r for r in m.roles if r.name != "@everyone"],
            "joined": m.joined_at.strftime("%Y-%m-%d %H:%M") if m.joined_at else "Unknown"
        })

    roles = [r for r in guild.roles if r.name != "@everyone"]
    total_members = len(guild.members)
    human_count = len([m for m in guild.members if not m.bot])
    bot_count = len([m for m in guild.members if m.bot])

    for member in guild.members:
        if member.joined_at and member.joined_at.date() >= join_day_start:
            join_counts[member.joined_at.date().isoformat()] += 1

    total_roles = len([r for r in guild.roles if r.name != "@everyone"])

    role_member_counts = []
    for role in guild.roles:
        if role.name != "@everyone":
            role_member_counts.append({
                "name": role.name,
                "count": len(role.members)
            })

    role_member_counts = sorted(
        role_member_counts,
        key=lambda x: x["count"],
        reverse=True
    )[:8]

    join_activity = []
    for offset in range(7):
        day = join_day_start + timedelta(days=offset)
        join_activity.append({
            "label": day.strftime("%b %d"),
            "count": join_counts[day.isoformat()]
        })

    chart_data = {
        "memberTypes": {
            "labels": ["Humans", "Bots"],
            "values": [human_count, bot_count],
        },
        "topRoles": {
            "labels": [r["name"] for r in role_member_counts],
            "values": [r["count"] for r in role_member_counts],
        },
        "joinActivity": {
            "labels": [d["label"] for d in join_activity],
            "values": [d["count"] for d in join_activity],
        },
    }


    return render_template(
        "index.html",
        members=members,
        roles=roles,
        actor=actor,
        session_id=session_id,
        total_members=total_members,
        human_count=human_count,
        bot_count=bot_count,
        total_roles=total_roles,
        chart_data=chart_data,
    )

@app.route("/kick", methods=["POST"])
def dashboard_kick():
    session_id, session, guild, actor = get_dashboard_session()
    if not guild:
        return "403 Forbidden", 403

    member_id = int(request.form.get("member_id"))

    async def do_kick():
        member = guild.get_member(member_id)
        if member:
            await member.kick(reason=f"Kicked from dashboard by {actor}")
            ch = approval_channel(bot_ref, guild.id)
            if ch:
                await ch.send(f"🚫 {actor.mention} kicked {member.mention} from dashboard.")
            log_db(str(actor), "DASHBOARD_KICK", str(member))

    asyncio.run_coroutine_threadsafe(do_kick(), bot_ref.loop)
    return redirect(url_for("dashboard_page", session=session_id))


@app.route("/role", methods=["POST"])
def dashboard_role():
    session_id, session, guild, actor = get_dashboard_session()
    if not guild:
        return "403 Forbidden", 403

    member_id = int(request.form.get("member_id"))
    role_id = int(request.form.get("role_id"))
    action = request.form.get("action")

    async def do_role():
        member = guild.get_member(member_id)
        role = guild.get_role(role_id)

        if member and role:
            if action == "add":
                await member.add_roles(role, reason=f"Dashboard by {actor}")
                action_text = "added"
            else:
                await member.remove_roles(role, reason=f"Dashboard by {actor}")
                action_text = "removed"

            ch = approval_channel(bot_ref, guild.id)
            if ch:
                await ch.send(f"✅ {actor.mention} {action_text} **{role.name}** for {member.mention}.")
            log_db(str(actor), f"DASHBOARD_ROLE_{action.upper()}", str(member), role.name)

    asyncio.run_coroutine_threadsafe(do_role(), bot_ref.loop)
    return redirect(url_for("dashboard_page", session=session_id))


def run_dashboard():
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False, use_reloader=False)


def start_dashboard():
    threading.Thread(target=run_dashboard, daemon=True).start()
