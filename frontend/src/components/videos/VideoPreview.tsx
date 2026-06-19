"use client";

import { useRef, useState, useEffect } from "react";
import type { VideoFileMeta } from "@/types/video.type";
import { formatFileSize, formatDurationVideo } from "@/services/video.service";

interface VideoPreviewProps {
  meta: VideoFileMeta;
  file: File;
  onRemove: () => void;
  disabled?: boolean;
}

export default function VideoPreview({ meta, file, onRemove, disabled }: VideoPreviewProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [objectUrl, setObjectUrl] = useState<string>("");

  // Tạo object URL từ file thật
  useEffect(() => {
    const url = URL.createObjectURL(file);
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function togglePlay() {
    const v = videoRef.current;
    if (!v) return;
    if (playing) {
      v.pause();
    } else {
      v.play();
    }
    setPlaying(!playing);
  }

  function handleTimeUpdate() {
    setCurrentTime(videoRef.current?.currentTime ?? 0);
  }

  function handleEnded() {
    setPlaying(false);
    setCurrentTime(0);
    if (videoRef.current) videoRef.current.currentTime = 0;
  }

  function handleSeek(e: React.ChangeEvent<HTMLInputElement>) {
    const t = parseFloat(e.target.value);
    if (videoRef.current) videoRef.current.currentTime = t;
    setCurrentTime(t);
  }

  const progress = meta.duration > 0 ? (currentTime / meta.duration) * 100 : 0;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
      {/* ── Video player ── */}
      <div className="relative aspect-video w-full overflow-hidden bg-black">
        {objectUrl && (
          <video
            ref={videoRef}
            src={objectUrl}
            className="h-full w-full object-contain"
            onTimeUpdate={handleTimeUpdate}
            onEnded={handleEnded}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            playsInline
            preload="metadata"
          />
        )}

        {/* Overlay controls — chỉ hiện khi không play */}
        {!playing && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/30">
            <button
              onClick={togglePlay}
              className="flex h-16 w-16 items-center justify-center rounded-full bg-white/20 backdrop-blur-sm ring-2 ring-white/40 transition hover:scale-105 hover:bg-white/30 active:scale-95"
              aria-label="Phát video"
            >
              <svg className="ml-1 h-7 w-7 text-white drop-shadow" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7z" />
              </svg>
            </button>
          </div>
        )}

        {/* Pause button khi đang play */}
        {playing && (
          <button
            onClick={togglePlay}
            className="absolute inset-0 flex items-center justify-center opacity-0 transition hover:opacity-100"
            aria-label="Tạm dừng"
          >
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-black/40 backdrop-blur-sm">
              <svg className="h-6 w-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
              </svg>
            </div>
          </button>
        )}

        {/* Duration badge */}
        <div className="absolute bottom-3 right-3 flex items-center gap-1.5 rounded-lg bg-black/70 px-2.5 py-1 backdrop-blur-sm">
          <svg className="h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <circle cx="12" cy="12" r="10" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6l4 2" />
          </svg>
          <span className="text-xs font-semibold text-white">
            {formatDurationVideo(meta.duration)}
          </span>
        </div>
      </div>

      {/* ── Seekbar ── */}
      <div className="px-4 pt-3">
        <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
          <div
            className="absolute left-0 top-0 h-full rounded-full bg-gradient-to-r from-violet-500 to-purple-500 transition-all"
            style={{ width: `${progress}%` }}
          />
          <input
            type="range"
            min={0}
            max={meta.duration || 100}
            step={0.1}
            value={currentTime}
            onChange={handleSeek}
            className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
            aria-label="Seek video"
          />
        </div>
        <div className="mt-1 flex justify-between text-[10px] text-slate-400 dark:text-slate-500">
          <span>{formatDurationVideo(currentTime)}</span>
          <span>{formatDurationVideo(meta.duration)}</span>
        </div>
      </div>

      {/* ── File info ── */}
      <div className="px-4 pb-4 pt-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
              {meta.name}
            </p>
            <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
              <MetaItem icon="📦" label={formatFileSize(meta.size)} />
              <MetaItem icon="🖥" label={`${meta.width}×${meta.height}`} />
              <MetaItem icon="⏱" label={formatDurationVideo(meta.duration)} />
            </div>
          </div>

          {!disabled && (
            <button
              onClick={onRemove}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-400 transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-900/20 dark:hover:text-red-400"
              title="Xóa file"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          )}
        </div>

        <div className="mt-2.5 flex items-center gap-2">
          <span className="rounded-md bg-violet-100 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-violet-700 dark:bg-violet-900/30 dark:text-violet-400">
            {meta.name.split(".").pop()}
          </span>
          <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
            ✓ Sẵn sàng để phân tích
          </span>
        </div>
      </div>
    </div>
  );
}

function MetaItem({ icon, label }: { icon: string; label: string }) {
  return (
    <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
      <span>{icon}</span>
      {label}
    </div>
  );
}
