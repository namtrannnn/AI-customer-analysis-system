"""
Debug tracking data trong DB.
Chay: python debug_tracking.py
"""

from app.database.session import SessionLocal
from app.models.movement_track import MovementTrack
from app.models.person_profile import PersonProfile
from app.models.visit_sessions import VisitSession
from sqlalchemy import func


def main():
    db = SessionLocal()
    try:
        # ── 1. Tổng quan ─────────────────────────────────────────────────────
        total_tracks = db.query(MovementTrack).count()
        total_sessions = db.query(VisitSession).count()
        total_profiles = db.query(PersonProfile).filter(
            PersonProfile.anonymous_code.like("P_%") |
            PersonProfile.anonymous_code.like("TRK_%")
        ).count()

        print(f"\n{'='*60}")
        print(f"TRACKING DEBUG REPORT")
        print(f"{'='*60}")
        print(f"Total movement_track points : {total_tracks}")
        print(f"Total visit_sessions        : {total_sessions}")
        print(f"Total person_profiles       : {total_profiles}")

        # ── 2. Group theo person_profile ─────────────────────────────────────
        print(f"\n{'─'*60}")
        print(f"{'PERSON':<15} {'POINTS':>8} {'SESSIONS':>10} {'X_MIN':>8} {'X_MAX':>8} {'Y_MIN':>8} {'Y_MAX':>8}")
        print(f"{'─'*60}")

        person_stats = (
            db.query(
                MovementTrack.person_profile_id,
                func.count(MovementTrack.id).label("point_count"),
                func.min(MovementTrack.position_x).label("x_min"),
                func.max(MovementTrack.position_x).label("x_max"),
                func.min(MovementTrack.position_y).label("y_min"),
                func.max(MovementTrack.position_y).label("y_max"),
            )
            .group_by(MovementTrack.person_profile_id)
            .order_by(func.count(MovementTrack.id).desc())
            .all()
        )

        for stat in person_stats:
            profile = db.query(PersonProfile).filter(
                PersonProfile.id == stat.person_profile_id
            ).first()
            acode = profile.anonymous_code if profile else "???"

            session_count = db.query(VisitSession).filter(
                VisitSession.person_profile_id == stat.person_profile_id
            ).count()

            print(
                f"{acode:<15} {stat.point_count:>8} {session_count:>10} "
                f"{stat.x_min or 0:>8.3f} {stat.x_max or 0:>8.3f} "
                f"{stat.y_min or 0:>8.3f} {stat.y_max or 0:>8.3f}"
            )

        # ── 3. Sample points của từng person ─────────────────────────────────
        print(f"\n{'─'*60}")
        print("SAMPLE POINTS (first 3 per person):")
        print(f"{'─'*60}")

        for stat in person_stats[:6]:  # Top 6
            profile = db.query(PersonProfile).filter(
                PersonProfile.id == stat.person_profile_id
            ).first()
            acode = profile.anonymous_code if profile else "???"

            pts = (
                db.query(MovementTrack)
                .filter(MovementTrack.person_profile_id == stat.person_profile_id)
                .order_by(MovementTrack.tracked_at)
                .limit(3)
                .all()
            )

            print(f"\n  {acode} — {stat.point_count} points:")
            for pt in pts:
                print(
                    f"    x={pt.position_x:.3f} y={pt.position_y:.3f} "
                    f"zone={pt.zone_id} at={pt.tracked_at}"
                )

        # ── 4. Kiểm tra range tọa độ ─────────────────────────────────────────
        print(f"\n{'─'*60}")
        print("COORDINATE SANITY CHECK:")

        bad_x = db.query(MovementTrack).filter(
            (MovementTrack.position_x < 0) | (MovementTrack.position_x > 1)
        ).count()
        bad_y = db.query(MovementTrack).filter(
            (MovementTrack.position_y < 0) | (MovementTrack.position_y > 1)
        ).count()

        print(f"  Points với x ngoài [0,1]: {bad_x}")
        print(f"  Points với y ngoài [0,1]: {bad_y}")

        if bad_x > 0 or bad_y > 0:
            print("  ❌ TỌA ĐỘ SAI! Cần kiểm tra normalize bbox.")
        else:
            print("  ✅ Tọa độ hợp lệ (0..1)")

        # ── 5. Kiểm tra zone assignment ───────────────────────────────────────
        print(f"\n{'─'*60}")
        print("ZONE ASSIGNMENT CHECK:")

        from app.models.store_zone import StoreZone
        zones = db.query(StoreZone).all()
        print(f"  Số zones trong DB: {len(zones)}")
        for z in zones:
            pts_in_zone = db.query(MovementTrack).filter(
                MovementTrack.zone_id == z.id
            ).count()
            pts_polygon = len(z.polygon) if z.polygon else 0
            print(f"  Zone [{z.id}] '{z.zone_name}': {pts_in_zone} points | polygon={pts_polygon} điểm")

        pts_no_zone = db.query(MovementTrack).filter(
            MovementTrack.zone_id == None
        ).count()
        print(f"  Points ngoài zone (zone_id=NULL): {pts_no_zone}")

        total_pts = db.query(MovementTrack).count()
        if total_pts > 0:
            pct_in_zone = round((total_pts - pts_no_zone) / total_pts * 100, 1)
            print(f"  Tỷ lệ trong zone: {pct_in_zone}% ({total_pts - pts_no_zone}/{total_pts})")
            if pct_in_zone > 30:
                print("  ✅ Zone assignment hợp lý")
            else:
                print("  ⚠️  Ít điểm trong zone — kiểm tra lại vị trí vẽ zone")

        print(f"\n{'='*60}\n")

    finally:
        db.close()


if __name__ == "__main__":
    main()
