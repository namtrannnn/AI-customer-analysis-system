"""
AI-11 ROI Service

Kiểm tra điểm tọa độ có nằm trong vùng ROI (polygon) không.
Tất cả tọa độ dùng hệ tương đối (0.0 → 1.0) để độc lập với resolution.

Thuật toán: Ray Casting
- Bắn 1 tia ngang từ điểm về phía phải (x → +∞)
- Đếm số lần tia cắt qua các cạnh polygon
- Số lần lẻ  → điểm nằm TRONG polygon
- Số lần chẵn → điểm nằm NGOÀI polygon
"""

from dataclasses import dataclass


@dataclass
class ZoneCheckResult:
    """Kết quả kiểm tra điểm trong vùng."""
    zone_id: int | None
    zone_name: str | None
    is_inside: bool


@dataclass
class BatchCheckResult:
    """Kết quả kiểm tra batch nhiều detection."""
    person_index: int
    center_x: float
    center_y: float
    zone_id: int | None
    zone_name: str | None


class ROIService:
    """
    AI-11: Region of Interest Service.

    Xác định vùng (zone) mà một người đang đứng dựa trên tọa độ bounding box.
    Dùng trong Movement Track Pipeline để gán zone_id cho từng track point.
    """

    # ─── Core geometry ────────────────────────────────────────────────────────

    def point_in_polygon(
        self,
        x: float,
        y: float,
        polygon: list[dict],
    ) -> bool:
        """
        Ray Casting — kiểm tra điểm (x, y) có nằm trong polygon không.

        Args:
            x, y : tọa độ tương đối (0.0 → 1.0)
            polygon: list dict [{"x": float, "y": float}, ...]

        Returns:
            True nếu điểm nằm trong polygon
        """
        if len(polygon) < 3:
            return False

        n = len(polygon)
        inside = False

        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]["x"], polygon[i]["y"]
            xj, yj = polygon[j]["x"], polygon[j]["y"]

            # Kiểm tra tia ngang từ (x, y) có cắt cạnh (xi,yi)-(xj,yj) không
            if ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
            ):
                inside = not inside

            j = i

        return inside

    def bbox_centroid(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> tuple[float, float]:
        """
        Tính tâm (centroid) của bounding box.

        Args:
            x1, y1, x2, y2: tọa độ tương đối (0..1)

        Returns:
            (cx, cy) — tâm bounding box
        """
        return (x1 + x2) / 2.0, (y1 + y2) / 2.0

    def normalize_bbox(
        self,
        x1: int | float,
        y1: int | float,
        x2: int | float,
        y2: int | float,
        frame_width: int,
        frame_height: int,
    ) -> tuple[float, float, float, float]:
        """
        Chuẩn hóa bbox pixel → tọa độ tương đối (0..1).

        Args:
            x1, y1, x2, y2  : tọa độ pixel từ YOLO
            frame_width, frame_height: kích thước frame

        Returns:
            (nx1, ny1, nx2, ny2) trong [0, 1]
        """
        w = max(frame_width, 1)
        h = max(frame_height, 1)
        return (
            max(0.0, min(1.0, x1 / w)),
            max(0.0, min(1.0, y1 / h)),
            max(0.0, min(1.0, x2 / w)),
            max(0.0, min(1.0, y2 / h)),
        )

    # ─── Zone lookup ─────────────────────────────────────────────────────────

    def find_zone_for_point(
        self,
        x: float,
        y: float,
        zones: list[dict],
    ) -> ZoneCheckResult:
        """
        Tìm zone đầu tiên chứa điểm (x, y).

        Args:
            x, y  : tọa độ tương đối (0..1)
            zones : list dict [{"id": int, "zone_name": str, "polygon": [...]}]

        Returns:
            ZoneCheckResult với zone_id/zone_name nếu tìm thấy, else None
        """
        for zone in zones:
            polygon = zone.get("polygon") or []
            if not polygon:
                continue

            if self.point_in_polygon(x, y, polygon):
                return ZoneCheckResult(
                    zone_id=zone.get("id"),
                    zone_name=zone.get("zone_name"),
                    is_inside=True,
                )

        return ZoneCheckResult(zone_id=None, zone_name=None, is_inside=False)

    def find_zone_for_bbox(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        zones: list[dict],
    ) -> ZoneCheckResult:
        """
        Tính centroid bbox rồi tìm zone chứa centroid đó.

        Args:
            x1, y1, x2, y2: tọa độ tương đối bbox (0..1)
            zones          : list zone dicts

        Returns:
            ZoneCheckResult
        """
        cx, cy = self.bbox_centroid(x1, y1, x2, y2)
        return self.find_zone_for_point(cx, cy, zones)

    # ─── Batch processing ────────────────────────────────────────────────────

    def batch_check_detections(
        self,
        detections: list[dict],
        zones: list[dict],
        frame_width: int = 1,
        frame_height: int = 1,
    ) -> list[BatchCheckResult]:
        """
        Kiểm tra batch nhiều detection cùng lúc.

        Args:
            detections  : output từ PersonDetectionService
                          Mỗi item cần có: person_index, bbox=[x1,y1,x2,y2]
                          bbox có thể là pixel (cần frame_width/height) hoặc
                          đã chuẩn hóa (frame_width=1, frame_height=1)
            zones       : list zone dicts (từ DB hoặc cache)
            frame_width : chiều rộng frame (pixels) — dùng để normalize
            frame_height: chiều cao frame (pixels)

        Returns:
            list[BatchCheckResult] — mỗi item kèm zone_id gán được
        """
        results: list[BatchCheckResult] = []

        for det in detections:
            bbox = det.get("bbox", [0, 0, 1, 1])
            if len(bbox) < 4:
                continue

            x1, y1, x2, y2 = bbox

            # Normalize nếu là pixel coords
            if frame_width > 1 or frame_height > 1:
                x1, y1, x2, y2 = self.normalize_bbox(
                    x1, y1, x2, y2, frame_width, frame_height
                )

            cx, cy = self.bbox_centroid(x1, y1, x2, y2)
            zone_result = self.find_zone_for_point(cx, cy, zones)

            results.append(
                BatchCheckResult(
                    person_index=det.get("person_index", 0),
                    center_x=round(cx, 4),
                    center_y=round(cy, 4),
                    zone_id=zone_result.zone_id,
                    zone_name=zone_result.zone_name,
                )
            )

        return results

    # ─── Utility ─────────────────────────────────────────────────────────────

    def get_zone_map(self, zones: list[dict]) -> dict[int, str]:
        """
        Tạo dict {zone_id: zone_name} để lookup nhanh.
        """
        return {z["id"]: z.get("zone_name", "") for z in zones if z.get("id")}

    def filter_detections_in_roi(
        self,
        detections: list[dict],
        zone_ids: list[int],
        zones: list[dict],
        frame_width: int = 1,
        frame_height: int = 1,
    ) -> list[dict]:
        """
        Lọc chỉ giữ các detection nằm trong một trong các zone chỉ định.

        Dùng khi muốn chỉ count/track người trong ROI cụ thể.

        Args:
            detections : list detection từ YOLO
            zone_ids   : list zone_id muốn giữ lại
            zones      : list zone dicts
            frame_width/height: để normalize pixel coords

        Returns:
            list detection đã lọc — chỉ những người trong zone_ids
        """
        batch = self.batch_check_detections(detections, zones, frame_width, frame_height)
        allowed_indices = {
            r.person_index for r in batch if r.zone_id in zone_ids
        }
        return [d for d in detections if d.get("person_index") in allowed_indices]


# ─── Singleton instance ───────────────────────────────────────────────────────
roi_service = ROIService()


# ─── Self-test (chạy file trực tiếp để verify) ───────────────────────────────
if __name__ == "__main__":
    # Test polygon hình chữ nhật (0.1,0.1) → (0.5,0.5)
    rect = [
        {"x": 0.1, "y": 0.1},
        {"x": 0.5, "y": 0.1},
        {"x": 0.5, "y": 0.5},
        {"x": 0.1, "y": 0.5},
    ]

    svc = ROIService()

    # Điểm trong polygon
    assert svc.point_in_polygon(0.3, 0.3, rect) is True,  "FAIL: (0.3,0.3) phải nằm trong"
    # Điểm ngoài polygon
    assert svc.point_in_polygon(0.8, 0.8, rect) is False, "FAIL: (0.8,0.8) phải nằm ngoài"
    # Điểm sát biên trái
    assert svc.point_in_polygon(0.09, 0.3, rect) is False, "FAIL: (0.09,0.3) phải nằm ngoài"
    # Điểm sát biên trong
    assert svc.point_in_polygon(0.11, 0.3, rect) is True,  "FAIL: (0.11,0.3) phải nằm trong"

    # Test find_zone_for_point
    zones = [
        {"id": 1, "zone_name": "Lối vào",     "polygon": rect},
        {"id": 2, "zone_name": "Khu trưng bày", "polygon": [
            {"x": 0.6, "y": 0.1},
            {"x": 0.9, "y": 0.1},
            {"x": 0.9, "y": 0.5},
            {"x": 0.6, "y": 0.5},
        ]},
    ]

    r1 = svc.find_zone_for_point(0.3, 0.3, zones)
    assert r1.zone_id == 1, f"FAIL: {r1}"

    r2 = svc.find_zone_for_point(0.75, 0.3, zones)
    assert r2.zone_id == 2, f"FAIL: {r2}"

    r3 = svc.find_zone_for_point(0.55, 0.55, zones)
    assert r3.zone_id is None, f"FAIL: {r3}"

    # Test batch
    detections = [
        {"person_index": 1, "bbox": [0.15, 0.15, 0.45, 0.45]},  # trong zone 1
        {"person_index": 2, "bbox": [0.65, 0.15, 0.85, 0.45]},  # trong zone 2
        {"person_index": 3, "bbox": [0.55, 0.55, 0.75, 0.75]},  # ngoài cả 2
    ]
    batch = svc.batch_check_detections(detections, zones)
    assert batch[0].zone_id == 1
    assert batch[1].zone_id == 2
    assert batch[2].zone_id is None

    print("✓ Tất cả test ROIService pass!")
