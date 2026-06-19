"use client";

import type { VideoError } from "@/types/video.type";

interface VideoUploadErrorProps {
  error: VideoError;
  onRetry: () => void;
}

const errorConfig = {
  file_too_large: {
    icon: (
      <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 11v4m0 4h.01" />
      </svg>
    ),
    color: "text-orange-500",
    bg: "bg-orange-50 dark:bg-orange-900/20",
    ring: "ring-orange-200 dark:ring-orange-800/40",
    title: "File quá lớn",
  },
  invalid_format: {
    icon: (
      <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
      </svg>
    ),
    color: "text-red-500",
    bg: "bg-red-50 dark:bg-red-900/20",
    ring: "ring-red-200 dark:ring-red-800/40",
    title: "Định dạng không hợp lệ",
  },
  no_person_found: {
    icon: (
      <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m9-4a4 4 0 11-8 0 4 4 0 018 0zm-5 9v-1" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M17 8l4-4m0 4l-4-4" />
      </svg>
    ),
    color: "text-yellow-600",
    bg: "bg-yellow-50 dark:bg-yellow-900/20",
    ring: "ring-yellow-200 dark:ring-yellow-800/40",
    title: "Không tìm thấy người",
  },
  upload_failed: {
    icon: (
      <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
      </svg>
    ),
    color: "text-red-500",
    bg: "bg-red-50 dark:bg-red-900/20",
    ring: "ring-red-200 dark:ring-red-800/40",
    title: "Upload thất bại",
  },
  analysis_failed: {
    icon: (
      <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
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
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Thử lại
      </button>
    </div>
  );
}
