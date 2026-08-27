"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Cctv, Plus, Pencil, Trash2, AlertTriangle,
  Wifi, WifiOff, RefreshCw, ServerCrash, Settings,
  MapPin, Layers, Signal, MonitorPlay, X,
} from "lucide-react";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import Modal from "@/components/ui/Modal";
import Input from "@/components/ui/Input";
import Select from "@/components/ui/Select";
import HLSPlayer from "@/components/cameras/HLSPlayer";
import { useToast } from "@/components/ui/ToastProvider";
import { usePermission } from "@/hooks/usePermission";
import {
  getCameras,
  createCamera,
  updateCamera,
  deleteCamera,
} from "@/services/camera.service";
import type {
  Camera,
  CameraCreatePayload,
  CameraStatus,
  ConnectionStatus,
} from "@/types/camera.type";
import {
  CAMERA_STATUS_CONFIG,
  CONNECTION_STATUS_CONFIG,
  MODE_LABELS,
  TRANSPORT_LABELS,
} from "@/types/camera.type";
import { formatDateTime } from "@/utils/formatDate";

// ─── Connection status dot ────────────────────────────────────────────────────
function ConnectionDot({ status }: { status: ConnectionStatus | null }) {
  if (!status) return (
    <span className="inline-flex items-center gap-1.5 text-xs text-slate-400">
      <span className="h-2 w-2 rounded-full bg-slate-300" />
      Chưa kết nối
    </span>
  );
  const cfg = CONNECTION_STATUS_CONFIG[status];
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
      <span className={`h-2 w-2 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

// ─── Camera status badge ──────────────────────────────────────────────────────
function StatusBadge({ status }: { status: CameraStatus }) {
  const cfg = CAMERA_STATUS_CONFIG[status];
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${cfg.bg} ${cfg.color}`}>
      {cfg.label}
    </span>
  );
}

// ─── Camera card ──────────────────────────────────────────────────────────────
function CameraCard({
  camera,
  canManage,
  onEdit,
  onDelete,
  onLive,
}: {
  camera: Camera;
  canManage: boolean;
  onEdit: (c: Camera) => void;
  onDelete: (c: Camera) => void;
  onLive: (c: Camera) => void;
}) {
  const connIcon = camera.last_connection_status === "online"
    ? <Wifi className="h-4 w-4 text-emerald-500" />
    : camera.last_connection_status === "reconnecting"
    ? <RefreshCw className="h-4 w-4 text-amber-500 animate-spin" />
    : camera.last_connection_status === "error"
    ? <ServerCrash className="h-4 w-4 text-red-500" />
    : <WifiOff className="h-4 w-4 text-slate-400" />;

  return (
    <div
      className="group flex flex-col overflow-hidden rounded-2xl transition hover:-translate-y-0.5 hover:shadow-md"
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {/* Top accent bar */}
      <div className={`h-1 w-full ${
        camera.status === "active" ? "bg-gradient-to-r from-sky-500 to-blue-600" :
        camera.status === "maintenance" ? "bg-gradient-to-r from-amber-400 to-orange-500" :
        camera.status === "error" ? "bg-gradient-to-r from-red-500 to-rose-600" :
        "bg-slate-200 dark:bg-slate-700"
      }`} />

      <div className="flex flex-1 flex-col gap-3 p-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
              camera.status === "active" ? "bg-sky-50 dark:bg-sky-500/10" : "bg-slate-100 dark:bg-slate-800"
            }`}>
              <Cctv className={`h-4.5 w-4.5 ${
                camera.status === "active" ? "text-sky-600 dark:text-sky-400" : "text-slate-400"
              }`} style={{ height: 18, width: 18 }} />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                {camera.camera_name}
              </p>
              {camera.camera_position && (
                <p className="flex items-center gap-1 text-xs truncate" style={{ color: "var(--text-muted)" }}>
                  <MapPin className="h-3 w-3 shrink-0" />
                  {camera.camera_position}
                </p>
              )}
            </div>
          </div>
          <StatusBadge status={camera.status} />
        </div>

        {/* Info rows */}
        <div className="space-y-1.5 text-xs" style={{ color: "var(--text-secondary)" }}>
          {camera.nvr_name && (
            <div className="flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-muted)" }} />
              <span className="truncate">{camera.nvr_name}{camera.nvr_model ? ` · ${camera.nvr_model}` : ""}</span>
            </div>
          )}
          {camera.channel_no && (
            <div className="flex items-center gap-1.5">
              <Signal className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-muted)" }} />
              <span>Kênh {camera.channel_no} · {TRANSPORT_LABELS[camera.transport]}</span>
            </div>
          )}
          <div className="flex items-center gap-1.5">
            <Settings className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-muted)" }} />
            <span>{MODE_LABELS[camera.mode]}</span>
          </div>
        </div>

        {/* Connection status */}
        <div
          className="flex items-center justify-between rounded-xl px-3 py-2"
          style={{ background: "var(--bg-surface-2)" }}
        >
          <div className="flex items-center gap-2">
            {connIcon}
            <ConnectionDot status={camera.last_connection_status} />
          </div>
          {camera.last_connected_at && (
            <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
              {formatDateTime(camera.last_connected_at)}
            </span>
          )}
        </div>

        {/* Error message */}
        {camera.last_error && (
          <p className="rounded-lg bg-red-50 px-2.5 py-1.5 text-xs text-red-600 dark:bg-red-500/10 dark:text-red-400">
            ⚠ {camera.last_error}
          </p>
        )}

        {/* Actions */}
        {canManage && (
          <div className="mt-auto flex gap-2 pt-1">
            <button
              onClick={() => onLive(camera)}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-sky-50 border border-sky-200 py-1.5 text-xs font-semibold text-sky-600 transition hover:bg-sky-100 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-400 dark:hover:bg-sky-500/20"
            >
              <MonitorPlay className="h-3.5 w-3.5" />
              Xem live
            </button>
            <button
              onClick={() => onEdit(camera)}
              className="flex items-center justify-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition hover:bg-slate-50 dark:hover:bg-slate-800"
              style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => onDelete(camera)}
              className="flex items-center justify-center gap-1.5 rounded-xl border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-500 transition hover:bg-red-50 dark:border-red-800 dark:hover:bg-red-500/10"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Camera form (dùng cho cả add và edit) ────────────────────────────────────
interface CameraFormData {
  camera_name: string;
  camera_position: string;
  nvr_name: string;
  nvr_model: string;
  channel_no: string;
  rtsp_url: string;
  preview_url: string;
  transport: "tcp" | "udp";
  mode: "anonymous" | "identified";
  status: CameraStatus;
}

const EMPTY_FORM: CameraFormData = {
  camera_name: "",
  camera_position: "",
  nvr_name: "",
  nvr_model: "",
  channel_no: "",
  rtsp_url: "",
  preview_url: "",
  transport: "tcp",
  mode: "anonymous",
  status: "active",
};

function cameraToForm(c: Camera): CameraFormData {
  return {
    camera_name: c.camera_name,
    camera_position: c.camera_position ?? "",
    nvr_name: c.nvr_name ?? "",
    nvr_model: c.nvr_model ?? "",
    channel_no: c.channel_no != null ? String(c.channel_no) : "",
    rtsp_url: "",           // không bao giờ hiển thị rtsp_url thật
    preview_url: c.preview_url ?? "",
    transport: c.transport,
    mode: c.mode,
    status: c.status,
  };
}

function formToPayload(f: CameraFormData): CameraCreatePayload {
  return {
    camera_name: f.camera_name.trim(),
    camera_position: f.camera_position.trim() || null,
    nvr_name: f.nvr_name.trim() || null,
    nvr_model: f.nvr_model.trim() || null,
    channel_no: f.channel_no ? parseInt(f.channel_no) : null,
    rtsp_url: f.rtsp_url.trim() || null,
    preview_url: f.preview_url.trim() || null,
    transport: f.transport,
    mode: f.mode,
    status: f.status,
  };
}

function CameraForm({
  data,
  onChange,
  isEdit,
}: {
  data: CameraFormData;
  onChange: (d: CameraFormData) => void;
  isEdit: boolean;
}) {
  const set = (key: keyof CameraFormData) => (e: React.ChangeEvent<HTMLInputElement>) =>
    onChange({ ...data, [key]: e.target.value });

  return (
    <div className="space-y-4">
      {/* Tên & Vị trí */}
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
            Tên camera <span className="text-red-500">*</span>
          </label>
          <Input
            value={data.camera_name}
            onChange={(e) => onChange({ ...data, camera_name: e.target.value })}
            placeholder="VD: Camera cửa vào"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
            Vị trí
          </label>
          <Input value={data.camera_position} onChange={set("camera_position")} placeholder="VD: Quầy thu ngân" />
        </div>
      </div>

      {/* NVR */}
      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>Tên NVR</label>
          <Input value={data.nvr_name} onChange={set("nvr_name")} placeholder="VD: NVR Phòng server" />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>Model NVR</label>
          <Input value={data.nvr_model} onChange={set("nvr_model")} placeholder="VD: Hikvision DS-7608" />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>Số kênh</label>
          <Input value={data.channel_no} onChange={set("channel_no")} placeholder="VD: 1" type="number" />
        </div>
      </div>

      {/* RTSP URL */}
      <div>
        <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
          RTSP URL {isEdit && <span className="font-normal text-amber-500">(để trống nếu không đổi)</span>}
        </label>
        <Input
          value={data.rtsp_url}
          onChange={set("rtsp_url")}
          placeholder="rtsp://user:pass@domain:554/channel/..."
          type="password"
        />
        <p className="mt-1 text-[11px]" style={{ color: "var(--text-muted)" }}>
          URL này được mã hóa, không hiển thị lại sau khi lưu.
        </p>
      </div>

      {/* Preview URL */}
      <div>
        <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
          Preview URL <span className="font-normal">(sub-stream, tùy chọn)</span>
        </label>
        <Input value={data.preview_url} onChange={set("preview_url")} placeholder="rtsp://...sub-stream..." />
      </div>

      {/* Transport / Mode / Status */}
      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>Transport</label>
          <Select
            value={data.transport}
            options={[
              { value: "tcp", label: "TCP (ổn định)" },
              { value: "udp", label: "UDP (latency thấp)" },
            ]}
            onChange={(v) => onChange({ ...data, transport: v as "tcp" | "udp" })}
            ariaLabel="Transport"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>Chế độ AI</label>
          <Select
            value={data.mode}
            options={[
              { value: "anonymous", label: "Ẩn danh" },
              { value: "identified", label: "Nhận diện" },
            ]}
            onChange={(v) => onChange({ ...data, mode: v as "anonymous" | "identified" })}
            ariaLabel="Mode"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-semibold" style={{ color: "var(--text-muted)" }}>Trạng thái</label>
          <Select
            value={data.status}
            options={[
              { value: "active",      label: "Hoạt động" },
              { value: "inactive",    label: "Tạm tắt" },
              { value: "maintenance", label: "Bảo trì" },
            ]}
            onChange={(v) => onChange({ ...data, status: v as CameraStatus })}
            ariaLabel="Status"
          />
        </div>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function CamerasPage() {
  const toast = useToast();
  const { hasPermission } = usePermission();
  const canManage = hasPermission("camera.manage");

  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);

  // Modal states
  const [addOpen, setAddOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Camera | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Camera | null>(null);
  const [liveTarget, setLiveTarget] = useState<Camera | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const [addForm, setAddForm] = useState<CameraFormData>(EMPTY_FORM);
  const [editForm, setEditForm] = useState<CameraFormData>(EMPTY_FORM);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getCameras();
      setCameras(data);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Không tải được danh sách camera");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Stats
  const activeCount = cameras.filter((c) => c.status === "active").length;
  const onlineCount = cameras.filter((c) => c.last_connection_status === "online").length;
  const errorCount = cameras.filter((c) => c.status === "error" || c.last_connection_status === "error").length;

  async function handleAdd() {
    if (!addForm.camera_name.trim()) { toast.error("Vui lòng nhập tên camera"); return; }
    setSaving(true);
    try {
      const created = await createCamera(formToPayload(addForm));
      setCameras((prev) => [created, ...prev]);
      toast.success(`Đã thêm camera "${created.camera_name}"`);
      setAddOpen(false);
      setAddForm(EMPTY_FORM);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Thêm camera thất bại");
    } finally { setSaving(false); }
  }

  async function handleEdit() {
    if (!editTarget) return;
    if (!editForm.camera_name.trim()) { toast.error("Vui lòng nhập tên camera"); return; }
    setSaving(true);
    try {
      const payload = formToPayload(editForm);
      // Không gửi rtsp_url nếu để trống (không muốn ghi đè)
      if (!payload.rtsp_url) delete payload.rtsp_url;
      const updated = await updateCamera(editTarget.id, payload);
      setCameras((prev) => prev.map((c) => c.id === updated.id ? updated : c));
      toast.success("Cập nhật camera thành công");
      setEditTarget(null);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Cập nhật thất bại");
    } finally { setSaving(false); }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleteLoading(true);
    try {
      await deleteCamera(deleteTarget.id);
      setCameras((prev) => prev.filter((c) => c.id !== deleteTarget.id));
      toast.success(`Đã xóa camera "${deleteTarget.camera_name}"`);
      setDeleteTarget(null);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Xóa thất bại");
    } finally { setDeleteLoading(false); }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="mb-1.5 inline-flex items-center gap-1.5 rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold text-sky-700 dark:bg-sky-900/30 dark:text-sky-400">
            <Cctv className="h-3 w-3" />
            Hệ thống camera
          </div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
            Quản lý Camera
          </h1>
          <p className="mt-0.5 text-sm" style={{ color: "var(--text-muted)" }}>
            Quản lý danh sách camera và cấu hình kết nối RTSP.
          </p>
        </div>
        {canManage && (
          <Button icon={<Plus className="h-4 w-4" />} onClick={() => { setAddForm(EMPTY_FORM); setAddOpen(true); }}>
            Thêm camera
          </Button>
        )}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Tổng camera", value: cameras.length, color: "text-sky-600 dark:text-sky-400", bg: "bg-sky-50 dark:bg-sky-500/10" },
          { label: "Đang hoạt động", value: activeCount, color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-500/10" },
          { label: "Có lỗi", value: errorCount, color: "text-red-600 dark:text-red-400", bg: "bg-red-50 dark:bg-red-500/10" },
        ].map((s) => (
          <div
            key={s.label}
            className="rounded-2xl p-4"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
          >
            <p className={`text-2xl font-black ${s.color}`}>{s.value}</p>
            <p className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>{s.label}</p>
          </div>
        ))}
      </div>

      {/* Camera grid */}
      {loading ? (
        <div className="flex min-h-[300px] items-center justify-center">
          <Loading text="Đang tải danh sách camera..." />
        </div>
      ) : cameras.length === 0 ? (
        <div
          className="flex min-h-[300px] flex-col items-center justify-center gap-4 rounded-2xl"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
        >
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-sky-50 dark:bg-sky-500/10">
            <Cctv className="h-7 w-7 text-sky-500" />
          </div>
          <div className="text-center">
            <p className="font-semibold" style={{ color: "var(--text-primary)" }}>Chưa có camera nào</p>
            <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
              Thêm camera để bắt đầu theo dõi
            </p>
          </div>
          {canManage && (
            <Button icon={<Plus className="h-4 w-4" />} onClick={() => setAddOpen(true)}>
              Thêm camera đầu tiên
            </Button>
          )}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {cameras.map((cam) => (
            <CameraCard
              key={cam.id}
              camera={cam}
              canManage={canManage}
              onEdit={(c) => { setEditTarget(c); setEditForm(cameraToForm(c)); }}
              onDelete={setDeleteTarget}
              onLive={setLiveTarget}
            />
          ))}
        </div>
      )}

      {/* Add Modal */}
      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Thêm camera mới"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setAddOpen(false)} disabled={saving}>Hủy</Button>
            <Button onClick={handleAdd} loading={saving}>Thêm camera</Button>
          </>
        }
      >
        <CameraForm data={addForm} onChange={setAddForm} isEdit={false} />
      </Modal>

      {/* Edit Modal */}
      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={`Sửa: ${editTarget?.camera_name}`}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditTarget(null)} disabled={saving}>Hủy</Button>
            <Button onClick={handleEdit} loading={saving}>Lưu thay đổi</Button>
          </>
        }
      >
        <CameraForm data={editForm} onChange={setEditForm} isEdit={true} />
      </Modal>

      {/* Delete Modal */}
      <Modal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="Xác nhận xóa camera"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)} disabled={deleteLoading}>Hủy</Button>
            <Button variant="danger" onClick={handleDelete} loading={deleteLoading}>Xóa camera</Button>
          </>
        }
      >
        <div className="flex flex-col items-center gap-3 py-2 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/20">
            <AlertTriangle className="h-6 w-6 text-red-500" />
          </div>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Xóa camera{" "}
            <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
              "{deleteTarget?.camera_name}"
            </span>
            ? Hành động này không thể hoàn tác.
          </p>
        </div>
      </Modal>

      {/* Live View Modal */}
      <Modal
        open={!!liveTarget}
        onClose={() => setLiveTarget(null)}
        title={
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
            <span>{liveTarget?.camera_name} — Live Stream</span>
          </div>
        }
        size="lg"
        footer={
          <Button variant="secondary" onClick={() => setLiveTarget(null)}>
            <X className="mr-1.5 h-4 w-4" /> Đóng
          </Button>
        }
      >
        {liveTarget && (
          <div className="space-y-3">
            {liveTarget.preview_url ? (
              <HLSPlayer
                src={liveTarget.preview_url}
                label={liveTarget.camera_name}
                autoPlay
              />
            ) : (
              <div className="flex flex-col items-center justify-center gap-3 rounded-xl bg-slate-900 py-16">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-800">
                  <MonitorPlay className="h-7 w-7 text-slate-500" />
                </div>
                <div className="text-center">
                  <p className="font-semibold text-white">Chưa có stream URL</p>
                  <p className="mt-1 text-sm text-slate-400">
                    Camera này chưa được cấu hình Preview URL (HLS).
                  </p>
                  <p className="mt-3 text-xs text-slate-500">
                    Cần cài MediaMTX trên server để convert RTSP → HLS,<br />
                    sau đó nhập HLS URL vào trường "Preview URL" của camera.
                  </p>
                </div>
                <button
                  onClick={() => { setLiveTarget(null); setEditTarget(liveTarget); setEditForm(cameraToForm(liveTarget)); }}
                  className="mt-1 flex items-center gap-1.5 rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-sky-700"
                >
                  <Pencil className="h-3.5 w-3.5" />
                  Cấu hình Preview URL
                </button>
              </div>
            )}

            {/* Camera info */}
            <div
              className="grid grid-cols-3 gap-2 rounded-xl p-3 text-xs"
              style={{ background: "var(--bg-surface-2)" }}
            >
              <div>
                <p style={{ color: "var(--text-muted)" }}>Vị trí</p>
                <p className="font-semibold" style={{ color: "var(--text-primary)" }}>
                  {liveTarget.camera_position ?? "—"}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-muted)" }}>Chế độ AI</p>
                <p className="font-semibold" style={{ color: "var(--text-primary)" }}>
                  {liveTarget.mode === "anonymous" ? "Ẩn danh" : "Nhận diện"}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--text-muted)" }}>Transport</p>
                <p className="font-semibold uppercase" style={{ color: "var(--text-primary)" }}>
                  {liveTarget.transport}
                </p>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
