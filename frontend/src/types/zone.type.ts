// ─── Point / Polygon ──────────────────────────────────────────────────────────
/** Tọa độ tương đối (0–1) so với kích thước ảnh nền */
export interface Point {
  x: number; // 0..1
  y: number; // 0..1
}

export type ZoneType =
  | "entrance"      // Lối vào
  | "checkout"      // Quầy thanh toán
  | "display"       // Khu trưng bày
  | "fitting_room"  // Phòng thử đồ
  | "promotion"     // Khu khuyến mãi
  | "other";        // Khác

export const ZONE_TYPE_LABELS: Record<ZoneType, string> = {
  entrance:     "Lối vào",
  checkout:     "Quầy thanh toán",
  display:      "Khu trưng bày",
  fitting_room: "Phòng thử đồ",
  promotion:    "Khu khuyến mãi",
  other:        "Khác",
};

// ─── Store Zone ───────────────────────────────────────────────────────────────
export interface StoreZone {
  id: number;
  zone_name: string;
  zone_type: ZoneType;
  description: string | null;
  /** Polygon points (relative 0–1) */
  polygon: Point[];
  color: string; // hex e.g. "#3b82f6"
  created_at: string;
  updated_at: string | null;
  // Stats
  total_visits: number;
  avg_duration_seconds: number | null;
}

export interface ZoneCreatePayload {
  zone_name: string;
  zone_type: ZoneType;
  description?: string;
  polygon: Point[];
  color: string;
}

export interface ZoneUpdatePayload extends Partial<ZoneCreatePayload> {}

// ─── ROI (Region of Interest) ─────────────────────────────────────────────────
export interface ROI {
  zone_id: number;
  polygon: Point[];
}

// ─── Movement Track ───────────────────────────────────────────────────────────
export interface TrackPoint {
  x: number;       // relative 0–1
  y: number;       // relative 0–1
  tracked_at: string; // ISO timestamp — khớp với BE field name
  zone_id: number | null;
}

export interface MovementTrack {
  id: number;
  person_profile_id: number;
  anonymous_id: string;
  visit_session_id: number;
  color: string;
  points: TrackPoint[];
  entry_time: string;
  exit_time: string | null;
  duration_seconds: number | null;
  zones_visited: number[];
  customer_id?: number | null;
  customer_name?: string | null;
  customer_avatar?: string | null;
  face_image_url?: string | null;
}

// ─── Zone Visit ───────────────────────────────────────────────────────────────
export interface ZoneVisit {
  id: number;
  zone_id: number;
  zone_name: string;
  person_profile_id: number;
  anonymous_id: string;
  enter_time: string;
  leave_time: string | null;
  duration_seconds: number | null;
}

// ─── Filter ───────────────────────────────────────────────────────────────────
export interface TrackFilterParams {
  person_id?: string;
  zone_id?: number | "";
  date?: string;
  start_time?: string;
  end_time?: string;
  duration?: "all" | "short" | "medium" | "long";
}

export const ZONE_COLORS = [
  "#3b82f6", // blue
  "#10b981", // emerald
  "#f59e0b", // amber
  "#ef4444", // red
  "#8b5cf6", // violet
  "#06b6d4", // cyan
  "#ec4899", // pink
  "#84cc16", // lime
];


// ─── Heatmap Types (PB07) ─────────────────────────────────────────────────────
export interface ZoneHeatmapItem {
  zone_id: number;
  zone_name: string;
  zone_type: ZoneType;
  polygon: Point[];
  color: string;
  total_visits: number;
  total_duration: number;
  intensity: number; // 0..100%
}

export interface ZoneHeatmapResponse {
  items: ZoneHeatmapItem[];
  max_duration: number;
  total_visits_sum: number;
}

export interface ZoneHeatmapFilters {
  start_date?: string;
  end_date?: string;
}

