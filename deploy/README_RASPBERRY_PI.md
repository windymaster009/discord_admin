# Raspberry Pi 4 Deployment

These steps run Windy as a background service on Raspberry Pi OS.

## 1. Install system packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

## 2. Copy the project

Put this project at:

```bash
/home/pi/bot-role
```

If you use a different path or username, edit `deploy/windy-bot.service`.

## 3. Create the Python environment

```bash
cd /home/pi/bot-role
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

## 4. Create `.env`

```bash
cp .env.example .env
nano .env
```

Set:

```env
DISCORD_TOKEN=your_discord_bot_token
MONGO_URI=your_mongodb_atlas_uri
MONGO_DB_NAME=Discord_bot
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8080
DASHBOARD_OPEN_URL=http://your-pi-ip:8080
REQUEST_INVITE_CHANNEL_ID=1393801371542622308
```

For example, find your Pi IP:

```bash
hostname -I
```

## 5. Test manually

```bash
cd /home/pi/bot-role
.venv/bin/python bot.py
```

Stop it with `Ctrl+C` after you see it online.

## 6. Install systemd service

```bash
sudo cp /home/pi/bot-role/deploy/windy-bot.service /etc/systemd/system/windy-bot.service
sudo systemctl daemon-reload
sudo systemctl enable windy-bot
sudo systemctl start windy-bot
```

## 7. Useful commands

```bash
sudo systemctl status windy-bot
sudo journalctl -u windy-bot -f
sudo systemctl restart windy-bot
sudo systemctl stop windy-bot
```

## 8. Discord setup

After the bot is online:

1. Make sure the invite includes `bot` and `applications.commands`.
2. Run `/setup` in each server to save that server's roles and approval channel.
3. Use `.dashboard` or `/dashboard` in the configured approval channel.
4. Users can request one-use invite links in the configured request channel with `/request_invite`, `.invite`, or by posting a message there.

## Notes

- Keep `.env` private.
- If MongoDB fails on the Pi, check Atlas Network Access and allow your Pi network IP.
- If using a home network and you want dashboard access from outside, use a tunnel or port forwarding and set `DASHBOARD_OPEN_URL` to that public URL.
