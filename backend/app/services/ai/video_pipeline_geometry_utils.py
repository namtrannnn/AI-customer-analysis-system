from typing import Dict, List, Optional

import cv2
import numpy as np


class VideoPipelineGeometryMixin:
    def _is_valid_person_crop_for_identity(self, frame, bbox) -> bool:
        """
        Chặn crop người quá xấu trước khi tạo/match identity.

        Mục tiêu:
        - Tránh case mới thấy chân/thân mà đã tạo profile.
        - Tránh làm bẩn appearance profile.
        """

        if frame is None or bbox is None:
            return False

        h, w = frame.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in bbox]

        x1 = max(0, min(x1, w - 1))
        x2 = max(0, min(x2, w))
        y1 = max(0, min(y1, h - 1))
        y2 = max(0, min(y2, h))

        box_w = max(0, x2 - x1)
        box_h = max(0, y2 - y1)

        if box_w < 40 or box_h < 100:
            return False

        ratio = box_h / (box_w + 1e-6)

        # Người đứng bình thường thường cao hơn rộng.
        if ratio < 1.2 or ratio > 5.0:
            return False

        # Nếu bbox nằm rất thấp, dễ là chỉ thấy chân/thân dưới.
        bottom_touch = y2 >= h - 5
        top_is_low = y1 > h * 0.65

        if bottom_touch and top_is_low:
            return False

        return True

    def _bbox_area_ratio(self, box_a, box_b) -> float:
        if box_a is None or box_b is None:
            return 0.0
        ax1, ay1, ax2, ay2 = [float(v) for v in box_a]
        bx1, by1, bx2, by2 = [float(v) for v in box_b]
        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        if area_a <= 0 or area_b <= 0:
            return 0.0
        small = min(area_a, area_b)
        large = max(area_a, area_b)
        if small <= 0:
            return 0.0
        return float(large / small)

    def _track_motion_norm(
        self,
        frame_bboxes: Optional[Dict[int, List[float]]],
        max_points: int = 12,
    ) -> float:
        """
        Độ dịch chuyển tâm bbox được chuẩn hoá theo kích thước bbox trung bình.
        Nhỏ => track đứng yên; lớn => track đang đi ngang/đi qua.
        """
        if not frame_bboxes or len(frame_bboxes) < 2:
            return 0.0

        items = sorted((int(f), b) for f, b in frame_bboxes.items() if b is not None)
        if len(items) < 2:
            return 0.0
        items = items[-max_points:]

        centers = []
        scales = []
        for _, box in items:
            x1, y1, x2, y2 = [float(v) for v in box]
            w = max(1.0, x2 - x1)
            h = max(1.0, y2 - y1)
            centers.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0))
            scales.append(max(w, h))

        dx = centers[-1][0] - centers[0][0]
        dy = centers[-1][1] - centers[0][1]
        scale = max(float(sum(scales) / len(scales)), 1.0)
        return float((dx * dx + dy * dy) ** 0.5 / scale)

    def _is_duplicate_like_bbox(
        self,
        box_a,
        box_b,
        duplicate_iou_threshold: float = 0.55,
        containment_threshold: float = 0.70,
        center_distance_norm_threshold: float = 0.12,
        area_ratio_min: float = 0.40,
        area_ratio_max: float = 2.80,
    ) -> tuple:
        if box_a is None or box_b is None:
            return False, 0.0

        ratio = self._bbox_area_ratio(box_a, box_b)
        if ratio < area_ratio_min or ratio > area_ratio_max:
            return False, 0.0

        iou = self._bbox_iou(box_a, box_b)
        containment = self._bbox_containment(box_a, box_b)
        center_norm = self._bbox_center_distance_norm(box_a, box_b)

        center_ok = center_norm <= center_distance_norm_threshold
        duplicate_like = (
            iou >= duplicate_iou_threshold
            or containment >= containment_threshold
            or (center_ok and containment >= 0.45)
        )

        score = max(iou, containment * 0.95, max(0.0, 1.0 - center_norm) * 0.70)
        return bool(duplicate_like), float(score)

    def _bbox_containment(self, box_a, box_b) -> float:
        if box_a is None or box_b is None:
            return 0.0
        ax1, ay1, ax2, ay2 = [float(v) for v in box_a]
        bx1, by1, bx2, by2 = [float(v) for v in box_b]
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        small = min(area_a, area_b)
        if small <= 0:
            return 0.0
        return float(inter_area / small)

    def _bbox_center_distance_norm(self, box_a, box_b) -> float:
        if box_a is None or box_b is None:
            return 999.0
        ax1, ay1, ax2, ay2 = [float(v) for v in box_a]
        bx1, by1, bx2, by2 = [float(v) for v in box_b]
        acx = (ax1 + ax2) / 2.0
        acy = (ay1 + ay2) / 2.0
        bcx = (bx1 + bx2) / 2.0
        bcy = (by1 + by2) / 2.0
        aw = max(1.0, ax2 - ax1)
        ah = max(1.0, ay2 - ay1)
        bw = max(1.0, bx2 - bx1)
        bh = max(1.0, by2 - by1)
        norm = max(aw, ah, bw, bh, 1.0)
        dist = ((acx - bcx) ** 2 + (acy - bcy) ** 2) ** 0.5
        return float(dist / norm)

    def _bbox_iou(self, box_a, box_b) -> float:
        if box_a is None or box_b is None:
            return 0.0

        ax1, ay1, ax2, ay2 = [float(v) for v in box_a]
        bx1, by1, bx2, by2 = [float(v) for v in box_b]

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h

        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)

        union = area_a + area_b - inter_area
        if union <= 0:
            return 0.0

        return float(inter_area / union)

    def _is_duplicate_like_bbox_pair(self, box_a, box_b) -> bool:
        iou = self._bbox_iou(box_a, box_b)
        containment = self._bbox_containment(box_a, box_b)
        center_norm = self._bbox_center_distance_norm(box_a, box_b)
        area_ratio = self._bbox_area_ratio(box_a, box_b)
        return bool(
            iou >= 0.55
            or containment >= 0.82
            or (center_norm <= 0.075 and 0.60 <= area_ratio <= 1.75 and containment >= 0.45)
        )

    def _track_span(self, track_frame_bboxes: Dict[int, Dict[int, List[float]]], track_id: int):
        bboxes = track_frame_bboxes.get(track_id, {}) or {}
        if not bboxes:
            return None
        frames = sorted(int(f) for f in bboxes.keys())
        return frames[0], frames[-1]

    def _track_bbox_at(self, track_frame_bboxes: Dict[int, Dict[int, List[float]]], track_id: int, frame_index: int):
        bboxes = track_frame_bboxes.get(track_id, {}) or {}
        return bboxes.get(frame_index) or bboxes.get(str(frame_index))

