/**
 * Trang bản đồ nhiệt khu vực khách quan tâm (PB07 - Heatmap)
 * Dùng Canvas (giống RouteViewer) để vẽ polygon chính xác lên ảnh mặt bằng.
 * Color scale: Xanh lục → Vàng → Cam → Đỏ dựa trên intensity %.
 */

"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  Flame, Calendar, RefreshCw, AlertCircle, Image as ImageIcon,
  MapPin, Clock, Users,
} from "lucide-react";

import { formatDuration } from "@/utils/formatDate";
import { getZoneHeatmap } from "@/services/zone.service";
import type { ZoneHeatmapItem, ZoneHeatmapFilters } from "@/types/zone.type";
import { ZONE_TYPE_LABELS } from "@/types/zone.type";

const DEFAULT_BG =
  "https://placehold.co/1200x675/1e293b/475569?text=Upload+Anh+Mat+Bang+Cua+Hang+↑";

// ─── HSL Color Scale ────────────────────────────────────────────────────────
// 0%   → Xanh lục (hue=120, Green)
// 33%  → Vàng     (hue=60,  Yellow)
// 66%  → Cam      (hue=30,  Orange)
// 100% → Đỏ      (hue=0,   Red)
function intensityToHSL(intensity: number): { fill: string; stroke: string; label: string } {
  const t = Math.max(0, Math.min(100, intensity)) / 100;
  const hue = 120 - t * 120; // 120 (green) → 0 (red)
  const sat = 80 + t * 20;   // 80% → 100%
  const light = 50;
  const fillAlpha = 0.35 + t * 0.45; // 0.35 → 0.80
  const strokeAlpha = 0.7 + t * 0.3;  // 0.7 → 1.0
  return {
    fill: `hsla(${hue}, ${sat}%, ${light}%, ${fillAlpha})`,
    stroke: `hsla(${hue}, ${sat}%, ${light}%, ${strokeAlpha})`,
    label: `hsl(${hue}, ${sat}%, ${light + 15}%)`,
  };
}

export default function ZoneHeatmapPage() {
  // ─── State ──────────────────────────────────────────────
  const [heatmapItems, setHeatmapItems] = useState<ZoneHeatmapItem[]>([]);
  const [maxDuration, setMaxDuration] = useState(0);
  const [totalVisitsSum, setTotalVisitsSum] = useState(0);

  const [filters, setFilters] = useState<ZoneHeatmapFilters>({
    start_date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
    end_date: new Date().toISOString().split("T")[0],
  });

  const [bgUrl, setBgUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredZone, setHoveredZone] = useState<ZoneHeatmapItem | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  // ─── Fetch data từ API ──────────────────────────────────
  const fetchHeatmapData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getZoneHeatmap(filters);
      setHeatmapItems(response.items);
      setMaxDuration(response.max_duration);
      setTotalVisitsSum(response.total_visits_sum);
    } catch (err: any) {
      console.error("Lỗi lấy dữ liệu Heatmap:", err);
      setError("Không thể lấy dữ liệu bản đồ nhiệt. Vui lòng tải lại trang.");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchHeatmapData();
  }, [fetchHeatmapData]);

  // ─── Upload mặt bằng cửa hàng ──────────────────────────
  const handleBgUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    setBgUrl(url);
    e.target.value = "";
  };

  // ─── Load background image ─────────────────────────────
  useEffect(() => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = bgUrl || DEFAULT_BG;
    img.onload = () => {
      imgRef.current = img;
      drawHeatmap();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bgUrl]);

  // ─── Draw Heatmap on Canvas ─────────────────────────────
  const drawHeatmap = useCallback(() => {
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

    // Draw zone polygons with heatmap colors
    heatmapItems.forEach((item) => {
      if (!item.polygon || item.polygon.length < 3) return;

      const colors = intensityToHSL(item.intensity);

      // Fill polygon
      ctx.beginPath();
      item.polygon.forEach((p, i) => {
        const cx = p.x * W;
        const cy = p.y * H;
        i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy);
      });
      ctx.closePath();
      ctx.fillStyle = colors.fill;
      ctx.fill();
      ctx.strokeStyle = colors.stroke;
      ctx.lineWidth = 2.5;
      ctx.stroke();

      // Zone label (tên vùng + intensity %)
      const centerX = item.polygon.reduce((s, p) => s + p.x, 0) / item.polygon.length * W;
      const centerY = item.polygon.reduce((s, p) => s + p.y, 0) / item.polygon.length * H;

      // Label background pill
      const labelText = item.zone_name;
      const intensityText = `${Math.round(item.intensity)}%`;
      ctx.font = "bold 12px 'Inter', sans-serif";
      const textWidth = ctx.measureText(labelText).width;
      const pillW = textWidth + 40;
      const pillH = 36;

      ctx.fillStyle = "rgba(0,0,0,0.65)";
      ctx.beginPath();
      const rx = centerX - pillW / 2;
      const ry = centerY - pillH / 2;
      const r = 8;
      ctx.moveTo(rx + r, ry);
      ctx.lineTo(rx + pillW - r, ry);
      ctx.quadraticCurveTo(rx + pillW, ry, rx + pillW, ry + r);
      ctx.lineTo(rx + pillW, ry + pillH - r);
      ctx.quadraticCurveTo(rx + pillW, ry + pillH, rx + pillW - r, ry + pillH);
      ctx.lineTo(rx + r, ry + pillH);
      ctx.quadraticCurveTo(rx, ry + pillH, rx, ry + pillH - r);
      ctx.lineTo(rx, ry + r);
      ctx.quadraticCurveTo(rx, ry, rx + r, ry);
      ctx.closePath();
      ctx.fill();

      // Zone name
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 11px 'Inter', sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(labelText, centerX, centerY - 6);

      // Intensity %
      ctx.fillStyle = colors.label;
      ctx.font = "bold 10px 'Inter', sans-serif";
      ctx.fillText(intensityText, centerX, centerY + 8);
    });
  }, [heatmapItems]);

  // Redraw when data changes
  useEffect(() => {
    drawHeatmap();
  }, [drawHeatmap]);

  // ─── Resize observer ────────────────────────────────────
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const ro = new ResizeObserver(() => {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
      drawHeatmap();
    });
    ro.observe(container);
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─── Canvas mouse hover → find zone ────────────────────
  function findZoneAtPoint(cx: number, cy: number, W: number, H: number): ZoneHeatmapItem | null {
    // Point-in-polygon (ray casting) for each zone
    for (const item of heatmapItems) {
      if (!item.polygon || item.polygon.length < 3) continue;
      const px = cx / W;
      const py = cy / H;
      let inside = false;
      const poly = item.polygon;
      for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        const xi = poly[i].x, yi = poly[i].y;
        const xj = poly[j].x, yj = poly[j].y;
        if ((yi > py) !== (yj > py) && px < (xj - xi) * (py - yi) / (yj - yi) + xi) {
          inside = !inside;
        }
      }
      if (inside) return item;
    }
    return null;
  }

  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    const zone = findZoneAtPoint(cx, cy, canvas.width, canvas.height);
    setHoveredZone(zone);
    if (zone) {
      setMousePos({ x: cx, y: cy });
      canvas.style.cursor = "pointer";
    } else {
      setMousePos(null);
      canvas.style.cursor = "default";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-800 dark:text-white tracking-tight flex items-center gap-2.5">
            <Flame className="h-7 w-7 text-rose-500 animate-bounce" />
            Bản đồ nhiệt khu vực (Zone Heatmap)
          </h1>
          <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">
            Theo dõi mật độ và thời gian quan tâm của khách hàng tại các vùng ROI trong cửa hàng
          </p>
        </div>

        {/* Upload Button */}
        <div className="flex items-center gap-2">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleBgUpload}
            accept="image/*"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition"
          >
            <ImageIcon className="h-4 w-4" />
            Tải mặt bằng tĩnh
          </button>
          <button
            onClick={fetchHeatmapData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-rose-50 dark:bg-rose-950/20 hover:bg-rose-100 text-rose-600 dark:text-rose-400 transition disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Làm mới
          </button>
        </div>
      </div>

      {/* Date Filters */}
      <div className="flex flex-wrap items-center gap-3 p-4 bg-white dark:bg-slate-800 rounded-2xl border border-slate-100 dark:border-slate-700/60 shadow-sm">
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-slate-400" />
          <label className="text-xs font-bold text-slate-500 uppercase">Từ ngày</label>
          <input
            type="date"
            value={filters.start_date || ""}
            onChange={(e) => setFilters(prev => ({ ...prev, start_date: e.target.value }))}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm text-slate-700 dark:text-slate-300 focus:ring-2 focus:ring-rose-500/30 outline-none"
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs font-bold text-slate-500 uppercase">Đến ngày</label>
          <input
            type="date"
            value={filters.end_date || ""}
            onChange={(e) => setFilters(prev => ({ ...prev, end_date: e.target.value }))}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm text-slate-700 dark:text-slate-300 focus:ring-2 focus:ring-rose-500/30 outline-none"
          />
        </div>
        {totalVisitsSum > 0 && (
          <div className="ml-auto text-xs font-bold text-slate-400 bg-slate-50 dark:bg-slate-900/50 px-3 py-1.5 rounded-xl">
            Tổng lượt ghé: <span className="text-rose-500">{totalVisitsSum}</span> lượt
          </div>
        )}
      </div>

      {error && (
        <div className="px-4 py-3 rounded-xl bg-red-50 dark:bg-red-900/20 text-sm font-semibold text-red-600 dark:text-red-400 flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {/* Main Grid: Heatmap Canvas & Ranking */}
      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-5 items-stretch" style={{ minHeight: 520 }}>
        {/* Heatmap Canvas */}
        <div className="bg-white dark:bg-slate-800 rounded-2xl border border-slate-100 dark:border-slate-700/60 shadow-sm overflow-hidden flex flex-col">
          <div className="h-0.5 bg-gradient-to-r from-green-500 via-yellow-500 via-orange-500 to-red-500" />

          <div className="p-4 border-b border-slate-100 dark:border-slate-700/60 flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
              <MapPin className="h-4 w-4 text-rose-500" /> Mặt bằng nhiệt tương tác
            </span>
            <span className="text-[10px] text-slate-400 font-semibold italic">Di chuột qua từng vùng để xem thông tin</span>
          </div>

          {/* Canvas container - full width */}
          <div
            ref={containerRef}
            className="relative flex-1 min-h-0 bg-slate-900"
            style={{ minHeight: 420 }}
          >
            <canvas
              ref={canvasRef}
              style={{ display: "block", width: "100%", height: "100%" }}
              onMouseMove={handleCanvasMouseMove}
              onMouseLeave={() => { setHoveredZone(null); setMousePos(null); }}
            />

            {/* Hover Tooltip */}
            {hoveredZone && mousePos && (
              <div
                className="absolute z-50 p-4 rounded-xl border border-slate-700/60 bg-slate-900/95 text-white shadow-2xl backdrop-blur-md text-xs pointer-events-none w-56 flex flex-col gap-2.5"
                style={{
                  left: Math.min(mousePos.x + 15, (containerRef.current?.clientWidth ?? 400) - 240),
                  top: Math.max(mousePos.y - 120, 8),
                }}
              >
                <div className="flex items-center justify-between border-b border-slate-700/60 pb-1.5">
                  <span className="font-extrabold text-sm">{hoveredZone.zone_name}</span>
                  <span
                    className="text-[9px] px-1.5 py-0.5 rounded font-extrabold text-white"
                    style={{ backgroundColor: intensityToHSL(hoveredZone.intensity).stroke.replace(/[\d.]+\)$/, '1)') }}
                  >
                    {Math.round(hoveredZone.intensity)}%
                  </span>
                </div>
                <div className="space-y-1.5 text-slate-300">
                  <div className="flex justify-between">
                    <span>Phân loại:</span>
                    <span className="font-bold text-white">{ZONE_TYPE_LABELS[hoveredZone.zone_type] || "Khác"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Lượt ghé:</span>
                    <span className="font-bold text-white flex items-center gap-0.5"><Users className="h-3.5 w-3.5 text-rose-400" /> {hoveredZone.total_visits}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Thời gian:</span>
                    <span className="font-bold text-white flex items-center gap-0.5"><Clock className="h-3.5 w-3.5 text-rose-400" /> {formatDuration(hoveredZone.total_duration)}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Empty state */}
            {!loading && heatmapItems.length === 0 && (
              <div className="absolute inset-0 flex items-center justify-center">
                <p className="text-sm font-medium text-slate-500">Chưa có dữ liệu vùng. Vui lòng tạo Zone ROI trước.</p>
              </div>
            )}
          </div>
        </div>

        {/* Right side: Heatmap rankings list */}
        <div className="bg-white dark:bg-slate-800 rounded-2xl border border-slate-100 dark:border-slate-700/60 shadow-sm flex flex-col overflow-hidden">
          <div className="h-0.5 bg-gradient-to-r from-amber-500 to-rose-500" />

          <div className="p-5 border-b border-slate-100 dark:border-slate-700/60">
            <h2 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wide flex items-center gap-2">
              <Flame className="h-4 w-4 text-rose-500" />
              Xếp hạng mức quan tâm
            </h2>
            <p className="text-xs text-slate-400 mt-1">Sắp xếp các khu vực theo tổng thời lượng khách hàng lưu lại</p>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {loading ? (
              <div className="space-y-3">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="h-16 bg-slate-50 dark:bg-slate-900/30 animate-pulse rounded-xl" />
                ))}
              </div>
            ) : heatmapItems.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-12">Không có dữ liệu xếp hạng</p>
            ) : (
              <div className="space-y-3">
                {heatmapItems
                  .slice()
                  .sort((a, b) => b.total_duration - a.total_duration)
                  .map((item, idx) => {
                    const barWidth = maxDuration > 0 ? (item.total_duration / maxDuration) * 100 : 0;
                    const colors = intensityToHSL(item.intensity);
                    return (
                      <div
                        key={item.zone_id}
                        className="p-3.5 bg-slate-50 dark:bg-slate-900/40 rounded-xl border border-slate-100 dark:border-slate-800/80 hover:border-rose-500/30 transition group"
                      >
                        <div className="flex items-center justify-between gap-3 mb-2">
                          <div className="flex items-center gap-2.5">
                            <span className="text-xs font-black text-slate-350 dark:text-slate-600 w-6">#{idx + 1}</span>
                            <div
                              className="h-3.5 w-3.5 rounded-full ring-2 ring-white dark:ring-slate-800 shadow-sm"
                              style={{ backgroundColor: colors.stroke.replace(/[\d.]+\)$/, '1)') }}
                            />
                            <div>
                              <p className="text-xs font-bold text-slate-800 dark:text-white">{item.zone_name}</p>
                              <p className="text-[10px] text-slate-400 mt-0.5">{ZONE_TYPE_LABELS[item.zone_type] || "Khác"}</p>
                            </div>
                          </div>
                          <div className="text-right shrink-0">
                            <p className="text-xs font-extrabold text-slate-700 dark:text-slate-300">{formatDuration(item.total_duration)}</p>
                            <p className="text-[9px] text-slate-400 mt-0.5">{item.total_visits} lượt ghé</p>
                          </div>
                        </div>
                        {/* Progress bar */}
                        <div className="h-1.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{
                              width: `${barWidth}%`,
                              background: `linear-gradient(90deg, ${colors.fill}, ${colors.stroke.replace(/[\d.]+\)$/, '1)')})`,
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}
          </div>

          {/* Color scale Legend */}
          <div className="border-t border-slate-100 dark:border-slate-700/60 p-4">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Thang mật độ nhiệt</p>
            <div className="flex items-center gap-1.5 text-[10px] text-slate-400 font-semibold">
              <span>Thấp</span>
              <div className="flex-1 h-3 rounded-full bg-gradient-to-r from-green-500 via-yellow-400 via-orange-500 to-red-600" />
              <span>Cao</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
