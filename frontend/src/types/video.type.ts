// ─── Upload state ─────────────────────────────────────────────────────────────
export type UploadStatus =
  | "idle"
  | "validating"
  | "ready"
  | "uploading"
  | "analyzing"
  | "done"
  | "error";

export type VideoErrorType =
  | "file_too_large"
  | "invalid_format"
  | "no_person_found"
  | "upload_failed"
  | "analysis_failed";

export interface VideoError {
  type: VideoErrorType;
  message: string;
}

// ─── File metadata ────────────────────────────────────────────────────────────
export interface VideoFileMeta {
  name: string;
  size: number;           // bytes
  type: string;           // MIME
  duration: number;       // seconds
  thumbnailUrl: string;   // object URL từ canvas
  width: number;
  height: number;
  _file: File;            // giữ reference để VideoPreview phát được
}

// ─── Analysis result ──────────────────────────────────────────────────────────
export type PersonType = "identified" | "anonymous";

export interface DetectedPerson {
  id: number;
  anonymous_id: string;         // e.g. "ANON-00001"
  person_type: PersonType;
  confidence: number;           // 0–1
  first_detected_at: string;    // timestamp in video (mm:ss)
  appearances: number;          // số lần xuất hiện
  zone: string | null;          // khu vực phát hiện
  thumbnail_url: string | null; // ảnh khuôn mặt crop
}

export interface VideoAnalysisStats {
  total_customers: number;
  new_customers: number;
  returning_customers: number;
  identified_customers: number;
  avg_confidence: number;
  processing_time_ms: number;
}

export interface VideoAnalysisResult {
  video_id: number;
  video_name: string;
  duration: number;
  processed_at: string;
  stats: VideoAnalysisStats;
  detected_persons: DetectedPerson[];
}

// ─── Upload constraints ───────────────────────────────────────────────────────
export const VIDEO_CONSTRAINTS = {
  maxSizeMB: 50,
  maxSizeBytes: 50 * 1024 * 1024,
  acceptedFormats: ["video/mp4", "video/avi", "video/quicktime", "video/x-matroska", "video/x-msvideo"],
  acceptedExtensions: [".mp4", ".avi", ".mov", ".mkv"],
} as const;
