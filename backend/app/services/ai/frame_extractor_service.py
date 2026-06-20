import cv2
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class ExtractedFrame:
    frame_index: int
    timestamp_seconds: float
    image_path: str
    width: int
    height: int


@dataclass
class FrameExtractionResult:
    video_path: str
    output_dir: str
    total_frames: int
    video_fps: float
    duration_seconds: float
    extracted_count: int
    frames: List[ExtractedFrame]


class FrameExtractorService:
    """
    AI-01 Frame Extractor Service

    Service này chỉ chịu trách nhiệm:
    - Đọc video từ local temp path.
    - Trích frame theo target_fps hoặc frame_interval.
    - Lưu frame vào temp directory.
    - Trả danh sách frame cho pipeline xử lý tiếp.
    """

    def extract_frames(
        self,
        video_path: str,
        output_dir: str,
        frame_interval: Optional[int] = None,
        target_fps: Optional[float] = 1.0,
        max_frames: Optional[int] = None,
        image_extension: str = "jpg",
        jpeg_quality: int = 90,
    ) -> FrameExtractionResult:
        video_file = Path(video_path)
        output_path = Path(output_dir)

        if not video_file.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if not video_file.is_file():
            raise ValueError(f"Invalid video path: {video_path}")

        if max_frames is not None and max_frames < 0:
            raise ValueError("max_frames must be greater than or equal to 0")

        self._validate_image_options(
            image_extension=image_extension,
            jpeg_quality=jpeg_quality,
        )

        output_path.mkdir(parents=True, exist_ok=True)

        capture = cv2.VideoCapture(str(video_file))

        if not capture.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        try:
            video_fps = capture.get(cv2.CAP_PROP_FPS)
            total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

            if video_fps <= 0:
                video_fps = 25.0

            duration_seconds = total_frames / video_fps if total_frames > 0 else 0

            effective_interval = self._resolve_frame_interval(
                video_fps=video_fps,
                frame_interval=frame_interval,
                target_fps=target_fps,
            )

            if max_frames == 0:
                return FrameExtractionResult(
                    video_path=str(video_file),
                    output_dir=str(output_path),
                    total_frames=total_frames,
                    video_fps=round(video_fps, 3),
                    duration_seconds=round(duration_seconds, 3),
                    extracted_count=0,
                    frames=[],
                )

            extracted_frames: List[ExtractedFrame] = []
            current_frame_index = 0

            while True:
                success, frame = capture.read()

                if not success:
                    break

                if current_frame_index % effective_interval == 0:
                    height, width = frame.shape[:2]
                    timestamp_seconds = current_frame_index / video_fps

                    image_filename = (
                        f"frame_{current_frame_index:06d}_"
                        f"{timestamp_seconds:.2f}s.{image_extension}"
                    )

                    image_path = output_path / image_filename

                    self._save_frame(
                        image_path=image_path,
                        frame=frame,
                        image_extension=image_extension,
                        jpeg_quality=jpeg_quality,
                    )

                    extracted_frames.append(
                        ExtractedFrame(
                            frame_index=current_frame_index,
                            timestamp_seconds=round(timestamp_seconds, 3),
                            image_path=str(image_path),
                            width=width,
                            height=height,
                        )
                    )

                    if max_frames is not None and len(extracted_frames) >= max_frames:
                        break

                current_frame_index += 1

            return FrameExtractionResult(
                video_path=str(video_file),
                output_dir=str(output_path),
                total_frames=total_frames,
                video_fps=round(video_fps, 3),
                duration_seconds=round(duration_seconds, 3),
                extracted_count=len(extracted_frames),
                frames=extracted_frames,
            )

        finally:
            capture.release()

    def create_temp_frame_dir(self) -> tempfile.TemporaryDirectory:
        """
        Tạo temp directory cho frames.

        Khuyến nghị:
        - Dùng hàm này ở router hoặc video_pipeline_service.
        - Giữ context sống trong suốt quá trình AI pipeline chạy.
        """

        return tempfile.TemporaryDirectory(prefix="frames_")

    def _resolve_frame_interval(
        self,
        video_fps: float,
        frame_interval: Optional[int],
        target_fps: Optional[float],
    ) -> int:
        if frame_interval is not None:
            if frame_interval <= 0:
                raise ValueError("frame_interval must be greater than 0")
            return frame_interval

        if target_fps is None:
            target_fps = 1.0

        if target_fps <= 0:
            raise ValueError("target_fps must be greater than 0")

        interval = int(math.ceil(video_fps / target_fps))

        return max(interval, 1)

    def _validate_image_options(
        self,
        image_extension: str,
        jpeg_quality: int,
    ) -> None:
        normalized_extension = image_extension.lower().replace(".", "")

        if normalized_extension not in ["jpg", "jpeg", "png"]:
            raise ValueError("Unsupported image extension. Use jpg, jpeg, or png.")

        if normalized_extension in ["jpg", "jpeg"] and not 1 <= jpeg_quality <= 100:
            raise ValueError("jpeg_quality must be between 1 and 100")

    def _save_frame(
        self,
        image_path: Path,
        frame,
        image_extension: str,
        jpeg_quality: int,
    ) -> None:
        image_extension = image_extension.lower().replace(".", "")

        if image_extension in ["jpg", "jpeg"]:
            saved = cv2.imwrite(
                str(image_path),
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality],
            )
        elif image_extension == "png":
            saved = cv2.imwrite(str(image_path), frame)
        else:
            raise ValueError("Unsupported image extension. Use jpg, jpeg, or png.")

        if not saved:
            raise ValueError(f"Failed to save frame: {image_path}")
