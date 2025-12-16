#!/usr/bin/env python3
"""Database migration: Add name column to slots and ad_creatives tables."""

import sqlite3
import sys
from pathlib import Path

# Database path
DB_PATH = Path("/app/data/tgchannel.db")

# For local development
if not DB_PATH.exists():
    DB_PATH = Path("data/tgchannel.db")

if not DB_PATH.exists():
    print(f"Error: Database not found at {DB_PATH}")
    sys.exit(1)

print(f"Migrating database: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Migration 1: Add name column to slots table
cursor.execute("PRAGMA table_info(slots)")
slots_columns = [col[1] for col in cursor.fetchall()]

if "name" in slots_columns:
    print("[slots] Column 'name' already exists, skipping.")
else:
    cursor.execute("ALTER TABLE slots ADD COLUMN name TEXT")
    conn.commit()
    print("[slots] Added column 'name'.")

# Migration 2: Add name column to ad_creatives table
cursor.execute("PRAGMA table_info(ad_creatives)")
creatives_columns = [col[1] for col in cursor.fetchall()]

if "name" in creatives_columns:
    print("[ad_creatives] Column 'name' already exists, skipping.")
else:
    cursor.execute("ALTER TABLE ad_creatives ADD COLUMN name TEXT")
    conn.commit()
    print("[ad_creatives] Added column 'name'.")

conn.close()
print("Migration completed!")
