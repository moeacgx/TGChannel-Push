"""Add caption and media_file_id columns to ad_creatives table."""

import sqlite3
import sys
from pathlib import Path


def migrate():
    """Run migration to add new columns."""
    db_path = Path(__file__).parent.parent / "data" / "techannel.db"

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        print("Run the application first to create the database.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check existing columns
    cursor.execute("PRAGMA table_info(ad_creatives)")
    columns = {row[1] for row in cursor.fetchall()}

    migrations = []

    if "caption" not in columns:
        migrations.append("ALTER TABLE ad_creatives ADD COLUMN caption TEXT")
        print("Adding 'caption' column...")

    if "media_file_id" not in columns:
        migrations.append("ALTER TABLE ad_creatives ADD COLUMN media_file_id TEXT")
        print("Adding 'media_file_id' column...")

    if not migrations:
        print("No migrations needed. All columns already exist.")
        conn.close()
        return

    # Run migrations
    for sql in migrations:
        cursor.execute(sql)
        print(f"  Executed: {sql}")

    # Copy caption_preview to caption for existing records
    cursor.execute("""
        UPDATE ad_creatives
        SET caption = caption_preview
        WHERE caption IS NULL AND caption_preview IS NOT NULL
    """)
    updated = cursor.rowcount
    print(f"  Copied caption_preview to caption for {updated} existing records")

    conn.commit()
    conn.close()

    print("\nMigration completed successfully!")


if __name__ == "__main__":
    migrate()
