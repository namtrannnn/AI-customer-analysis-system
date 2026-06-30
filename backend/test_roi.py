"""
Test AI-11 ROI Service voi zones that tu DB.

Chay:
    cd d:\\ai-customer-analysis-system\\backend
    venv\\Scripts\\activate
    python test_roi.py
"""

from app.database.session import SessionLocal
from app.models.store_zone import StoreZone
from app.services.ai.roi_service import roi_service


def main():
    # ─── 1. Lấy zones từ DB ───────────────────────────────────────────────────
    db = SessionLocal()
    try:
        zones_db = db.query(StoreZone).all()
    finally:
        db.close()

    if not zones_db:
        print("❌ Chưa có zone nào trong DB.")
        print("   → Vào UI /zones, upload ảnh nền, vẽ ít nhất 1 vùng và lưu trước.")
        return

    # Convert sang dict cho ROI service
    zones = [
        {
            "id": z.id,
            "zone_name": z.zone_name,
            "polygon": z.polygon or [],
        }
        for z in zones_db
    ]

    print(f"\n✓ Tìm thấy {len(zones)} zone(s) trong DB:\n")
    for z in zones:
        pts = len(z["polygon"])
        print(f"  [{z['id']}] {z['zone_name']} — {pts} điểm polygon")
        if pts > 0:
            # In ra bounding box của polygon để biết test điểm nào
            xs = [p["x"] for p in z["polygon"]]
            ys = [p["y"] for p in z["polygon"]]
            print(f"       Bounding box: x=[{min(xs):.2f}~{max(xs):.2f}] y=[{min(ys):.2f}~{max(ys):.2f}]")
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)
            print(f"       Centroid: ({cx:.2f}, {cy:.2f})")

    print()

    # ─── 2. Test centroid của chính từng zone ────────────────────────────────
    print("\n─── Test centroid của từng zone (phải hit chính xác) ──────────")
    valid_zones = [z for z in zones if len(z["polygon"]) >= 3]

    if not valid_zones:
        print("  ❌ Không có zone nào có polygon hợp lệ (cần ≥ 3 điểm)")
    else:
        for z in valid_zones:
            xs = [p["x"] for p in z["polygon"]]
            ys = [p["y"] for p in z["polygon"]]
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)
            result = roi_service.find_zone_for_point(cx, cy, zones)
            status = f"✅ Zone [{result.zone_id}] '{result.zone_name}'" if result.is_inside else "❌ MISS (centroid nằm ngoài polygon?)"
            print(f"  Zone '{z['zone_name']}' centroid ({cx:.2f},{cy:.2f}) → {status}")

    print()

    # ─── 3. Test batch với mock detections ───────────────────────────────────
    print("─── Batch check (giả lập 4 detection) ────────────────────────")
    mock_detections = [
        {"person_index": 1, "bbox": [0.05, 0.05, 0.25, 0.35]},
        {"person_index": 2, "bbox": [0.40, 0.40, 0.60, 0.60]},
        {"person_index": 3, "bbox": [0.70, 0.10, 0.90, 0.40]},
        {"person_index": 4, "bbox": [0.30, 0.60, 0.50, 0.90]},
    ]

    batch = roi_service.batch_check_detections(mock_detections, zones)
    for r in batch:
        zone_info = f"Zone [{r.zone_id}] '{r.zone_name}'" if r.zone_id else "Ngoài zone"
        print(f"  Person #{r.person_index} tại ({r.center_x:.2f}, {r.center_y:.2f}) → {zone_info}")

    print()

    # ─── 4. Test normalize bbox pixel ────────────────────────────────────────
    print("─── Normalize pixel bbox (frame 1280x720) ─────────────────────")
    pixel_bbox = (128, 72, 640, 360)  # Chiếm 1/4 màn hình góc trên trái
    nx1, ny1, nx2, ny2 = roi_service.normalize_bbox(*pixel_bbox, 1280, 720)
    print(f"  Pixel {pixel_bbox} → Normalized ({nx1:.2f}, {ny1:.2f}, {nx2:.2f}, {ny2:.2f})")
    result = roi_service.find_zone_for_bbox(nx1, ny1, nx2, ny2, zones)
    zone_info = f"Zone [{result.zone_id}] '{result.zone_name}'" if result.is_inside else "Ngoài zone"
    print(f"  Centroid tại ({(nx1+nx2)/2:.2f}, {(ny1+ny2)/2:.2f}) → {zone_info}")

    print("\n✓ Test hoàn tất!")


if __name__ == "__main__":
    main()
