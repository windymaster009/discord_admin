# Windy Discord Admin Bot 🌙

Windy is a Discord.py admin bot for server approval, invite requests, dashboard tools, and scam/spam protection.

## ✨ Features

- ✅ Member approval system with voting
- 👑 President role instant approve/deny powers
- 🤖 Separate approval rules for bots and humans
- 🔗 Invite request approval flow
- 📊 Private Flask dashboard for moderation tools
- 🛡️ Scam/spam security system
- 📝 Security and approval logs
- 💾 MongoDB storage for server setup and history

## 📁 Project Files

- `bot.py` - main Discord bot, commands, slash commands, events
- `config.py` - loads `.env` values and fallback defaults
- `database.py` - MongoDB connection, logs, saved server settings
- `approval.py` - member join approval and voting system
- `dashboard.py` - Flask dashboard
- `security.py` - scam/spam detection, delete, DM, timeout, logs
- `.env` - your real private config
- `.env.example` - safe template showing available config options

## ⚠️ Important Security Note

Never share your real `.env` file or screenshots of it. It contains private secrets like:

- Discord bot token
- MongoDB username/password
- Private channel/user IDs

If your token or database password is exposed, rotate them immediately.

## 🧠 How Config Works

The bot uses config in this order:

1. `.env` is loaded first.
2. `config.py` uses `.env` values when they exist.
3. If a value is missing from `.env`, `config.py` uses its default.
4. Approval role/channel settings saved by `/setup` in MongoDB override fallback IDs.

So your `.env` does **not** need to look exactly like `.env.example`.

Example:

```env
REQUEST_INVITE_CHANNEL_ID=1393801371542622308
```

If this exists in `.env`, the bot uses it. If it is missing, the bot uses the default inside `config.py`.

## 🛠️ Setup

1. Install Python 3.10+.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the example config:

```bash
copy .env.example .env
```

4. Edit `.env` and add your real values:

```env
DISCORD_TOKEN=your_real_bot_token
MONGO_URI=your_mongodb_connection_string
MONGO_DB_NAME=Discord_bot
REQUEST_INVITE_CHANNEL_ID=your_invite_request_channel_id
DASHBOARD_OPEN_URL=https://your-dashboard-url
```

5. Start the bot:

```bash
python bot.py
```

## ⚙️ Recommended `.env`

Your real `.env` can stay short. These are the most important values:

```env
DISCORD_TOKEN=your_real_bot_token
MONGO_URI=your_mongodb_connection_string
MONGO_DB_NAME=Discord_bot

APPROVAL_CHANNEL_ID=1441224922486542387
REQUEST_INVITE_CHANNEL_ID=1393801371542622308
DASHBOARD_OPEN_URL=127.0.0.0:8888

BOT_APPROVE_REQUIRED=3
RULES_CHANNEL_ID=1337444919773761629

SECURITY_ENABLED=true
SECURITY_LOG_CHANNEL_ID=1441224922486542387
SECURITY_TIMEOUT_SECONDS=7200
SECURITY_DM_OWNER_ID=your_discord_user_id
```

## ✅ Approval System

When a new member joins:

- Windy posts an approval card in the approval channel.
- Members can vote to approve.
- President can approve or deny instantly.
- Approved users receive a DM with the rules channel link.
- Denied users are kicked.

Current defaults:

- Humans need `3` approvals.
- Bots need `3` approvals.
- Rules channel: `<#1337444919773761629>`

After changing approval settings, run `/setup` again if MongoDB already has old saved values.

## 👑 `/setup`

Use `/setup` inside Discord to save server-specific settings:

- Approval channel
- Pending role
- Comrade/member role
- Bot role
- President role
- Human approval count
- Bot approval count

These saved settings are stored in MongoDB and override fallback values from `.env` or `config.py`.

## 🛡️ Security System

The security module catches scam/spam content like:

- Crypto bonus messages
- Fake withdrawal or USDT messages
- Gambling/casino promos
- Fake gifts, claims, giveaways, airdrops
- Suspicious links
- Repeated image spam
- Repeated message spam

When security triggers:

1. 🗑️ Deletes the bad message
2. 📩 DMs the user
3. 🔇 Times them out for 2 hours
4. 👑 DMs the configured owner/President
5. 📝 Sends a public security log embed

Security logs go to:

```env
SECURITY_LOG_CHANNEL_ID=1441224922486542387
```

Set this to your owner Discord user ID:

```env
SECURITY_DM_OWNER_ID=your_discord_user_id
```

## 🔗 Invite Requests

Users can request invite links in the configured invite request channel.

Admins, President, or users with invite permissions can approve or deny requests.

The bot creates one-use invite links when approved.

## 📊 Dashboard

The dashboard is a private moderation panel.

Useful config:

```env
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8080
DASHBOARD_OPEN_URL=https://your-public-dashboard-url
```

Use:

```text
/dashboard
```

Only President users can open the dashboard.

## 🔐 Required Bot Permissions

Make sure the bot has:

- View Channels
- Send Messages
- Embed Links
- Read Message History
- Manage Messages
- Moderate Members
- Kick Members
- Manage Roles
- Create Invite

For timeouts to work, the bot role must be above the target user role.

## 🧪 Useful Commands

```text
/help
/setup
/dashboard
/approval
/commands
/request_invite
```

Text commands also exist:

```text
.help
.setup
.dashboard
.request_invite
```

## 🧯 Troubleshooting

### Logs are going to the wrong channel

Run `/setup` again and choose the correct approval channel.

Security logs use:

```env
SECURITY_LOG_CHANNEL_ID=1441224922486542387
```

Approval logs use `/setup` saved settings first, then `APPROVAL_CHANNEL_ID`.

### Approval still needs 5 votes

MongoDB probably saved the old `/setup` value.

Run `/setup` again and set bot approvals to `3`.

### Timeout does not work

Check:

- Bot has `Moderate Members`
- Bot role is higher than the user role
- User is not admin, President, or manage-messages staff

### User does not get a DM

The user may have DMs closed. The bot will still delete, timeout, and log.

## 🚀 Run

```bash
python bot.py
```

When it starts correctly, you should see MongoDB connect and the bot come online.
