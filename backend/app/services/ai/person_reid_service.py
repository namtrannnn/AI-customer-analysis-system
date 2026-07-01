from __future__ import annotations

from typing import Dict, List, Optional

import cv2
import numpy as np


class PersonReIDService:
    """
    Lightweight person/body ReID for tracklet-level correction.

    v2 color-guard version:
    - keeps the original stripe/upper/full HSV histogram cues,
    - adds central torso LAB/HSV color statistics,
    - returns color_* diagnostics in compare_tracklets().

    This is still not a deep ReID model, but it is much stronger for cases like
    red shirt vs white shirt, where face score can be misleading.
    """

    def __init__(self, stripes: int = 6) -> None:
        self.stripes = int(max(3, stripes))
        self.hist_bins = [16, 16]
        self.hist_ranges = [0, 180, 0, 256]

    def extract(self, frame: np.ndarray, bbox: List[float]) -> Optional[Dict]:
        if frame is None or bbox is None:
            return None

        h, w = frame.shape[:2]
        x1, y1, x2, y2 = [int(round(v)) for v in bbox]
        x1 = max(0, min(x1, w - 1))
        x2 = max(0, min(x2, w))
        y1 = max(0, min(y1, h - 1))
        y2 = max(0, min(y2, h))

        if x2 <= x1 or y2 <= y1:
            return None

        crop = frame[y1:y2, x1:x2]
        if crop is None or crop.size == 0:
            return None

        ch, cw = crop.shape[:2]
        if ch < 60 or cw < 24:
            return None

        # Remove a small border to reduce background noise.
        bx1 = int(cw * 0.08)
        bx2 = max(bx1 + 1, int(cw * 0.92))
        by1 = int(ch * 0.02)
        by2 = max(by1 + 1, int(ch * 0.98))
        crop = crop[by1:by2, bx1:bx2]
        if crop.size == 0:
            return None

        crop = cv2.resize(crop, (96, 192), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

        stripe_hists: List[List[float]] = []
        hh = hsv.shape[0]
        for i in range(self.stripes):
            sy1 = int(i * hh / self.stripes)
            sy2 = int((i + 1) * hh / self.stripes)
            stripe = hsv[sy1:sy2, :]
            hist = self._calc_hs_hist(stripe)
            stripe_hists.append(hist.tolist())

        upper = hsv[int(hh * 0.20):int(hh * 0.68), :]
        full_hist = self._calc_hs_hist(hsv).tolist()
        upper_hist = self._calc_hs_hist(upper).tolist() if upper.size else full_hist

        # Central torso crop. This intentionally avoids most background, head and legs.
        # For the checkout camera, this is the most useful cue for red-shirt vs white-shirt.
        torso_bgr = crop[int(192 * 0.20):int(192 * 0.62), int(96 * 0.18):int(96 * 0.82)]
        if torso_bgr is None or torso_bgr.size == 0:
            torso_bgr = crop
        torso_hsv = cv2.cvtColor(torso_bgr, cv2.COLOR_BGR2HSV)
        torso_lab = cv2.cvtColor(torso_bgr, cv2.COLOR_BGR2LAB)
        torso_mean_hsv = np.mean(torso_hsv.reshape(-1, 3), axis=0).astype(np.float32)
        torso_mean_lab = np.mean(torso_lab.reshape(-1, 3), axis=0).astype(np.float32)
        torso_sat_mean = float(torso_mean_hsv[1])
        torso_val_mean = float(torso_mean_hsv[2])

        # A saturation-aware dominant hue. For white/gray/black clothes hue is unreliable,
        # so we keep saturation/value as separate cues.
        sat_mask = torso_hsv[:, :, 1] >= 45
        if np.any(sat_mask):
            hue_values = torso_hsv[:, :, 0][sat_mask]
            hist_h = cv2.calcHist([hue_values.astype(np.uint8)], [0], None, [18], [0, 180]).flatten()
            dominant_hue_bin = int(np.argmax(hist_h))
            dominant_hue = float((dominant_hue_bin + 0.5) * 10.0)
            saturated_fraction = float(np.mean(sat_mask))
        else:
            dominant_hue = -1.0
            saturated_fraction = 0.0

        aspect = float((x2 - x1) / max(1.0, (y2 - y1)))
        area_norm = float(((x2 - x1) * (y2 - y1)) / max(1.0, h * w))

        return {
            "stripe_hists": stripe_hists,
            "full_hist": full_hist,
            "upper_hist": upper_hist,
            "torso_lab_mean": torso_mean_lab.tolist(),
            "torso_hsv_mean": torso_mean_hsv.tolist(),
            "torso_sat_mean": torso_sat_mean,
            "torso_val_mean": torso_val_mean,
            "dominant_hue": dominant_hue,
            "saturated_fraction": saturated_fraction,
            "aspect": aspect,
            "area_norm": area_norm,
        }

    def compare(self, sig_a: Optional[Dict], sig_b: Optional[Dict]) -> float:
        if not sig_a or not sig_b:
            return 0.0

        stripes_a = sig_a.get("stripe_hists") or []
        stripes_b = sig_b.get("stripe_hists") or []
        stripe_score = self._compare_stripes(stripes_a, stripes_b)
        full_score = self._hist_similarity(sig_a.get("full_hist"), sig_b.get("full_hist"))
        upper_score = self._hist_similarity(sig_a.get("upper_hist"), sig_b.get("upper_hist"))
        color_score = self._torso_color_similarity(sig_a, sig_b)

        aspect_a = float(sig_a.get("aspect", 0.0) or 0.0)
        aspect_b = float(sig_b.get("aspect", 0.0) or 0.0)
        if aspect_a > 0 and aspect_b > 0:
            aspect_ratio = min(aspect_a, aspect_b) / max(aspect_a, aspect_b)
        else:
            aspect_ratio = 0.5

        # Color score is given higher weight because it is the strongest signal for
        # red-shirt-vs-white-shirt contamination. Stripe/upper still protect same clothes
        # under lighting/crop variation.
        score = 0.32 * color_score + 0.26 * stripe_score + 0.24 * upper_score + 0.12 * full_score + 0.06 * aspect_ratio
        return float(max(0.0, min(1.0, score)))

    def compare_tracklets(self, samples_a: List[Dict], samples_b: List[Dict], max_pairs: int = 80) -> Dict[str, float]:
        sigs_a = [s.get("signature") for s in (samples_a or []) if s.get("signature")]
        sigs_b = [s.get("signature") for s in (samples_b or []) if s.get("signature")]
        if not sigs_a or not sigs_b:
            return {"best": 0.0, "avg_top": 0.0, "pairs": 0, "color_best": 0.0, "color_avg_top": 0.0}

        sigs_a = self._subsample(sigs_a, int(np.sqrt(max_pairs)) + 1)
        sigs_b = self._subsample(sigs_b, int(np.sqrt(max_pairs)) + 1)

        scores: List[float] = []
        color_scores: List[float] = []
        for a in sigs_a:
            for b in sigs_b:
                scores.append(self.compare(a, b))
                color_scores.append(self._torso_color_similarity(a, b))

        if not scores:
            return {"best": 0.0, "avg_top": 0.0, "pairs": 0, "color_best": 0.0, "color_avg_top": 0.0}

        scores.sort(reverse=True)
        color_scores.sort(reverse=True)
        top_k = min(8, len(scores))
        color_top_k = min(8, len(color_scores))
        return {
            "best": float(scores[0]),
            "avg_top": float(sum(scores[:top_k]) / top_k),
            "pairs": len(scores),
            "color_best": float(color_scores[0]) if color_scores else 0.0,
            "color_avg_top": float(sum(color_scores[:color_top_k]) / color_top_k) if color_scores else 0.0,
        }

    def _subsample(self, items: List[Dict], max_items: int) -> List[Dict]:
        if len(items) <= max_items:
            return items
        indices = np.linspace(0, len(items) - 1, max_items).round().astype(int)
        return [items[int(i)] for i in indices]

    def _calc_hs_hist(self, hsv_image: np.ndarray) -> np.ndarray:
        hist = cv2.calcHist([hsv_image], [0, 1], None, self.hist_bins, self.hist_ranges)
        cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        return hist.flatten().astype(np.float32)

    def _hist_similarity(self, hist_a, hist_b) -> float:
        if hist_a is None or hist_b is None:
            return 0.0
        arr_a = np.array(hist_a, dtype=np.float32).flatten()
        arr_b = np.array(hist_b, dtype=np.float32).flatten()
        if arr_a.size == 0 or arr_b.size == 0 or arr_a.shape != arr_b.shape:
            return 0.0
        score = cv2.compareHist(arr_a, arr_b, cv2.HISTCMP_CORREL)
        return float(max(0.0, min(1.0, (score + 1.0) / 2.0)))

    def _compare_stripes(self, stripes_a: List, stripes_b: List) -> float:
        if not stripes_a or not stripes_b:
            return 0.0
        n = min(len(stripes_a), len(stripes_b))
        if n <= 0:
            return 0.0

        scores: List[float] = []
        for i in range(n):
            local = []
            for j in (i - 1, i, i + 1):
                if 0 <= j < len(stripes_b):
                    local.append(self._hist_similarity(stripes_a[i], stripes_b[j]))
            if local:
                scores.append(max(local))
        if not scores:
            return 0.0
        return float(sum(scores) / len(scores))

    def _torso_color_similarity(self, sig_a: Optional[Dict], sig_b: Optional[Dict]) -> float:
        if not sig_a or not sig_b:
            return 0.0

        lab_a = np.array(sig_a.get("torso_lab_mean") or [], dtype=np.float32).flatten()
        lab_b = np.array(sig_b.get("torso_lab_mean") or [], dtype=np.float32).flatten()
        if lab_a.size != 3 or lab_b.size != 3:
            return 0.5

        # LAB distance normalized. Red vs white usually has a large a/b distance.
        lab_dist = float(np.linalg.norm(lab_a - lab_b))
        lab_sim = max(0.0, min(1.0, 1.0 - lab_dist / 115.0))

        sat_a = float(sig_a.get("torso_sat_mean", 0.0) or 0.0) / 255.0
        sat_b = float(sig_b.get("torso_sat_mean", 0.0) or 0.0) / 255.0
        val_a = float(sig_a.get("torso_val_mean", 0.0) or 0.0) / 255.0
        val_b = float(sig_b.get("torso_val_mean", 0.0) or 0.0) / 255.0
        sat_sim = max(0.0, 1.0 - abs(sat_a - sat_b) / 0.65)
        val_sim = max(0.0, 1.0 - abs(val_a - val_b) / 0.75)

        hue_a = float(sig_a.get("dominant_hue", -1.0) or -1.0)
        hue_b = float(sig_b.get("dominant_hue", -1.0) or -1.0)
        frac_a = float(sig_a.get("saturated_fraction", 0.0) or 0.0)
        frac_b = float(sig_b.get("saturated_fraction", 0.0) or 0.0)
        if hue_a >= 0 and hue_b >= 0 and frac_a >= 0.08 and frac_b >= 0.08:
            dh = abs(hue_a - hue_b)
            dh = min(dh, 180.0 - dh)
            hue_sim = max(0.0, 1.0 - dh / 70.0)
        else:
            # Hue is not meaningful for white/gray/black clothes.
            hue_sim = 0.5

        return float(max(0.0, min(1.0, 0.48 * lab_sim + 0.25 * sat_sim + 0.17 * val_sim + 0.10 * hue_sim)))
