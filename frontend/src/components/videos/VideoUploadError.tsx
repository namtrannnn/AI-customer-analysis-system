"use client";

import { FileVideo, Ban, UserX, Upload, Monitor, RefreshCw } from "lucide-react";
import type { VideoError } from "@/types/video.type";

interface VideoUploadErrorProps {
  error: VideoError;
  onRetry: () => void;
}

const errorConfig = {
  file_too_large: {
    icon: <FileVideo className="h-7 w-7" />,
    color: "text-orange-500",
    bg: "bg-orange-50 dark:bg-orange-900/20",
    ring: "ring-orange-200 dark:ring-orange-800/40",
    title: "File quá lớn",
  },
  invalid_format: {
    icon: <Ban className="h-7 w-7" />,
    color: "text-red-500",
    bg: "bg-red-50 dark:bg-red-900/20",
    ring: "ring-red-200 dark:ring-red-800/40",
    title: "Định dạng không hợp lệ",
  },
  no_person_found: {
    icon: <UserX className="h-7 w-7" />,
    color: "text-yellow-600",
    bg: "bg-yellow-50 dark:bg-yellow-900/20",
    ring: "ring-yellow-200 dark:ring-yellow-800/40",
    title: "Không tìm thấy người",
  },
  upload_failed: {
    icon: <Upload className="h-7 w-7" />,
    color: "text-red-500",
    bg: "bg-red-50 dark:bg-red-900/20",
    ring: "ring-red-200 dark:ring-red-800/40",
    title: "Upload thất bại",
  },
  analysis_failed: {
    icon: <Monitor className="h-7 w-7" />,
    color: "text-purple-500",
    bg: "bg-purple-50 dark:bg-purple-900/20",
    ring: "ring-purple-200 dark:ring-purple-800/40",
    title: "Phân tích thất bại",
  },
};

export default function VideoUploadError({ error, onRetry }: VideoUploadErrorProps) {
  const cfg = errorConfig[error.type];

  return (
    <div className={`flex flex-col items-center gap-4 rounded-2xl p-8 text-center ring-1 ${cfg.bg} ${cfg.ring}`}>
      {/* Icon */}
      <div className={`flex h-16 w-16 items-center justify-center rounded-2xl bg-white shadow-sm ring-1 dark:bg-slate-800 ${cfg.ring} ${cfg.color}`}>
        {cfg.icon}
      </div>

      {/* Text */}
      <div>
        <h3 className={`text-base font-bold ${cfg.color}`}>{cfg.title}</h3>
        <p className="mt-1.5 max-w-sm text-sm text-slate-600 dark:text-slate-400">
          {error.message}
        </p>
      </div>

      {/* Suggestions per error type */}
      {error.type === "file_too_large" && (
        <div className="rounded-xl bg-white/60 px-4 py-3 text-left text-xs text-slate-600 dark:bg-slate-800/60 dark:text-slate-400">
          <p className="mb-1 font-semibold">Gợi ý:</p>
          <ul className="list-inside list-disc space-y-0.5">
            <li>Nén video trước khi upload</li>
            <li>Cắt bớt đoạn video không cần thiết</li>
            <li>Giảm độ phân giải xuống 1080p hoặc thấp hơn</li>
          </ul>
        </div>
      )}

      {error.type === "invalid_format" && (
        <div className="rounded-xl bg-white/60 px-4 py-3 text-left text-xs text-slate-600 dark:bg-slate-800/60 dark:text-slate-400">
          <p className="mb-1 font-semibold">Định dạng hỗ trợ:</p>
          <p className="font-mono">.mp4 · .avi · .mov · .mkv</p>
        </div>
      )}

      {error.type === "no_person_found" && (
        <div className="rounded-xl bg-white/60 px-4 py-3 text-left text-xs text-slate-600 dark:bg-slate-800/60 dark:text-slate-400">
          <p className="mb-1 font-semibold">Gợi ý:</p>
          <ul className="list-inside list-disc space-y-0.5">
            <li>Video cần có ít nhất 3 giây</li>
            <li>Đảm bảo người xuất hiện rõ ràng trong frame</li>
            <li>Kiểm tra chất lượng ánh sáng video</li>
          </ul>
        </div>
      )}

      {/* Retry button */}
      <button
        onClick={onRetry}
        className="flex items-center gap-2 rounded-xl bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm ring-1 ring-slate-200 transition hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700 dark:hover:bg-slate-700"
      >
        <RefreshCw className="h-4 w-4" />
        Thử lại
      </button>
    </div>
  );
}
