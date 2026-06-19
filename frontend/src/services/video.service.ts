/**
 * Video Service — Mock implementation
 * Khi có backend thật: xóa mock, uncomment các dòng http.*
 */

import { delay } from "./api";
import { generateMockAnalysisResult } from "@/mocks/videos.mock";
import type { VideoAnalysisResult, VideoFileMeta } from "@/types/video.type";
import { VIDEO_CONSTRAINTS } from "@/types/video.type";

// ─── Validate file trước khi upload ──────────────────────────────────────────
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

// ─── Extract video metadata (duration, thumbnail, dimensions) ────────────────
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
      // Capture thumbnail từ frame hiện tại
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

// ─── Upload video ─────────────────────────────────────────────────────────────
export async function uploadVideo(
  file: File,
  onProgress?: (percent: number) => void
): Promise<{ video_id: number; upload_url: string }> {
  // Mock: simulate upload progress
  const steps = [10, 25, 45, 65, 80, 95, 100];
  for (const step of steps) {
    await delay(200 + Math.random() * 300);
    onProgress?.(step);
  }

  return {
    video_id: Math.floor(Math.random() * 10000),
    upload_url: `mock://videos/${file.name}`,
  };

  // ── Khi có backend ──
  // const form = new FormData();
  // form.append("file", file);
  // const res = await fetch(`${BASE_URL}/videos/upload`, {
  //   method: "POST",
  //   headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
  //   body: form,
  // });
  // const json = await res.json();
  // return json.data;
}

// ─── Trigger phân tích video ──────────────────────────────────────────────────
export async function analyzeVideo(
  videoId: number,
  fileMeta: VideoFileMeta
): Promise<VideoAnalysisResult> {
  // Mock: simulate AI processing time (tỷ lệ với duration)
  const processingTime = Math.min(fileMeta.duration * 200, 4000);
  await delay(processingTime);

  const result = generateMockAnalysisResult(fileMeta.name, fileMeta.duration);

  // Giả lập "no person found" nếu video quá ngắn
  if (fileMeta.duration < 3) {
    throw new Error("NO_PERSON_FOUND");
  }

  return result;

  // ── Khi có backend ──
  // return http.post<VideoAnalysisResult>(`/videos/${videoId}/analyze`, {});
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
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
