"use client";

import { useRef, useEffect, useCallback, useState } from "react";
import type { MovementTrack, StoreZone } from "@/types/zone.type";
import TrackDetailPopup from "./TrackDetailPopup";

interface RouteViewerProps {
  tracks: MovementTrack[];
  zones: StoreZone[];
  backgroundUrl?: string;
  selectedTrackId?: number | null;
  onSelectTrack?: (track: MovementTrack | null) => void;
}

const DEFAULT_BG = "https://placehold.co/1200x675/1e293b/475569?text=Floor+Plan";

function hexToRgb(hex: string) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `${r},${g},${b}`;
}

export default function RouteViewer({
  tracks,
  zones,
  backgroundUrl = DEFAULT_BG,
  selectedTrackId,
  onSelectTrack,
}: RouteViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const animFrameRef = useRef<number>(0);
  const [hoveredTrackId, setHoveredTrackId] = useState<number | null>(null);
  const [popupTrack, setPopupTrack] = useState<MovementTrack | null>(null);
  const [animProgress, setAnimProgress] = useState(1); // 0..1
  const isAnimating = useRef(false);

  // Load image
  useEffect(() => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = backgroundUrl;
    img.onload = () => { imgRef.current = img; drawAll(1); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backgroundUrl]);

  // ─── Draw ──────────────────────────────────────────────────────────────────
  const drawAll = useCallback(
    (progress: number) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const W = canvas.width;
      const H = canvas.height;
      ctx.clearRect(0, 0, W, H);

      // Background
      if (imgRef.current) {
        ctx.drawImage(imgRef.current, 0, 0, W, H);
      } else {
        ctx.fillStyle = "#0f172a";
        ctx.fillRect(0, 0, W, H);
      }

      // Draw zones (semi-transparent)
      zones.forEach((zone) => {
        if (zone.polygon.length < 3) return;
        ctx.beginPath();
        zone.polygon.forEach((p, i) => {
          const cx = p.x * W;
          const cy = p.y * H;
          i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy);
        });
        ctx.closePath();
        ctx.fillStyle = zone.color + "22";
        ctx.fill();
        ctx.strokeStyle = zone.color + "88";
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Zone label
        const cx = zone.polygon.reduce((s, p) => s + p.x, 0) / zone.polygon.length * W;
        const cy = zone.polygon.reduce((s, p) => s + p.y, 0) / zone.polygon.length * H;
        ctx.fillStyle = zone.color + "cc";
        ctx.font = "bold 11px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(zone.zone_name, cx, cy);
      });

      // Draw tracks
      tracks.forEach((track) => {
        if (track.points.length < 2) return;

        const isSelected = track.id === selectedTrackId;
        const isHovered = track.id === hoveredTrackId;
        const isActive = isSelected || isHovered;
        const alpha = selectedTrackId !== null && !isActive ? 0.2 : 1;
        const lineWidth = isActive ? 3 : 2;

        const totalPoints = track.points.length;
        const endIdx = Math.floor(totalPoints * progress);
        const pts = track.points.slice(0, Math.max(endIdx, 2));

        // Draw path
        ctx.beginPath();
        pts.forEach((p, i) => {
          const cx = p.x * W;
          const cy = p.y * H;
          i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy);
        });
        ctx.strokeStyle = `rgba(${hexToRgb(track.color)},${alpha})`;
        ctx.lineWidth = lineWidth;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.setLineDash([]);
        ctx.stroke();

        // Gradient dots along path
        pts.forEach((p, i) => {
          if (i === 0 || i === pts.length - 1 || i % 3 !== 0) return;
          const cx = p.x * W;
          const cy = p.y * H;
          ctx.beginPath();
          ctx.arc(cx, cy, 2, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${hexToRgb(track.color)},${alpha * 0.6})`;
          ctx.fill();
        });

        // Start point (circle)
        const start = pts[0];
        ctx.beginPath();
        ctx.arc(start.x * W, start.y * H, isActive ? 8 : 6, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${hexToRgb(track.color)},${alpha})`;
        ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,0.8)";
        ctx.lineWidth = 2;
        ctx.stroke();

        // End point (arrow head or current position)
        const last = pts[pts.length - 1];
        const prev = pts[pts.length - 2] ?? start;
        const angle = Math.atan2((last.y - prev.y) * H, (last.x - prev.x) * W);
        const cx = last.x * W;
        const cy = last.y * H;
        const r = isActive ? 9 : 7;

        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(angle);
        ctx.beginPath();
        ctx.moveTo(r, 0);
        ctx.lineTo(-r * 0.6, -r * 0.5);
        ctx.lineTo(-r * 0.6, r * 0.5);
        ctx.closePath();
        ctx.fillStyle = `rgba(${hexToRgb(track.color)},${alpha})`;
        ctx.fill();
        ctx.restore();

        // Label (anonymous_id)
        if (isActive) {
          ctx.fillStyle = `rgba(${hexToRgb(track.color)},${alpha})`;
          ctx.font = "bold 11px monospace";
          ctx.textAlign = "center";
          ctx.textBaseline = "bottom";
          ctx.fillText(track.anonymous_id, cx, cy - r - 3);
        }
      });
    },
    [tracks, zones, selectedTrackId, hoveredTrackId]
  );

  useEffect(() => {
    drawAll(animProgress);
  }, [drawAll, animProgress]);

  // Resize observer
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const ro = new ResizeObserver(() => {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
      drawAll(animProgress);
    });
    ro.observe(container);
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─── Animate replay ────────────────────────────────────────────────────────
  const playAnimation = useCallback(() => {
    if (isAnimating.current) return;
    isAnimating.current = true;
    let start: number | null = null;
    const duration = 3000;

    const step = (ts: number) => {
      if (!start) start = ts;
      const p = Math.min((ts - start) / duration, 1);
      setAnimProgress(p);
      if (p < 1) {
        animFrameRef.current = requestAnimationFrame(step);
      } else {
        isAnimating.current = false;
      }
    };

    setAnimProgress(0);
    animFrameRef.current = requestAnimationFrame(step);
  }, []);

  useEffect(() => () => cancelAnimationFrame(animFrameRef.current), []);

  // ─── Click / hover detection ───────────────────────────────────────────────
  function findTrackAt(cx: number, cy: number, W: number, H: number): MovementTrack | null {
    for (const track of [...tracks].reverse()) {
      for (const p of track.points) {
        const dx = p.x * W - cx;
        const dy = p.y * H - cy;
        if (Math.sqrt(dx * dx + dy * dy) < 12) return track;
      }
    }
    return null;
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    const t = findTrackAt(cx, cy, canvas.width, canvas.height);
    setHoveredTrackId(t?.id ?? null);
    canvas.style.cursor = t ? "pointer" : "default";
  };

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    const t = findTrackAt(cx, cy, canvas.width, canvas.height);

    if (t) {
      setPopupTrack(t);
      onSelectTrack?.(t);
    } else {
      setPopupTrack(null);
      onSelectTrack?.(null);
    }
  };

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden rounded-xl bg-slate-900">
      <canvas
        ref={canvasRef}
        style={{ display: "block", width: "100%", height: "100%" }}
        onMouseMove={handleMouseMove}
        onClick={handleClick}
        onMouseLeave={() => setHoveredTrackId(null)}
      />

      {/* Replay button */}
      <button
        onClick={playAnimation}
        className="absolute bottom-3 left-3 flex items-center gap-1.5 rounded-full bg-black/60 px-3 py-1.5 text-xs font-medium text-white backdrop-blur-sm transition hover:bg-black/80"
      >
        <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 16 16">
          <path d="M4 3l9 5-9 5V3z" />
        </svg>
        Phát lại hành trình
      </button>

      {/* Stats badge */}
      <div className="absolute bottom-3 right-3 rounded-full bg-black/60 px-3 py-1.5 text-xs text-white backdrop-blur-sm">
        {tracks.length} khách · {zones.length} vùng
      </div>

      {/* Track detail popup */}
      {popupTrack && (
        <TrackDetailPopup
          track={popupTrack}
          zones={zones}
          onClose={() => { setPopupTrack(null); onSelectTrack?.(null); }}
        />
      )}

      {/* Legend */}
      {tracks.length > 0 && (
        <div className="absolute left-3 top-3 flex flex-col gap-1 rounded-xl bg-black/60 p-2 backdrop-blur-sm">
          {tracks.slice(0, 6).map((t) => (
            <button
              key={t.id}
              onClick={() => {
                const same = t.id === selectedTrackId;
                onSelectTrack?.(same ? null : t);
                setPopupTrack(same ? null : t);
              }}
              className={`flex items-center gap-1.5 rounded-lg px-2 py-0.5 text-xs transition ${
                t.id === selectedTrackId ? "bg-white/20" : "hover:bg-white/10"
              }`}
            >
              <div className="h-2 w-2 rounded-full" style={{ backgroundColor: t.color }} />
              <span className="font-mono text-white">{t.anonymous_id}</span>
            </button>
          ))}
          {tracks.length > 6 && (
            <p className="px-2 text-[10px] text-white/50">+{tracks.length - 6} khác</p>
          )}
        </div>
      )}

      {/* Empty state */}
      {tracks.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center">
            <p className="text-sm font-medium text-slate-400">Chưa có dữ liệu tracking</p>
            <p className="mt-1 text-xs text-slate-600">Dữ liệu sẽ hiển thị sau khi BE tích hợp AI tracking</p>
          </div>
        </div>
      )}
    </div>
  );
}
