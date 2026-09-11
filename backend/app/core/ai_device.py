"""
Cấu hình thiết bị AI (GPU/CUDA) dùng chung cho pipeline.

Mặc định `AI_DEVICE=auto`: dùng GPU CUDA nếu torch nhận diện được,
ngược lại tự fallback về CPU để không crash trên máy không có GPU
(CI, Docker, máy dev khác).

Có thể force qua biến môi trường:
    AI_DEVICE=cpu   -> ép CPU
    AI_DEVICE=cuda  -> ép GPU (lỗi nếu không có CUDA)
    AI_DEVICE=cuda:0 -> ép GPU cụ thể
"""

import os
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def _torch_module():
    try:
        import torch

        return torch
    except ImportError:
        return None


class DeviceManager:
    def __init__(self) -> None:
        self._info = self._build_info()

    def _build_info(self) -> dict[str, Any]:
        raw = (os.getenv("AI_DEVICE") or "auto").strip().lower()
        torch = _torch_module()

        info: dict[str, Any] = {
            "requested_device": raw,
            "selected_device": "cpu",
            "mode": "cpu",
            "cuda_available": False,
            "gpu_name": None,
            "fallback_reason": None,
            "torch_available": torch is not None,
        }

        if raw in ("", "auto"):
            if torch is None:
                info["fallback_reason"] = "torch_not_installed"
                return info

            if torch.cuda.is_available():
                info["selected_device"] = "cuda:0"
                info["mode"] = "cuda"
                info["cuda_available"] = True
                info["gpu_name"] = torch.cuda.get_device_name(0)
                return info

            info["fallback_reason"] = "cuda_unavailable"
            return info

        if raw == "cpu":
            return info

        if raw.startswith("cuda") or raw.isdigit():
            device = f"cuda:{int(raw)}" if raw.isdigit() else raw
            if torch is None:
                info["fallback_reason"] = "torch_not_installed"
                return info

            if not torch.cuda.is_available():
                info["fallback_reason"] = "cuda_unavailable"
                return info

            index = int(device.split(":", 1)[1]) if ":" in device else 0
            info["selected_device"] = device
            info["mode"] = "cuda"
            info["cuda_available"] = True
            info["gpu_name"] = torch.cuda.get_device_name(index)
            return info

        info["fallback_reason"] = "invalid_ai_device"
        return info

    @property
    def info(self) -> dict[str, Any]:
        return self._info

    @property
    def selected_device(self) -> str:
        return str(self._info["selected_device"])

    @property
    def is_cuda(self) -> bool:
        return self._info["mode"] == "cuda"

    @property
    def cuda_available(self) -> bool:
        return bool(self._info["cuda_available"])

    def get_info(self) -> dict[str, Any]:
        return dict(self._info)

    def resolve_device(self) -> str:
        return self.selected_device

    def log_status(self) -> None:
        if self._info["mode"] == "cuda":
            print(
                f"[AI-DEVICE] Dùng GPU {self._info['selected_device']}"
                + (f" ({self._info['gpu_name']})" if self._info.get("gpu_name") else "")
            )
            return

        reason = self._info.get("fallback_reason")
        if reason == "torch_not_installed":
            print("[AI-DEVICE] Chưa cài torch -> dùng CPU cho pipeline AI.")
        elif reason == "cuda_unavailable":
            print(
                "[AI-DEVICE] torch không thấy CUDA (có thể đang dùng bản CPU) -> dùng CPU. "
                "Cài bản GPU: pip install torch --index-url https://download.pytorch.org/whl/cu126"
            )
        elif reason == "invalid_ai_device":
            print(f"[AI-DEVICE] Giá trị AI_DEVICE='{self._info['requested_device']}' không hợp lệ -> dùng CPU.")
        else:
            print("[AI-DEVICE] Dùng CPU cho pipeline AI.")


_DEVICE_MANAGER = DeviceManager()


def get_device_manager() -> DeviceManager:
    return _DEVICE_MANAGER


def get_ai_device_info() -> dict[str, Any]:
    return _DEVICE_MANAGER.get_info()


def resolve_ai_device() -> str:
    return _DEVICE_MANAGER.resolve_device()


def log_ai_device_status() -> None:
    _DEVICE_MANAGER.log_status()
