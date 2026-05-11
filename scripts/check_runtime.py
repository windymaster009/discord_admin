import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from config import DASHBOARD_OPEN_URL, MONGO_DB_NAME, MONGO_URI, TOKEN
from database import init_db


def main():
    print("Discord token set:", bool(TOKEN))
    print("Mongo URI set:", bool(MONGO_URI))
    print("Mongo DB:", MONGO_DB_NAME)
    print("Dashboard URL:", DASHBOARD_OPEN_URL)
    init_db()
    print("Runtime check passed.")


if __name__ == "__main__":
    main()
