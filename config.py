import os


def load_local_env(path=".env"):
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()


def env_int(name, default):
    value = os.getenv(name)
    return int(value) if value else default


TOKEN = os.getenv("DISCORD_TOKEN", "")

APPROVAL_CHANNEL_ID = env_int("APPROVAL_CHANNEL_ID", 1440967805846552677)
REQUEST_INVITE_CHANNEL_ID = env_int("REQUEST_INVITE_CHANNEL_ID", 1393801371542622308)

PENDING_ROLE_ID = env_int("PENDING_ROLE_ID", 1350648247898869760)
COMRADE_ROLE_ID = env_int("COMRADE_ROLE_ID", 1274015762352181389)
BOT_ROLE_ID = env_int("BOT_ROLE_ID", 1147093707326226506)
PRESIDENT_ROLE_ID = env_int("PRESIDENT_ROLE_ID", 1270692749863292949)

HUMAN_APPROVE_REQUIRED = env_int("HUMAN_APPROVE_REQUIRED", 3)
BOT_APPROVE_REQUIRED = env_int("BOT_APPROVE_REQUIRED", 5)

MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "Discord_bot")

DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = env_int("DASHBOARD_PORT", 8080)
DASHBOARD_OPEN_URL = os.getenv("DASHBOARD_OPEN_URL", "http://127.0.0.1:8080")
