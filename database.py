import datetime

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
except ImportError:
    MongoClient = None

    class PyMongoError(Exception):
        pass

    class ServerSelectionTimeoutError(PyMongoError):
        pass

from config import (
    APPROVAL_CHANNEL_ID,
    BOT_APPROVE_REQUIRED,
    BOT_ROLE_ID,
    COMRADE_ROLE_ID,
    HUMAN_APPROVE_REQUIRED,
    MONGO_DB_NAME,
    MONGO_URI,
    PENDING_ROLE_ID,
    PRESIDENT_ROLE_ID,
)

mongo_client = None
mongo_db = None


def get_database():
    global mongo_client, mongo_db

    if mongo_db is not None:
        return mongo_db

    if not MONGO_URI:
        raise RuntimeError("MONGO_URI is not set. Add it to your environment or .env file.")

    if MongoClient is None:
        raise RuntimeError("pymongo is not installed. Run: pip install -r requirements.txt")

    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    mongo_db = mongo_client[MONGO_DB_NAME]
    return mongo_db


def init_db():
    try:
        db = get_database()
        db.command("ping")
        db.logs.create_index("ts")
        db.logs.create_index("action")
        db.guild_settings.create_index("guild_id", unique=True)
        print(f"MongoDB connected: {MONGO_DB_NAME}")
    except ServerSelectionTimeoutError as e:
        raise RuntimeError(
            "Could not connect to MongoDB Atlas. Check your MONGO_URI, internet connection, "
            "and Atlas Network Access IP whitelist."
        ) from e
    except PyMongoError as e:
        raise RuntimeError(f"MongoDB startup failed: {e}") from e


def log_db(actor, action, target, detail=""):
    db = get_database()
    try:
        db.logs.insert_one({
            "ts": datetime.datetime.now(datetime.UTC).isoformat(),
            "actor": actor,
            "action": action,
            "target": target,
            "detail": detail,
        })
    except PyMongoError as e:
        print("MongoDB log insert failed:", e)


def default_guild_settings():
    return {
        "approval_channel_id": APPROVAL_CHANNEL_ID,
        "pending_role_id": PENDING_ROLE_ID,
        "comrade_role_id": COMRADE_ROLE_ID,
        "bot_role_id": BOT_ROLE_ID,
        "president_role_id": PRESIDENT_ROLE_ID,
        "human_approve_required": HUMAN_APPROVE_REQUIRED,
        "bot_approve_required": BOT_APPROVE_REQUIRED,
        "is_configured": False,
    }


def get_guild_settings(guild_id):
    settings = default_guild_settings()
    db = get_database()
    row = db.guild_settings.find_one({"guild_id": int(guild_id)})

    if not row:
        return settings

    settings.update({
        "approval_channel_id": int(row["approval_channel_id"]),
        "pending_role_id": int(row["pending_role_id"]),
        "comrade_role_id": int(row["comrade_role_id"]),
        "bot_role_id": int(row["bot_role_id"]),
        "president_role_id": int(row["president_role_id"]),
        "human_approve_required": int(row["human_approve_required"]),
        "bot_approve_required": int(row["bot_approve_required"]),
        "is_configured": True,
    })
    return settings


def save_guild_settings(
    guild_id,
    approval_channel_id,
    pending_role_id,
    comrade_role_id,
    bot_role_id,
    president_role_id,
    human_approve_required,
    bot_approve_required,
):
    db = get_database()
    db.guild_settings.update_one(
        {"guild_id": int(guild_id)},
        {
            "$set": {
                "guild_id": int(guild_id),
                "approval_channel_id": int(approval_channel_id),
                "pending_role_id": int(pending_role_id),
                "comrade_role_id": int(comrade_role_id),
                "bot_role_id": int(bot_role_id),
                "president_role_id": int(president_role_id),
                "human_approve_required": int(human_approve_required),
                "bot_approve_required": int(bot_approve_required),
                "updated_at": datetime.datetime.now(datetime.UTC).isoformat(),
            }
        },
        upsert=True,
    )
