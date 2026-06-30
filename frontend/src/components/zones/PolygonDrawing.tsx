"use client";

import {
  useRef,
  useEffect,
  useCallback,
  useState,
  forwardRef,
  useImperativeHandle,
} from "react";
import type { Point, StoreZone } from "@/types/zone.type";

interface PolygonDrawingProps {
  /** URL ảnh nền (floor plan hoặc camera frame) */
  backgroundUrl: string;
  /** Các zone đã lưu — hiển thị mờ bên dưới */
  existingZones?: StoreZone[];
  /** Zone đang chỉnh sửa (nếu có) — dùng để exclude khỏi existingZones */
  editingZoneId?: number | null;
  /** Màu polygon đang vẽ */
  color?: string;
  /** Callback khi polygon thay đổi */
  onChange?: (points: Point[]) => void;
  /** Cho phép vẽ */
  enabled?: boolean;
}

export interface PolygonDrawingRef {
  clearPolygon: () => void;
  setPolygon: (points: Point[]) => void;
  getPolygon: () => Point[];
}

const POINT_RADIUS = 7;
const CLOSE_THRESHOLD = 0.025; // click gần điểm đầu để đóng

function toCanvas(p: Point, w: number, h: number) {
  return { cx: p.x * w, cy: p.y * h };
}

function toPct(cx: number, cy: number, w: number, h: number): Point {
  return { x: cx / w, y: cy / h };
}

function dist(ax: number, ay: number, bx: number, by: number) {
  return Math.sqrt((ax - bx) ** 2 + (ay - by) ** 2);
}

const PolygonDrawing = forwardRef<PolygonDrawingRef, PolygonDrawingProps>(
  (
    {
      backgroundUrl,
      existingZones = [],
      editingZoneId = null,
      color = "#3b82f6",
      onChange,
      enabled = true,
    },
    ref
  ) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const imgRef = useRef<HTMLImageElement | null>(null);
    const [points, setPoints] = useState<Point[]>([]);
    const [closed, setClosed] = useState(false);
    const [dragIdx, setDragIdx] = useState<number | null>(null);
    const [hoverIdx, setHoverIdx] = useState<number | null>(null);

    // Expose methods
    useImperativeHandle(ref, () => ({
      clearPolygon: () => { setPoints([]); setClosed(false); onChange?.([]); },
      setPolygon: (pts) => { setPoints(pts); setClosed(pts.length >= 3); onChange?.(pts); },
      getPolygon: () => points,
    }));

    // Load image
    useEffect(() => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.src = backgroundUrl;
      img.onload = () => { imgRef.current = img; draw(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [backgroundUrl]);

    // ─── Draw ─────────────────────────────────────────────────────────────────
    const draw = useCallback(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const W = canvas.width;
      const H = canvas.height;

      ctx.clearRect(0, 0, W, H);

      // Background image
      if (imgRef.current) {
        ctx.drawImage(imgRef.current, 0, 0, W, H);
      } else {
        ctx.fillStyle = "#1e293b";
        ctx.fillRect(0, 0, W, H);
        ctx.fillStyle = "#334155";
        ctx.font = "14px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("Đang tải ảnh nền...", W / 2, H / 2);
      }

      // Existing zones (mờ)
      existingZones
        .filter((z) => z.id !== editingZoneId)
        .forEach((zone) => {
          if (zone.polygon.length < 2) return;
          ctx.beginPath();
          zone.polygon.forEach((p, i) => {
            const { cx, cy } = toCanvas(p, W, H);
            i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy);
          });
          ctx.closePath();
          ctx.fillStyle = zone.color + "33";
          ctx.fill();
          ctx.strokeStyle = zone.color + "99";
          ctx.lineWidth = 2;
          ctx.stroke();

          // Label
          const cx = zone.polygon.reduce((s, p) => s + p.x, 0) / zone.polygon.length * W;
          const cy = zone.polygon.reduce((s, p) => s + p.y, 0) / zone.polygon.length * H;
          ctx.fillStyle = zone.color;
          ctx.font = "bold 12px sans-serif";
          ctx.textAlign = "center";
          ctx.fillText(zone.zone_name, cx, cy);
        });

      if (points.length === 0) return;

      const canvasPoints = points.map((p) => toCanvas(p, W, H));

      // Fill when closed
      if (closed) {
        ctx.beginPath();
        canvasPoints.forEach(({ cx, cy }, i) =>
          i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy)
        );
        ctx.closePath();
        ctx.fillStyle = color + "33";
        ctx.fill();
      }

      // Lines
      ctx.beginPath();
      canvasPoints.forEach(({ cx, cy }, i) =>
        i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy)
      );
      if (closed) ctx.closePath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.5;
      ctx.setLineDash(closed ? [] : [6, 3]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Points
      canvasPoints.forEach(({ cx, cy }, i) => {
        const isFirst = i === 0;
        const isHover = i === hoverIdx;
        const r = isFirst && !closed ? POINT_RADIUS + 3 : POINT_RADIUS;

        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fillStyle = isHover ? color : "#fff";
        ctx.fill();
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        ctx.stroke();

        if (isFirst && !closed) {
          ctx.beginPath();
          ctx.arc(cx, cy, r + 5, 0, Math.PI * 2);
          ctx.strokeStyle = color + "66";
          ctx.lineWidth = 1.5;
          ctx.setLineDash([3, 2]);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      });
    }, [points, closed, color, existingZones, editingZoneId, hoverIdx]);

    useEffect(() => { draw(); }, [draw]);

    // Resize observer
    useEffect(() => {
      const container = containerRef.current;
      const canvas = canvasRef.current;
      if (!container || !canvas) return;

      const ro = new ResizeObserver(() => {
        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight;
        draw();
      });
      ro.observe(container);
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
      return () => ro.disconnect();
    }, [draw]);

    // ─── Event handlers ───────────────────────────────────────────────────────
    function getRelativePos(e: React.MouseEvent | React.TouchEvent) {
      const canvas = canvasRef.current!;
      const rect = canvas.getBoundingClientRect();
      const clientX = "touches" in e ? e.touches[0].clientX : e.clientX;
      const clientY = "touches" in e ? e.touches[0].clientY : e.clientY;
      return {
        cx: clientX - rect.left,
        cy: clientY - rect.top,
        W: canvas.width,
        H: canvas.height,
      };
    }

    function findNearPoint(cx: number, cy: number, W: number, H: number): number | null {
      for (let i = points.length - 1; i >= 0; i--) {
        const { cx: px, cy: py } = toCanvas(points[i], W, H);
        if (dist(cx, cy, px, py) <= POINT_RADIUS + 4) return i;
      }
      return null;
    }

    const handleMouseDown = useCallback(
      (e: React.MouseEvent) => {
        if (!enabled) return;
        const { cx, cy, W, H } = getRelativePos(e);

        // Drag existing point
        if (closed || points.length > 0) {
          const idx = findNearPoint(cx, cy, W, H);
          if (idx !== null) { setDragIdx(idx); return; }
        }

        if (closed) return; // can't add points after closing

        // Check close polygon
        if (points.length >= 3) {
          const { cx: fx, cy: fy } = toCanvas(points[0], W, H);
          if (dist(cx, cy, fx, fy) <= POINT_RADIUS + 8) {
            setClosed(true);
            onChange?.(points);
            return;
          }
        }

        // Add point
        const newPoint = toPct(cx, cy, W, H);
        const next = [...points, newPoint];
        setPoints(next);
        onChange?.(next);
      },
      // eslint-disable-next-line react-hooks/exhaustive-deps
      [enabled, points, closed, onChange]
    );

    const handleMouseMove = useCallback(
      (e: React.MouseEvent) => {
        const { cx, cy, W, H } = getRelativePos(e);

        // Hover detection
        const idx = findNearPoint(cx, cy, W, H);
        setHoverIdx(idx);

        // Drag
        if (dragIdx !== null) {
          const updated = [...points];
          updated[dragIdx] = toPct(cx, cy, W, H);
          setPoints(updated);
          if (closed) onChange?.(updated);
        }
      },
      // eslint-disable-next-line react-hooks/exhaustive-deps
      [dragIdx, points, closed, onChange]
    );

    const handleMouseUp = useCallback(() => {
      if (dragIdx !== null) {
        setDragIdx(null);
        onChange?.(points);
      }
    }, [dragIdx, points, onChange]);

    const handleDblClick = useCallback(
      (e: React.MouseEvent) => {
        if (!enabled || !closed) return;
        const { cx, cy, W, H } = getRelativePos(e);
        const idx = findNearPoint(cx, cy, W, H);
        if (idx !== null && points.length > 3) {
          const updated = points.filter((_, i) => i !== idx);
          setPoints(updated);
          onChange?.(updated);
        }
      },
      // eslint-disable-next-line react-hooks/exhaustive-deps
      [enabled, closed, points, onChange]
    );

    const cursor =
      !enabled ? "default"
      : dragIdx !== null ? "grabbing"
      : hoverIdx !== null ? "grab"
      : closed ? "default"
      : "crosshair";

    return (
      <div ref={containerRef} className="relative h-full w-full overflow-hidden rounded-xl bg-slate-900">
        <canvas
          ref={canvasRef}
          style={{ cursor, display: "block", width: "100%", height: "100%" }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onDoubleClick={handleDblClick}
        />
        {/* Instruction overlay */}
        {enabled && !closed && points.length === 0 && (
          <div className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-black/60 px-4 py-1.5 text-xs text-white backdrop-blur-sm">
            Click để thêm điểm • Click điểm đầu để đóng vùng
          </div>
        )}
        {enabled && !closed && points.length >= 3 && (
          <div className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-black/60 px-4 py-1.5 text-xs text-white backdrop-blur-sm">
            Click điểm đầu (vòng tròn lớn) để hoàn thành
          </div>
        )}
        {enabled && closed && (
          <div className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-black/60 px-4 py-1.5 text-xs text-white backdrop-blur-sm">
            Kéo điểm để chỉnh • Double-click điểm để xóa
          </div>
        )}
      </div>
    );
  }
);

PolygonDrawing.displayName = "PolygonDrawing";
export default PolygonDrawing;
