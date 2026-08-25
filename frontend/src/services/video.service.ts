import type { VideoFileMeta } from "@/types/video.type";
import { VIDEO_CONSTRAINTS } from "@/types/video.type";

// ─── Validate file ────────────────────────────────────────────────────────────
export function validateVideoFile(file: File): string | null {
  if (file.size > VIDEO_CONSTRAINTS.maxSizeBytes) {
    return `File quá lớn. Giới hạn ${VIDEO_CONSTRAINTS.maxSizeMB}MB, file của bạn ${(file.size / 1024 / 1024).toFixed(1)}MB`;
  }

  if (!VIDEO_CONSTRAINTS.acceptedFormats.includes(file.type as never)) {
    const ext = file.name.split(".").pop()?.toLowerCase();
    const validExt = VIDEO_CONSTRAINTS.acceptedExtensions.join(", ");
    return `Định dạng "${ext}" không được hỗ trợ. Vui lòng dùng: ${validExt}`;
  }

  return null;
}

// ─── Extract video metadata + thumbnail ──────────────────────────────────────
export async function extractVideoMeta(file: File): Promise<VideoFileMeta> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.muted = true;
    video.src = url;

    video.onloadedmetadata = () => {
      video.currentTime = Math.min(2, video.duration * 0.1);
    };

    video.onseeked = () => {
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 360;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      }
      const thumbnailUrl = canvas.toDataURL("image/jpeg", 0.8);
      URL.revokeObjectURL(url);

      resolve({
        name: file.name,
        size: file.size,
        type: file.type,
        duration: video.duration,
        thumbnailUrl,
        width: video.videoWidth || 640,
        height: video.videoHeight || 360,
        _file: file,
      });
    };

    video.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Không thể đọc file video"));
    };
  });
}

// ─── Format helpers ───────────────────────────────────────────────────────────
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDurationVideo(seconds: number): string {
  if (isNaN(seconds) || !isFinite(seconds)) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0)
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
