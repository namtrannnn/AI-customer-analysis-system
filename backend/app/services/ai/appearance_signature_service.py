import cv2
import numpy as np
from typing import Dict, List, Optional


class AppearanceSignatureService:
    """
    Trích đặc trưng ngoại hình đơn giản từ person crop:
    - upper_hist: màu áo / thân trên
    - head_hist: màu vùng đầu / nón / tóc

    Chỉ dùng làm tín hiệu phụ cho face matching.
    Không dùng appearance để thay thế hoàn toàn face embedding.
    """

    def __init__(self) -> None:
        self.hist_bins = [16, 16]
        self.hist_ranges = [0, 180, 0, 256]

    def extract_from_person_crop(
        self,
        frame: np.ndarray,
        bbox: List[float],
    ) -> Optional[Dict]:
        if frame is None or bbox is None:
            return None

        h, w = frame.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in bbox]

        x1 = max(0, min(x1, w - 1))
        x2 = max(0, min(x2, w))
        y1 = max(0, min(y1, h - 1))
        y2 = max(0, min(y2, h))

        if x2 <= x1 or y2 <= y1:
            return None

        person_crop = frame[y1:y2, x1:x2]

        if person_crop is None or person_crop.size == 0:
            return None

        crop_h, crop_w = person_crop.shape[:2]

        if crop_h < 40 or crop_w < 20:
            return None

        # Vùng đầu/nón: 0% -> 28% chiều cao người
        head_y1 = 0
        head_y2 = max(1, int(crop_h * 0.28))
        head_x1 = max(0, int(crop_w * 0.15))
        head_x2 = min(crop_w, int(crop_w * 0.85))

        # Vùng áo/thân trên: 25% -> 70% chiều cao người
        upper_y1 = max(0, int(crop_h * 0.25))
        upper_y2 = min(crop_h, int(crop_h * 0.70))
        upper_x1 = max(0, int(crop_w * 0.10))
        upper_x2 = min(crop_w, int(crop_w * 0.90))

        head_zone = person_crop[head_y1:head_y2, head_x1:head_x2]
        upper_zone = person_crop[upper_y1:upper_y2, upper_x1:upper_x2]

        head_hist = self._calc_hs_hist(head_zone)
        upper_hist = self._calc_hs_hist(upper_zone)

        if head_hist is None and upper_hist is None:
            return None

        return {
            "head_hist": head_hist.tolist() if head_hist is not None else [],
            "upper_hist": upper_hist.tolist() if upper_hist is not None else [],
        }

    def compare(self, sig_a: Dict, sig_b: Dict) -> float:
        """
        Trả về điểm giống appearance từ 0 -> 1.
        Ưu tiên áo hơn vùng đầu/nón vì vùng đầu dễ nhiễu hơn.
        """

        if not sig_a or not sig_b:
            return 0.0

        upper_a = np.array(sig_a.get("upper_hist", []), dtype=np.float32)
        upper_b = np.array(sig_b.get("upper_hist", []), dtype=np.float32)

        head_a = np.array(sig_a.get("head_hist", []), dtype=np.float32)
        head_b = np.array(sig_b.get("head_hist", []), dtype=np.float32)

        upper_score = self._hist_similarity(upper_a, upper_b)
        head_score = self._hist_similarity(head_a, head_b)

        if upper_score > 0 and head_score > 0:
            return float(upper_score * 0.75 + head_score * 0.25)

        if upper_score > 0:
            return float(upper_score)

        if head_score > 0:
            return float(head_score)

        return 0.0

    def _calc_hs_hist(self, image: np.ndarray) -> Optional[np.ndarray]:
        if image is None or image.size == 0:
            return None

        h, w = image.shape[:2]

        if h < 5 or w < 5:
            return None

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        hist = cv2.calcHist(
            [hsv],
            [0, 1],
            None,
            self.hist_bins,
            self.hist_ranges,
        )

        cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)

        return hist.flatten()

    def _hist_similarity(self, hist_a: np.ndarray, hist_b: np.ndarray) -> float:
        if hist_a.size == 0 or hist_b.size == 0:
            return 0.0

        if hist_a.shape != hist_b.shape:
            return 0.0

        score = cv2.compareHist(
            hist_a.astype(np.float32),
            hist_b.astype(np.float32),
            cv2.HISTCMP_CORREL,
        )

        # HISTCMP_CORREL nằm trong khoảng -1 -> 1.
        # Chuyển về 0 -> 1.
        score = (score + 1.0) / 2.0

        return max(0.0, min(1.0, float(score)))