"""CLI commands for TGChannel-Push."""

import asyncio
import sys


def init_db_command() -> None:
    """Initialize the database."""
    from tgchannel_push.database import init_db

    print("Initializing database...")
    asyncio.run(init_db())
    print("Database initialized successfully!")


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m tgchannel_push.cli <command>")
        print("Commands:")
        print("  init-db    Initialize the database")
        sys.exit(1)

    command = sys.argv[1]

    if command == "init-db":
        init_db_command()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
