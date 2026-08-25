/**
 * Component hiển thị tiến độ và tốc độ phân tích thời gian thực (StreamingProgress)
 * Hiển thị các chỉ số chi tiết: Số frame, FPS tốc độ xử lý, thời gian còn lại dự kiến (ETA)
 */

"use client";

// Đã xóa import Percent vì không cần thiết nữa
import { Activity, Clock, Cpu } from "lucide-react";
import type { StreamProgressPayload } from "@/services/video_stream.service";

interface StreamingProgressProps {
  progress: StreamProgressPayload;
}

export default function StreamingProgress({ progress }: StreamingProgressProps) {
  const { current_frame, total_frames, fps, progress_percent } = progress;

  // Tính toán thời gian xử lý còn lại dự kiến (ETA)
  const remainingFrames = total_frames - current_frame;
  const etaSeconds = fps > 0 ? Math.ceil(remainingFrames / fps) : 0;

  const formatEta = (seconds: number) => {
    if (seconds <= 0) return "Hoàn thành";
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m > 0 ? `${m} phút ${s} giây` : `${s} giây`;
  };

  return (
    <div className="space-y-4 rounded-2xl border border-slate-100 bg-slate-50/50 p-5 dark:border-slate-800 dark:bg-slate-900/30">
      {/* Tiến trình % và thanh trượt */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs font-bold text-slate-500 uppercase tracking-wider dark:text-slate-400">
            Tiến trình phân tích
          </span>
          {/* Đã xóa icon <Percent /> ở đây */}
          <span className="text-base font-extrabold text-indigo-600 dark:text-indigo-400 flex items-center">
            {progress_percent}%
          </span>
        </div>

        <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200/60 dark:bg-slate-800">
          <div
            className="h-full rounded-full bg-gradient-to-r from-indigo-500 via-purple-500 to-violet-500 transition-all duration-300 ease-out"
            style={{ width: `${progress_percent}%` }}
          />
        </div>
      </div>

      {/* Grid thông số thống kê chi tiết */}
      <div className="grid grid-cols-3 gap-3">
        {/* Số Frame */}
        <div className="flex items-center gap-3 p-3 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700/50">
          <div className="h-8 w-8 shrink-0 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 flex items-center justify-center">
            <Cpu className="h-4.5 w-4.5 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-bold text-slate-450 dark:text-slate-500 uppercase tracking-wide">Khung hình</p>
            <p className="text-xs font-extrabold text-slate-800 dark:text-slate-200 mt-0.5">
              {current_frame} / {total_frames}
            </p>
          </div>
        </div>

        {/* FPS */}
        <div className="flex items-center gap-3 p-3 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700/50">
          <div className="h-8 w-8 shrink-0 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 flex items-center justify-center">
            <Activity className="h-4.5 w-4.5 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-bold text-slate-450 dark:text-slate-500 uppercase tracking-wide">Tốc độ (FPS)</p>
            <p className="text-xs font-extrabold text-slate-800 dark:text-slate-200 mt-0.5">
              {fps.toFixed(1)} frames/s
            </p>
          </div>
        </div>

        {/* ETA */}
        <div className="flex items-center gap-3 p-3 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700/50">
          <div className="h-8 w-8 shrink-0 rounded-lg bg-amber-50 dark:bg-amber-950/40 flex items-center justify-center">
            <Clock className="h-4.5 w-4.5 text-amber-600 dark:text-amber-400" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-bold text-slate-450 dark:text-slate-500 uppercase tracking-wide">Thời gian còn lại</p>
            <p className="text-xs font-extrabold text-slate-800 dark:text-slate-200 mt-0.5 truncate" title={formatEta(etaSeconds)}>
              {formatEta(etaSeconds)}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}