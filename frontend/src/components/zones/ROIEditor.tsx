"use client";

import { useState, useRef, useCallback } from "react";
import { Plus, RotateCcw, Check, X, ImagePlus, Pencil, FlaskConical } from "lucide-react";
import type { StoreZone, ZoneCreatePayload, Point } from "@/types/zone.type";
import { ZONE_TYPE_LABELS, ZONE_COLORS } from "@/types/zone.type";
import PolygonDrawing, { type PolygonDrawingRef } from "./PolygonDrawing";
import ZoneForm from "./ZoneForm";
import Button from "@/components/ui/Button";
import Modal from "@/components/ui/Modal";
import { checkPoint, type CheckPointResult } from "@/services/zone.service";

const DEFAULT_BG =
  "https://placehold.co/1200x675/1e293b/475569?text=Upload+%E1%BA%A3nh+n%E1%BB%81n+%E2%86%91";

type EditorMode = "idle" | "drawing" | "editing-polygon" | "editing-form" | "testing";

interface ROIEditorProps {
  zones: StoreZone[];
  backgroundUrl?: string;
  onBgChange?: (url: string) => void;
  onZoneCreate: (payload: ZoneCreatePayload) => Promise<void>;
  onZoneEdit: (zone: StoreZone) => void;
  onZoneDelete: (zone: StoreZone) => void;
}

// ─── Tooltip kết quả test ─────────────────────────────────────────────────────
interface TooltipState {
  x: number;       // pixel trên canvas
  y: number;
  result: CheckPointResult | null;
  loading: boolean;
}

export default function ROIEditor({
  zones,
  backgroundUrl = DEFAULT_BG,
  onBgChange,
  onZoneCreate,
  onZoneEdit,
  onZoneDelete,
}: ROIEditorProps) {
  const drawingRef = useRef<PolygonDrawingRef>(null);
  const bgInputRef = useRef<HTMLInputElement>(null);
  const canvasContainerRef = useRef<HTMLDivElement>(null);

  const [mode, setMode] = useState<EditorMode>("idle");
  const [currentPoints, setCurrentPoints] = useState<Point[]>([]);
  const [currentColor, setCurrentColor] = useState(ZONE_COLORS[0]);
  const [editingZone, setEditingZone] = useState<StoreZone | null>(null);
  const [localBg, setLocalBg] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const activeBg = localBg ?? backgroundUrl;
  const isDrawingOrEditing = mode === "drawing" || mode === "editing-polygon";
  const isTesting = mode === "testing";

  const nextColor =
    ZONE_COLORS.find((c) => !zones.some((z) => z.color === c)) ?? ZONE_COLORS[0];

  // ─── Background upload ────────────────────────────────────────────────────
  const handleBgUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    setLocalBg(url);
    onBgChange?.(url);
    e.target.value = "";
  };

  // ─── Draw mode ───────────────────────────────────────────────────────────
  const startDrawing = useCallback(() => {
    setEditingZone(null);
    setCurrentColor(nextColor);
    setCurrentPoints([]);
    setTooltip(null);
    drawingRef.current?.clearPolygon();
    setMode("drawing");
  }, [nextColor]);

  const cancelMode = useCallback(() => {
    setMode("idle");
    setCurrentPoints([]);
    setEditingZone(null);
    setTooltip(null);
    drawingRef.current?.clearPolygon();
  }, []);

  const confirmPolygon = useCallback(() => {
    if (currentPoints.length < 3) return;
    setMode("editing-form");
  }, [currentPoints]);

  const handlePolygonChange = useCallback((pts: Point[]) => {
    setCurrentPoints(pts);
  }, []);

  const handleEditClick = useCallback((zone: StoreZone) => {
    setEditingZone(zone);
    setCurrentColor(zone.color);
    setCurrentPoints(zone.polygon);
    setTooltip(null);
    drawingRef.current?.setPolygon(zone.polygon);
    setMode("editing-polygon");
  }, []);

  const handleCreate = async (payload: ZoneCreatePayload) => {
    await onZoneCreate({ ...payload, polygon: currentPoints, color: currentColor });
    cancelMode();
  };

  const handleEditSubmit = async (payload: ZoneCreatePayload) => {
    if (!editingZone) return;
    onZoneEdit({ ...editingZone, ...payload, polygon: currentPoints });
    cancelMode();
  };

  const resetPolygon = useCallback(() => {
    if (mode === "editing-polygon" && editingZone) {
      drawingRef.current?.setPolygon(editingZone.polygon);
      setCurrentPoints(editingZone.polygon);
    } else {
      drawingRef.current?.clearPolygon();
      setCurrentPoints([]);
    }
  }, [mode, editingZone]);

  // ─── Test mode: click canvas → gọi AI-11 ──────────────────────────────────
  const toggleTestMode = useCallback(() => {
    if (isTesting) {
      setMode("idle");
      setTooltip(null);
    } else {
      drawingRef.current?.clearPolygon();
      setCurrentPoints([]);
      setTooltip(null);
      setMode("testing");
    }
  }, [isTesting]);

  const handleCanvasClick = useCallback(
    async (e: React.MouseEvent<HTMLDivElement>) => {
      if (!isTesting) return;

      const container = canvasContainerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const px = e.clientX - rect.left;
      const py = e.clientY - rect.top;

      // Tọa độ tương đối 0..1
      const x = Math.max(0, Math.min(1, px / rect.width));
      const y = Math.max(0, Math.min(1, py / rect.height));

      // Hiện loading tooltip ngay tại chỗ click
      setTooltip({ x: px, y: py, result: null, loading: true });

      try {
        const result = await checkPoint(x, y);
        setTooltip({ x: px, y: py, result, loading: false });
      } catch {
        setTooltip({
          x: px, y: py,
          result: { x, y, zone_id: null, zone_name: null, zone_type: null, color: null, is_inside: false },
          loading: false,
        });
      }
    },
    [isTesting]
  );

  const pointsLabel =
    currentPoints.length < 3
      ? `${currentPoints.length} điểm — cần ít nhất 3`
      : `${currentPoints.length} điểm ✓`;

  return (
    <div className="flex h-full flex-col">
      {/* ── Toolbar ── */}
      <div
        className="flex items-center justify-between border-b px-4 py-2.5"
        style={{ borderColor: "var(--border)" }}
      >
        <div className="flex items-center gap-2">
          {/* Upload bg */}
          <Button
            size="sm"
            variant="secondary"
            onClick={() => bgInputRef.current?.click()}
            icon={<ImagePlus className="h-4 w-4" />}
          >
            {localBg ? "Đổi ảnh nền" : "Upload ảnh nền"}
          </Button>
          <input ref={bgInputRef} type="file" accept="image/*" className="hidden" onChange={handleBgUpload} />

          <div className="h-5 w-px" style={{ background: "var(--border)" }} />

          {/* Idle: vẽ + test */}
          {mode === "idle" && (
            <>
              <Button size="sm" onClick={startDrawing} icon={<Plus className="h-4 w-4" />}>
                Vẽ vùng mới
              </Button>
              {zones.length > 0 && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={toggleTestMode}
                  icon={<FlaskConical className="h-4 w-4" />}
                >
                  Test ROI
                </Button>
              )}
            </>
          )}

          {/* Test mode */}
          {isTesting && (
            <>
              <span className="rounded-full bg-teal-100 px-2.5 py-1 text-xs font-semibold text-teal-700 dark:bg-teal-900/30 dark:text-teal-400">
                🔬 Đang test — click bất kỳ điểm nào lên ảnh
              </span>
              <Button size="sm" variant="secondary" onClick={toggleTestMode} icon={<X className="h-3.5 w-3.5" />}>
                Thoát test
              </Button>
            </>
          )}

          {/* Drawing / editing-polygon */}
          {isDrawingOrEditing && (
            <>
              <span
                className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                  mode === "editing-polygon"
                    ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                    : "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400"
                }`}
              >
                {mode === "editing-polygon" ? `✎ Đang sửa: ${editingZone?.zone_name}` : "✦ Vẽ vùng mới"}
              </span>
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>{pointsLabel}</span>
              <Button size="sm" variant="ghost" onClick={resetPolygon} icon={<RotateCcw className="h-3.5 w-3.5" />}>Reset</Button>
              <Button size="sm" variant="danger" onClick={cancelMode} icon={<X className="h-3.5 w-3.5" />}>Hủy</Button>
              {currentPoints.length >= 3 && (
                <Button size="sm" onClick={confirmPolygon} icon={<Check className="h-3.5 w-3.5" />}>
                  {mode === "editing-polygon" ? "Xác nhận vùng mới" : "Xác nhận"}
                </Button>
              )}
            </>
          )}
        </div>

        {/* Color picker */}
        {isDrawingOrEditing && (
          <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
            <span>Màu:</span>
            <div className="h-5 w-5 rounded-full ring-2 ring-white shadow dark:ring-slate-700" style={{ backgroundColor: currentColor }} />
            <div className="flex gap-1">
              {ZONE_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCurrentColor(c)}
                  className={`h-4 w-4 rounded-full transition-transform hover:scale-125 ${currentColor === c ? "ring-2 ring-offset-1 ring-blue-500" : ""}`}
                  style={{ backgroundColor: c }}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Canvas ── */}
      <div
        ref={canvasContainerRef}
        className="relative min-h-0 flex-1"
        onClick={handleCanvasClick}
        style={{ cursor: isTesting ? "crosshair" : "default" }}
      >
        <PolygonDrawing
          ref={drawingRef}
          backgroundUrl={activeBg}
          existingZones={zones}
          editingZoneId={editingZone?.id ?? null}
          color={currentColor}
          onChange={handlePolygonChange}
          enabled={isDrawingOrEditing}
        />

        {/* Zone overlay (idle) */}
        {mode === "idle" && zones.length > 0 && (
          <div className="absolute right-3 top-3 flex flex-col gap-1 max-h-[80%] overflow-y-auto">
            {zones.map((z) => (
              <div key={z.id} className="flex items-center gap-1.5 rounded-lg bg-black/60 px-2.5 py-1 text-xs font-medium text-white backdrop-blur-sm">
                <div className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: z.color }} />
                <span className="max-w-[120px] truncate">{z.zone_name}</span>
                <button onClick={() => handleEditClick(z)} className="ml-1 rounded p-0.5 text-white/60 hover:bg-white/20 hover:text-white" title="Sửa vùng">
                  <Pencil className="h-3 w-3" />
                </button>
                <button onClick={() => onZoneDelete(z)} className="rounded p-0.5 text-red-300 hover:bg-red-500/20 hover:text-red-200" title="Xóa vùng">
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Edit hint */}
        {mode === "editing-polygon" && (
          <div className="pointer-events-none absolute left-1/2 top-3 -translate-x-1/2 rounded-full bg-amber-500/90 px-4 py-1.5 text-xs font-semibold text-white backdrop-blur-sm">
            Kéo điểm để chỉnh • Double-click điểm để xóa • Bấm "Xác nhận" khi xong
          </div>
        )}

        {/* Test mode hint */}
        {isTesting && !tooltip && (
          <div className="pointer-events-none absolute left-1/2 top-3 -translate-x-1/2 rounded-full bg-teal-600/90 px-4 py-1.5 text-xs font-semibold text-white backdrop-blur-sm">
            Click bất kỳ điểm nào để kiểm tra điểm đó thuộc zone nào
          </div>
        )}

        {/* ── Tooltip kết quả AI-11 ── */}
        {isTesting && tooltip && (
          <div
            className="pointer-events-none absolute z-20"
            style={{
              left: Math.min(tooltip.x + 12, (canvasContainerRef.current?.clientWidth ?? 400) - 220),
              top: Math.max(tooltip.y - 80, 8),
            }}
          >
            <div
              className="min-w-[180px] rounded-xl border px-3.5 py-3 text-sm shadow-xl backdrop-blur-sm"
              style={{
                background: "var(--bg-surface)",
                borderColor: "var(--border)",
                boxShadow: "var(--shadow-xl)",
              }}
            >
              {tooltip.loading ? (
                <div className="flex items-center gap-2" style={{ color: "var(--text-muted)" }}>
                  <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                  </svg>
                  <span className="text-xs">Đang kiểm tra...</span>
                </div>
              ) : tooltip.result?.is_inside ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <div className="h-3 w-3 rounded-full shadow-sm" style={{ backgroundColor: tooltip.result.color ?? "#3b82f6" }} />
                    <span className="font-bold" style={{ color: "var(--text-primary)" }}>
                      {tooltip.result.zone_name}
                    </span>
                  </div>
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    {tooltip.result.zone_type ? ZONE_TYPE_LABELS[tooltip.result.zone_type as keyof typeof ZONE_TYPE_LABELS] ?? tooltip.result.zone_type : ""}
                  </p>
                  <p className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>
                    ({tooltip.result.x.toFixed(3)}, {tooltip.result.y.toFixed(3)})
                  </p>
                </div>
              ) : (
                <div className="space-y-1">
                  <p className="font-semibold text-slate-500 dark:text-slate-400">⬜ Ngoài tất cả zone</p>
                  {tooltip.result && (
                    <p className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>
                      ({tooltip.result.x.toFixed(3)}, {tooltip.result.y.toFixed(3)})
                    </p>
                  )}
                </div>
              )}
            </div>
            {/* Arrow */}
            <div className="ml-3 h-2 w-2 rotate-45 border-b border-r" style={{ background: "var(--bg-surface)", borderColor: "var(--border)", marginTop: "-1px" }} />
          </div>
        )}

        {/* Click indicator dot */}
        {isTesting && tooltip && (
          <div
            className="pointer-events-none absolute z-10 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow-md"
            style={{
              left: tooltip.x,
              top: tooltip.y,
              backgroundColor: tooltip.result?.color ?? "#6b7280",
            }}
          />
        )}
      </div>

      {/* ── Create Modal ── */}
      <Modal open={mode === "editing-form" && !editingZone} onClose={cancelMode} title="Đặt tên vùng theo dõi" size="md">
        <ZoneForm
          polygon={currentPoints}
          initialValues={{ color: currentColor }}
          onSubmit={handleCreate}
          onCancel={cancelMode}
          submitLabel="Tạo vùng"
        />
      </Modal>

      {/* ── Edit Modal ── */}
      <Modal open={mode === "editing-form" && !!editingZone} onClose={cancelMode} title={`Cập nhật: ${editingZone?.zone_name}`} size="md">
        {editingZone && (
          <ZoneForm
            polygon={currentPoints}
            initialValues={{
              zone_name: editingZone.zone_name,
              zone_type: editingZone.zone_type,
              description: editingZone.description ?? "",
              color: currentColor,
            }}
            onSubmit={handleEditSubmit}
            onCancel={cancelMode}
            submitLabel="Lưu thay đổi"
          />
        )}
      </Modal>
    </div>
  );
}
