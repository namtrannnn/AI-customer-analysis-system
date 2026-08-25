"use client";

import { useRef, useState, useEffect } from "react";
import { Play, Pause, Clock, Trash2 } from "lucide-react";
import type { VideoFileMeta } from "@/types/video.type";
import { formatFileSize, formatDurationVideo } from "@/services/video.service";

interface VideoPreviewProps {
  meta: VideoFileMeta;
  file: File;
  onRemove: () => void;
  disabled?: boolean;
  analysisMode?: boolean;
  analysisReady?: boolean;
  analysisProgress?: number;
  autoPlayWhenReady?: boolean;
  playbackRate?: number;
}

export default function VideoPreview({
  meta,
  file,
  onRemove,
  disabled,
  analysisMode = false,
  analysisReady = true,
  analysisProgress = 0,
  autoPlayWhenReady = true,
  playbackRate = 0.8,
}: VideoPreviewProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [objectUrl, setObjectUrl] = useState<string>("");

  const canPlay = !analysisMode || analysisReady;

  // Tạo object URL từ file thật
  useEffect(() => {
    const url = URL.createObjectURL(file);
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    video.playbackRate = playbackRate;
    if (analysisMode && !analysisReady) {
      video.pause();
      video.currentTime = 0;
      setPlaying(false);
      setCurrentTime(0);
      return;
    }

    if (analysisMode && analysisReady && autoPlayWhenReady) {
      void video.play().catch(() => {
        // Trình duyệt có thể chặn autoplay; người dùng vẫn có thể nhấn Play.
      });
    }
  }, [analysisMode, analysisReady, autoPlayWhenReady, playbackRate]);

  function togglePlay() {
    const v = videoRef.current;
    if (!v || !canPlay) return;
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
    if (!canPlay) return;
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
            preload="auto"
            controls={false}
          />
        )}

        {analysisMode && !analysisReady && (
          <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/70 px-6 text-center text-white backdrop-blur-sm">
            <div className="mb-3 h-9 w-9 animate-spin rounded-full border-4 border-white/30 border-t-white" />
            <p className="text-sm font-bold">Đang chờ quét video...</p>
            <p className="mt-1 text-xs text-white/75">
              Khách hàng sẽ xuất hiện ngay khi AI nhận dạng
            </p>
            <p className="mt-3 text-[11px] font-semibold text-white/70">
              Đã chuẩn bị{" "}
              {Math.max(0, Math.min(100, Math.round(analysisProgress)))}%
            </p>
          </div>
        )}

        {/* Overlay controls — chỉ hiện khi không play */}
        {!playing && canPlay && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/30">
            <button
              onClick={togglePlay}
              className="flex h-16 w-16 items-center justify-center rounded-full bg-white/20 backdrop-blur-sm ring-2 ring-white/40 transition hover:scale-105 hover:bg-white/30 active:scale-95"
              aria-label="Phát video"
            >
              <Play className="ml-1 h-7 w-7 text-white drop-shadow" />
            </button>
          </div>
        )}

        {/* Pause button khi đang play */}
        {playing && canPlay && (
          <button
            onClick={togglePlay}
            className="absolute inset-0 flex items-center justify-center opacity-0 transition hover:opacity-100"
            aria-label="Tạm dừng"
          >
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-black/40 backdrop-blur-sm">
              <Pause className="h-6 w-6 text-white" />
            </div>
          </button>
        )}

        {/* Duration badge */}
        <div className="absolute bottom-3 right-3 flex items-center gap-1.5 rounded-lg bg-black/70 px-2.5 py-1 backdrop-blur-sm">
          <Clock className="h-3.5 w-3.5 text-white" />
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
            disabled={!canPlay}
            className="absolute inset-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
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
              <Trash2 className="h-4 w-4" />
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