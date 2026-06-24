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
    # ── cameras (tạo nếu chưa có để FK sau này dùng được) ────────────────────
    """
    CREATE TABLE IF NOT EXISTS cameras (
        id              BIGSERIAL PRIMARY KEY,
        camera_name     VARCHAR(100) NOT NULL,
        camera_position VARCHAR(100),
        mode            VARCHAR(30) NOT NULL DEFAULT 'anonymous',
        rtsp_url        TEXT,
        status          VARCHAR(30) NOT NULL DEFAULT 'active',
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # ── store_zones ───────────────────────────────────────────────────────────
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS polygon JSONB DEFAULT '[]'::jsonb",
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS color VARCHAR(20) NOT NULL DEFAULT '#3b82f6'",
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS total_visits INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "ALTER TABLE store_zones ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",

    # ── movement_tracks ───────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS movement_tracks (
        id                BIGSERIAL PRIMARY KEY,
        visit_session_id  BIGINT NOT NULL REFERENCES visit_sessions(id) ON DELETE CASCADE,
        person_profile_id BIGINT NOT NULL REFERENCES person_profiles(id) ON DELETE CASCADE,
        zone_id           BIGINT REFERENCES store_zones(id) ON DELETE SET NULL,
        position_x        DOUBLE PRECISION,
        position_y        DOUBLE PRECISION,
        tracked_at        TIMESTAMP NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_movement_tracks_session ON movement_tracks(visit_session_id)",
    "CREATE INDEX IF NOT EXISTS idx_movement_tracks_person ON movement_tracks(person_profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_movement_tracks_tracked_at ON movement_tracks(tracked_at)",

    # ── zone_visits ───────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS zone_visits (
        id                BIGSERIAL PRIMARY KEY,
        visit_session_id  BIGINT NOT NULL REFERENCES visit_sessions(id) ON DELETE CASCADE,
        person_profile_id BIGINT NOT NULL REFERENCES person_profiles(id) ON DELETE CASCADE,
        zone_id           BIGINT NOT NULL REFERENCES store_zones(id) ON DELETE CASCADE,
        enter_time        TIMESTAMP NOT NULL,
        leave_time        TIMESTAMP,
        duration_seconds  INTEGER
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_zone_visits_session ON zone_visits(visit_session_id)",
    "CREATE INDEX IF NOT EXISTS idx_zone_visits_zone ON zone_visits(zone_id)",
    "CREATE INDEX IF NOT EXISTS idx_zone_visits_person ON zone_visits(person_profile_id)",
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
