"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { MapPin, Route, Trash2, AlertTriangle } from "lucide-react";
import ROIEditor, { type ROIEditorRef } from "@/components/zones/ROIEditor";
import ZoneList from "@/components/zones/ZoneList";
import RouteViewer from "@/components/zones/RouteViewer";
import TrackInspector from "@/components/zones/TrackInspector";
import Loading from "@/components/ui/Loading";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Select from "@/components/ui/Select";
import Modal from "@/components/ui/Modal";
import type { SelectOption } from "@/components/ui/Select";
import {
  getZones,
  createZone,
  updateZone,
  deleteZone,
  getMovementTracks,
} from "@/services/zone.service";
import type {
  StoreZone,
  ZoneCreatePayload,
  MovementTrack,
  TrackFilterParams,
} from "@/types/zone.type";

type TabKey = "roi" | "tracking";

export default function ZonesPage() {
  const [tab, setTab] = useState<TabKey>("roi");

  const roiEditorRef = useRef<ROIEditorRef>(null);

  // ─── Background image state (shared giữa ROI editor & Route viewer) ────────
  const [bgUrl, setBgUrl] = useState<string | null>(null);
  const [zones, setZones] = useState<StoreZone[]>([]);
  const [zonesLoading, setZonesLoading] = useState(true);
  const [selectedZone, setSelectedZone] = useState<StoreZone | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<StoreZone | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // ─── Track state ───────────────────────────────────────────────────────────
  const [tracks, setTracks] = useState<MovementTrack[]>([]);
  const [tracksLoading, setTracksLoading] = useState(false);
  const [selectedTrack, setSelectedTrack] = useState<MovementTrack | null>(
    null,
  );
  const [trackFilter, setTrackFilter] = useState<TrackFilterParams>({});

  // ─── Toast ─────────────────────────────────────────────────────────────────
  const [toast, setToast] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);

  function showToast(type: "success" | "error", msg: string) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  }

  // ─── Load data ─────────────────────────────────────────────────────────────
  const loadZones = useCallback(async () => {
    setZonesLoading(true);
    try {
      const data = await getZones();
      setZones(data);
    } catch (e: unknown) {
      showToast(
        "error",
        e instanceof Error ? e.message : "Không tải được danh sách vùng",
      );
    } finally {
      setZonesLoading(false);
    }
  }, []);

  const loadTracks = useCallback(async () => {
    setTracksLoading(true);
    try {
      const data = await getMovementTracks(trackFilter);
      setTracks(data);
    } catch {
      showToast("error", "Không tải được dữ liệu tracking");
    } finally {
      setTracksLoading(false);
    }
  }, [trackFilter]);

  useEffect(() => {
    loadZones();
  }, [loadZones]);
  useEffect(() => {
    if (tab === "tracking") loadTracks();
  }, [tab, loadTracks]);

  // ─── Zone CRUD ─────────────────────────────────────────────────────────────
  const handleCreate = async (payload: ZoneCreatePayload) => {
    const created = await createZone(payload);
    setZones((prev) => [created, ...prev]);
    showToast("success", `Đã tạo vùng "${created.zone_name}"`);
  };

  const handleEdit = async (zone: StoreZone) => {
    const updated = await updateZone(zone.id, {
      zone_name: zone.zone_name,
      zone_type: zone.zone_type,
      description: zone.description ?? undefined,
      polygon: zone.polygon,
      color: zone.color,
    });
    setZones((prev) => prev.map((z) => (z.id === updated.id ? updated : z)));
    showToast("success", `Đã cập nhật vùng "${updated.zone_name}"`);
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleteLoading(true);
    try {
      await deleteZone(deleteTarget.id);
      setZones((prev) => prev.filter((z) => z.id !== deleteTarget.id));
      showToast("success", `Đã xóa vùng "${deleteTarget.zone_name}"`);
      setDeleteTarget(null);
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "Xóa thất bại");
    } finally {
      setDeleteLoading(false);
    }
  };

  // ─── Zone filter options for tracking tab ──────────────────────────────────
  const zoneOptions: SelectOption<string>[] = [
    { value: "", label: "Tất cả vùng" },
    ...zones.map((z) => ({ value: String(z.id), label: z.zone_name })),
  ];

  const durationOptions = [
    { value: "all", label: "Tất cả thời lượng" },
    { value: "short", label: "Dưới 1 phút (<60s)" },
    { value: "medium", label: "1 - 5 phút" },
    { value: "long", label: "Trên 5 phút" },
  ];

  // ─── Filtered tracks computed on the fly ───
  const getFilteredTracks = useCallback(() => {
    return tracks.filter((t) => {
      // 1. Filter by Person ID / ANON ID
      if (trackFilter.person_id?.trim()) {
        const q = trackFilter.person_id.trim().toLowerCase();
        const matchesAnon = t.anonymous_id?.toLowerCase().includes(q);
        const matchesName = t.customer_name?.toLowerCase().includes(q);
        if (!matchesAnon && !matchesName) return false;
      }

      // 2. Filter by Zone
      if (trackFilter.zone_id) {
        if (!t.zones_visited.includes(Number(trackFilter.zone_id)))
          return false;
      }

      // 3. Filter by Date (YYYY-MM-DD)
      if (trackFilter.date) {
        const trackDate = t.entry_time?.split("T")[0];
        if (trackDate !== trackFilter.date) return false;
      }

      // 4. Filter by Start Time (HH:MM)
      if (trackFilter.start_time) {
        const trackTime = t.entry_time?.split("T")[1]?.substring(0, 5); // "HH:MM"
        if (!trackTime || trackTime < trackFilter.start_time) return false;
      }

      // 5. Filter by End Time (HH:MM)
      if (trackFilter.end_time) {
        const trackTime = t.entry_time?.split("T")[1]?.substring(0, 5); // "HH:MM"
        if (!trackTime || trackTime > trackFilter.end_time) return false;
      }

      // 6. Filter by Duration
      if (trackFilter.duration && trackFilter.duration !== "all") {
        const dur = t.duration_seconds ?? 0;
        if (trackFilter.duration === "short" && dur >= 60) return false;
        if (trackFilter.duration === "medium" && (dur < 60 || dur > 300))
          return false;
        if (trackFilter.duration === "long" && dur <= 300) return false;
      }

      return true;
    });
  }, [tracks, trackFilter]);

  const displayTracks = getFilteredTracks();

  return (
    <>
      {/* ── Page header ── */}
      <div className="mb-6 flex items-center gap-1.5">
        <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
          <MapPin className="h-3 w-3" />
          Quản lý vùng
        </div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
          Vùng theo dõi & Tracking
        </h1>
      </div>

      {/* ── Tabs ── */}
      <div
        className="mb-5 flex gap-1 rounded-xl p-1"
        style={{ background: "var(--bg-surface-2)" }}
      >
        {(
          [
            {
              key: "roi",
              label: "Quản lý vùng ROI",
              icon: <MapPin className="h-4 w-4" />,
            },
            {
              key: "tracking",
              label: "Theo dõi đường đi",
              icon: <Route className="h-4 w-4" />,
            },
          ] as { key: TabKey; label: string; icon: React.ReactNode }[]
        ).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-semibold transition-all ${
              tab === t.key
                ? "bg-white shadow-sm text-slate-900 dark:bg-slate-700 dark:text-slate-100"
                : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {/* ── ROI Editor Tab ── */}
      {tab === "roi" && (
        <div className="grid h-[calc(100vh-280px)] min-h-[500px] gap-5 lg:grid-cols-[1fr_280px]">
          {/* Canvas */}
          <div
            className="overflow-hidden rounded-2xl shadow-sm"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
            }}
          >
            <div className="h-0.5 bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500" />
            {zonesLoading ? (
              <div className="flex h-full items-center justify-center">
                <Loading text="Đang tải vùng theo dõi..." />
              </div>
            ) : (
              <ROIEditor
                ref={roiEditorRef}
                zones={zones}
                backgroundUrl={bgUrl ?? undefined}
                onBgChange={setBgUrl}
                onZoneCreate={handleCreate}
                onZoneEdit={handleEdit}
                onZoneDelete={(z) => setDeleteTarget(z)}
              />
            )}
          </div>

          {/* Zone list panel */}
          <div
            className="flex flex-col overflow-hidden rounded-2xl shadow-sm"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
            }}
          >
            <div
              className="flex items-center justify-between border-b px-4 py-3"
              style={{ borderColor: "var(--border)" }}
            >
              <h3
                className="text-sm font-semibold"
                style={{ color: "var(--text-primary)" }}
              >
                Danh sách vùng
                <span
                  className="ml-2 rounded-full px-2 py-0.5 text-xs"
                  style={{
                    background: "var(--bg-surface-2)",
                    color: "var(--text-muted)",
                  }}
                >
                  {zones.length}
                </span>
              </h3>
            </div>

            <div className="flex-1 overflow-y-auto p-3">
              <ZoneList
                zones={zones}
                selectedId={selectedZone?.id}
                onSelect={setSelectedZone}
                onEdit={(zone) => roiEditorRef.current?.startEdit(zone)}
                onDelete={(z) => setDeleteTarget(z)}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Tracking Tab ── */}
      {tab === "tracking" && (
        <div className="space-y-4">
          {/* Filter bar */}
          <div
            className="flex flex-wrap items-center gap-3 rounded-2xl p-4 shadow-sm"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
            }}
          >
            {/* Person search */}
            <div className="min-w-[200px] flex-1">
              <Input
                placeholder="Tìm theo ANON ID hoặc KH ID..."
                value={trackFilter.person_id ?? ""}
                onChange={(e) =>
                  setTrackFilter((p) => ({ ...p, person_id: e.target.value }))
                }
                leftIcon={<Route className="h-4 w-4" />}
              />
            </div>

            {/* Zone dropdown */}
            <Select
              value={String(trackFilter.zone_id ?? "")}
              options={zoneOptions}
              onChange={(v) =>
                setTrackFilter((p) => ({ ...p, zone_id: v ? Number(v) : "" }))
              }
              ariaLabel="Lọc theo vùng"
              className="min-w-[160px]"
            />

            {/* Date filter */}
            <div className="flex items-center gap-1.5 min-w-[145px]">
              <span className="text-xs text-slate-450 shrink-0">Ngày:</span>
              <Input
                type="date"
                value={trackFilter.date ?? ""}
                onChange={(e) =>
                  setTrackFilter((p) => ({ ...p, date: e.target.value }))
                }
                className="w-full"
              />
            </div>

            {/* Time range filters */}
            <div className="flex items-center gap-1.5 min-w-[220px]">
              <span className="text-xs text-slate-450 shrink-0">Giờ:</span>
              <Input
                type="time"
                value={trackFilter.start_time ?? ""}
                onChange={(e) =>
                  setTrackFilter((p) => ({ ...p, start_time: e.target.value }))
                }
                className="w-full"
              />
              <span className="text-xs text-slate-450 shrink-0">đến</span>
              <Input
                type="time"
                value={trackFilter.end_time ?? ""}
                onChange={(e) =>
                  setTrackFilter((p) => ({ ...p, end_time: e.target.value }))
                }
                className="w-full"
              />
            </div>

            {/* Duration filter */}
            <Select
              value={trackFilter.duration ?? "all"}
              options={durationOptions}
              onChange={(v) =>
                setTrackFilter((p) => ({ ...p, duration: v as any }))
              }
              ariaLabel="Lọc theo thời lượng"
              className="min-w-[160px]"
            />

            {/* Control buttons */}
            <div className="ml-auto flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setTrackFilter({})}
              >
                Reset
              </Button>

              <Button size="sm" onClick={loadTracks} loading={tracksLoading}>
                Làm mới
              </Button>
            </div>
          </div>

          {/* Main content grid */}
          <div
            className="grid grid-cols-1 gap-5 lg:grid-cols-[3fr_1fr] items-stretch min-h-[500px]"
            style={{ height: "calc(100vh - 330px)" }}
          >
            {/* Canvas column */}
            <div
              className="overflow-hidden rounded-2xl shadow-sm flex flex-col"
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
              }}
            >
              <div className="h-0.5 bg-gradient-to-r from-violet-500 via-purple-500 to-pink-500" />
              <div className="flex-1 min-h-0 relative">
                {tracksLoading ? (
                  <div className="flex h-full items-center justify-center">
                    <Loading text="Đang tải dữ liệu tracking..." />
                  </div>
                ) : (
                  <RouteViewer
                    tracks={displayTracks}
                    zones={zones}
                    backgroundUrl={bgUrl ?? undefined}
                    selectedTrackId={selectedTrack?.id}
                    onSelectTrack={setSelectedTrack}
                  />
                )}
              </div>
            </div>

            {/* Inspector column */}
            <div
              className="flex flex-col overflow-hidden rounded-2xl shadow-sm border"
              style={{
                background: "var(--bg-surface)",
                borderColor: "var(--border)",
              }}
            >
              <TrackInspector
                tracks={displayTracks}
                zones={zones}
                selectedTrackId={selectedTrack?.id}
                onSelectTrack={setSelectedTrack}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Delete confirm modal ── */}
      <Modal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="Xác nhận xóa vùng"
        size="sm"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => setDeleteTarget(null)}
              disabled={deleteLoading}
            >
              Hủy
            </Button>
            <Button
              variant="danger"
              onClick={handleDelete}
              loading={deleteLoading}
            >
              Xóa vùng
            </Button>
          </>
        }
      >
        <div className="flex flex-col items-center gap-3 py-2 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/20">
            <AlertTriangle className="h-6 w-6 text-red-500" />
          </div>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Xóa vùng{" "}
            <span
              className="font-semibold"
              style={{ color: "var(--text-primary)" }}
            >
              "{deleteTarget?.zone_name}"
            </span>
            ? Dữ liệu tracking liên quan sẽ không bị ảnh hưởng.
          </p>
        </div>
      </Modal>

      {/* ── Toast ── */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-xl px-4 py-3 shadow-xl ${
            toast.type === "success"
              ? "bg-emerald-600 text-white"
              : "bg-red-600 text-white"
          }`}
          role="alert"
        >
          <span className="text-sm font-semibold">{toast.msg}</span>
        </div>
      )}
    </>
  );
}
