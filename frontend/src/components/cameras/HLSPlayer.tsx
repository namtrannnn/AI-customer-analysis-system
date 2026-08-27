"use client";

/**
 * HLSPlayer — Play HLS stream (.m3u8) từ MediaMTX hoặc bất kỳ HLS source nào.
 * 
 * Flow: Camera RTSP → MediaMTX → HLS (.m3u8) → component này play
 * 
 * Dùng hls.js cho browser không hỗ trợ HLS native (Chrome, Firefox).
 * Safari hỗ trợ HLS native nên sẽ dùng <video src> trực tiếp.
 */

import { useEffect, useRef, useState } from "react";
import {
  Play, Pause, Volume2, VolumeX, Maximize2,
  RefreshCw, WifiOff, Loader2, AlertTriangle,
} from "lucide-react";

interface HLSPlayerProps {
  /** HLS stream URL (.m3u8) — từ MediaMTX hoặc media server */
  src: string;
  /** Tên hiển thị góc trên trái */
  label?: string;
  /** Tự động play khi mount */
  autoPlay?: boolean;
  /** Chiều cao cố định, mặc định aspect-ratio 16/9 */
  height?: number;
  /** Callback khi stream lỗi */
  onError?: (msg: string) => void;
}

type PlayerState = "loading" | "playing" | "paused" | "error" | "offline";

export default function HLSPlayer({
  src,
  label,
  autoPlay = true,
  height,
  onError,
}: HLSPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<any>(null);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [state, setState] = useState<PlayerState>("loading");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [muted, setMuted] = useState(true);
  const [retryCount, setRetryCount] = useState(0);

  function cleanup() {
    if (hlsRef.current) {
      hlsRef.current.destroy();
      hlsRef.current = null;
    }
    if (retryTimer.current) {
      clearTimeout(retryTimer.current);
      retryTimer.current = null;
    }
  }

  function initPlayer(hlsSrc: string) {
    const video = videoRef.current;
    if (!video || !hlsSrc) return;

    cleanup();
    setState("loading");
    setErrorMsg("");

    // Safari: hỗ trợ HLS native
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = hlsSrc;
      video.addEventListener("loadedmetadata", () => setState("playing"), { once: true });
      video.addEventListener("error", () => handleError("Không thể tải stream"), { once: true });
      if (autoPlay) video.play().catch(() => {});
      return;
    }

    // Chrome/Firefox: dùng hls.js
    import("hls.js").then(({ default: Hls }) => {
      if (!Hls.isSupported()) {
        handleError("Trình duyệt không hỗ trợ HLS playback");
        return;
      }

      const hls = new Hls({
        enableWorker: true,
        lowLatencyMode: true,
        backBufferLength: 30,
        liveMaxLatencyDuration: 10,
        liveSyncDurationCount: 2,
      });

      hlsRef.current = hls;
      hls.loadSource(hlsSrc);
      hls.attachMedia(video);

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        setState("playing");
        if (autoPlay) video.play().catch(() => {});
      });

      hls.on(Hls.Events.ERROR, (_: any, data: any) => {
        if (data.fatal) {
          if (data.type === "networkError") {
            handleError("Không kết nối được stream — camera offline?");
          } else if (data.type === "mediaError") {
            hls.recoverMediaError();
          } else {
            handleError("Lỗi stream không thể khôi phục");
          }
        }
      });
    });
  }

  function handleError(msg: string) {
    setState("error");
    setErrorMsg(msg);
    onError?.(msg);
    // Auto retry sau 8 giây
    retryTimer.current = setTimeout(() => {
      setRetryCount((n) => n + 1);
    }, 8000);
  }

  function handleRetry() {
    setRetryCount((n) => n + 1);
  }

  useEffect(() => {
    if (src) initPlayer(src);
    return cleanup;
  }, [src, retryCount]);

  function toggleMute() {
    if (!videoRef.current) return;
    videoRef.current.muted = !muted;
    setMuted(!muted);
  }

  function toggleFullscreen() {
    videoRef.current?.requestFullscreen().catch(() => {});
  }

  function togglePlay() {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) { v.play(); setState("playing"); }
    else { v.pause(); setState("paused"); }
  }

  const isLoading = state === "loading";
  const isError = state === "error";

  return (
    <div
      className="group relative overflow-hidden rounded-xl bg-black"
      style={height ? { height } : { aspectRatio: "16/9" }}
    >
      {/* Video element */}
      <video
        ref={videoRef}
        className="h-full w-full object-contain"
        muted={muted}
        playsInline
        autoPlay={autoPlay}
      />

      {/* Loading overlay */}
      {isLoading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/70">
          <Loader2 className="h-8 w-8 animate-spin text-sky-400" />
          <p className="text-sm font-medium text-slate-300">Đang kết nối stream...</p>
        </div>
      )}

      {/* Error overlay */}
      {isError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/80">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-500/20">
            <WifiOff className="h-6 w-6 text-red-400" />
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold text-white">Không thể phát stream</p>
            <p className="mt-1 max-w-xs text-xs text-slate-400">{errorMsg}</p>
          </div>
          <button
            onClick={handleRetry}
            className="flex items-center gap-1.5 rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-sky-700"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Thử lại
          </button>
          {retryCount > 0 && (
            <p className="text-xs text-slate-500">Tự retry sau 8 giây... (lần {retryCount})</p>
          )}
        </div>
      )}

      {/* Camera label */}
      {label && (
        <div className="absolute left-2 top-2 flex items-center gap-1.5 rounded-lg bg-black/60 px-2.5 py-1 backdrop-blur-sm">
          <span className={`h-1.5 w-1.5 rounded-full ${state === "playing" ? "bg-emerald-400 animate-pulse" : "bg-red-400"}`} />
          <span className="text-xs font-semibold text-white">{label}</span>
        </div>
      )}

      {/* LIVE badge */}
      {state === "playing" && (
        <div className="absolute right-2 top-2 rounded-md bg-red-600 px-2 py-0.5 text-[10px] font-black tracking-widest text-white">
          LIVE
        </div>
      )}

      {/* Controls — hiện khi hover */}
      <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-black/80 to-transparent px-3 py-2 opacity-0 transition-opacity group-hover:opacity-100">
        <div className="flex items-center gap-2">
          <button onClick={togglePlay} className="text-white hover:text-sky-400">
            {state === "paused"
              ? <Play className="h-4 w-4" />
              : <Pause className="h-4 w-4" />
            }
          </button>
          <button onClick={toggleMute} className="text-white hover:text-sky-400">
            {muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          </button>
        </div>
        <button onClick={toggleFullscreen} className="text-white hover:text-sky-400">
          <Maximize2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
