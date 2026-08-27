export type CameraStatus = "active" | "inactive" | "maintenance" | "error";
export type CameraMode = "anonymous" | "identified";
export type CameraTransport = "tcp" | "udp";
export type ConnectionStatus = "online" | "offline" | "reconnecting" | "error";

export interface Camera {
  id: number;
  camera_name: string;
  camera_position: string | null;
  nvr_name: string | null;
  nvr_model: string | null;
  channel_no: number | null;
  // rtsp_url KHÔNG có trong response — BE không trả ra
  preview_url: string | null;
  transport: CameraTransport;
  mode: CameraMode;
  status: CameraStatus;
  last_connection_status: ConnectionStatus | null;
  last_connected_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface CameraCreatePayload {
  camera_name: string;
  camera_position?: string | null;
  nvr_name?: string | null;
  nvr_model?: string | null;
  channel_no?: number | null;
  rtsp_url?: string | null;
  preview_url?: string | null;
  transport?: CameraTransport;
  mode?: CameraMode;
  status?: CameraStatus;
}

export interface CameraUpdatePayload extends Partial<CameraCreatePayload> {}

export const CAMERA_STATUS_CONFIG: Record<CameraStatus, { label: string; color: string; bg: string }> = {
  active:      { label: "Hoạt động",    color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-500/10" },
  inactive:    { label: "Tạm tắt",      color: "text-slate-500 dark:text-slate-400",     bg: "bg-slate-100 dark:bg-slate-700/40" },
  maintenance: { label: "Bảo trì",      color: "text-amber-600 dark:text-amber-400",     bg: "bg-amber-50 dark:bg-amber-500/10" },
  error:       { label: "Lỗi",          color: "text-red-600 dark:text-red-400",         bg: "bg-red-50 dark:bg-red-500/10" },
};

export const CONNECTION_STATUS_CONFIG: Record<ConnectionStatus, { label: string; dot: string }> = {
  online:       { label: "Online",        dot: "bg-emerald-500" },
  offline:      { label: "Offline",       dot: "bg-slate-400" },
  reconnecting: { label: "Đang kết nối",  dot: "bg-amber-500 animate-pulse" },
  error:        { label: "Lỗi kết nối",   dot: "bg-red-500" },
};

export const MODE_LABELS: Record<CameraMode, string> = {
  anonymous:  "Ẩn danh",
  identified: "Nhận diện",
};

export const TRANSPORT_LABELS: Record<CameraTransport, string> = {
  tcp: "TCP (ổn định)",
  udp: "UDP (latency thấp)",
};
