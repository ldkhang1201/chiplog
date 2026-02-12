import os

from dotenv import load_dotenv

from infrastructure.db.identity_repository_sqlite import SqliteIdentityRepository
from infrastructure.db.user_repository_sqlite import SqliteUserRepository
from interfaces.discord.handlers import create_discord_bot


load_dotenv()

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
DB_PATH = os.environ.get("DB_PATH", "poker.db")


def main() -> None:
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN environment variable is not set.")

    user_repo = SqliteUserRepository(DB_PATH)
    identity_repo = SqliteIdentityRepository(DB_PATH, user_repo)

    bot = create_discord_bot(user_repo, identity_repo)
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()

