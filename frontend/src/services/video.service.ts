import { generateMockAnalysisResult } from "@/mocks/videos.mock";
import type { VideoAnalysisResult, VideoFileMeta } from "@/types/video.type";
import { VIDEO_CONSTRAINTS } from "@/types/video.type";
import { http } from "@/lib/http";

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
      if (ctx) ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
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

// ─── Upload + Analyze (1 bước — khớp BE API) ─────────────────────────────────
export async function uploadAndAnalyzeVideo(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<VideoAnalysisResult> {
  // Simulate progress tăng dần trong khi chờ server
  let currentProgress = 0;
  const progressInterval = setInterval(() => {
    currentProgress = Math.min(currentProgress + 5, 90);
    onProgress?.(currentProgress);
  }, 300);

  try {
    const form = new FormData();
    form.append("file", file);

    // Dùng http.raw để axios tự set Content-Type multipart/form-data với boundary
    const res = await http.raw.post<{
      status: string;
      data: {
        total_customers: number;
        new_customers: number;
        returning_customers: number;
        detected_customers: Array<{
          anonymous_id: string;
          customer_type: string;
          confidence: number;
          customer_id?: number | null;
          customer_name?: string | null;
          customer_avatar?: string | null;
        }>;
        message: string;
      };
    }>("/videos/upload/", form, {
      timeout: 10 * 60 * 1000, // 10 phút — video dài cần nhiều thời gian xử lý
    });

    clearInterval(progressInterval);
    onProgress?.(100);

    const data = res.data.data;

    // Map BE schema → FE VideoAnalysisResult
    const avgConf =
      data.detected_customers.length > 0
        ? data.detected_customers.reduce((s, c) => s + c.confidence, 0) /
          data.detected_customers.length
        : 0;

    const result: VideoAnalysisResult = {
      video_id: Date.now(),
      video_name: file.name,
      duration: 0,
      processed_at: new Date().toISOString(),
      stats: {
        total_customers: data.total_customers,
        new_customers: data.new_customers,
        returning_customers: data.returning_customers,
        identified_customers: data.detected_customers.filter(
          (c) => c.customer_type === "returning",
        ).length,
        avg_confidence: parseFloat(avgConf.toFixed(3)),
        processing_time_ms: 0,
      },
      detected_persons: data.detected_customers.map((c, i) => ({
        id: i + 1,
        anonymous_id: c.anonymous_id,
        person_type:
          c.customer_type === "returning" ? "identified" : "anonymous",
        confidence: c.confidence,
        first_detected_at: "—",
        appearances: 1,
        zone: null,
        thumbnail_url:
          c.customer_avatar ||
          `https://api.dicebear.com/7.x/personas/svg?seed=${c.anonymous_id}`,
        customer_id: c.customer_id,
        customer_name: c.customer_name,
      })),
    };

    return result;
  } catch (e) {
    clearInterval(progressInterval);
    // Axios interceptor đã format message — map sang error type
    const msg = e instanceof Error ? e.message : "Có lỗi xảy ra";
    if (msg.includes("50MB") || msg.includes("quá lớn"))
      throw new Error("FILE_TOO_LARGE");
    if (msg.includes("định dạng") || msg.includes("video/"))
      throw new Error("INVALID_FORMAT");
    throw e;
  }
}

// ─── Mock (dùng khi chưa có backend) ─────────────────────────────────────────
// export async function uploadAndAnalyzeMock(
//   fileMeta: VideoFileMeta,
//   onProgress?: (percent: number) => void,
// ): Promise<VideoAnalysisResult> {
//   const steps = [10, 25, 45, 65, 80, 95, 100];
//   for (const step of steps) {
//     await delay(200 + Math.random() * 300);
//     onProgress?.(step);
//   }

//   if (fileMeta.duration < 3) throw new Error("NO_PERSON_FOUND");

//   return generateMockAnalysisResult(fileMeta.name, fileMeta.duration);
// }

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
