"""
Script thêm các cột mới vào bảng store_zones.
Chạy: python migrate_zones.py
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)

migrations = [
    # Thêm polygon (JSON array of {x, y} points)
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS polygon JSONB DEFAULT '[]'::jsonb",
    # Thêm color
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS color VARCHAR(20) NOT NULL DEFAULT '#3b82f6'",
    # Thêm total_visits
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS total_visits INTEGER NOT NULL DEFAULT 0",
    # Thêm timestamps
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
]

with engine.connect() as conn:
    for sql in migrations:
        try:
            conn.execute(text(sql))
            print(f"✓ {sql[:60]}...")
        except Exception as e:
            print(f"✗ Lỗi: {e}")
    conn.commit()

print("\nMigration hoàn tất!")
