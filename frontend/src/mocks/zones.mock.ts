import type { StoreZone, MovementTrack, ZoneVisit } from "@/types/zone.type";

// ─── Store Zones ──────────────────────────────────────────────────────────────
export const MOCK_ZONES: StoreZone[] = [
  {
    id: 1,
    zone_name: "Lối vào chính",
    zone_type: "entrance",
    description: "Khu vực cửa ra vào chính của cửa hàng",
    polygon: [
      { x: 0.05, y: 0.1 },
      { x: 0.25, y: 0.1 },
      { x: 0.25, y: 0.4 },
      { x: 0.05, y: 0.4 },
    ],
    color: "#3b82f6",
    created_at: "2024-01-15T08:00:00Z",
    updated_at: null,
    total_visits: 245,
    avg_duration_seconds: 12,
  },
  {
    id: 2,
    zone_name: "Khu trưng bày A",
    zone_type: "display",
    description: "Kệ hàng điện tử",
    polygon: [
      { x: 0.3, y: 0.1 },
      { x: 0.6, y: 0.1 },
      { x: 0.6, y: 0.45 },
      { x: 0.3, y: 0.45 },
    ],
    color: "#10b981",
    created_at: "2024-01-15T08:00:00Z",
    updated_at: null,
    total_visits: 180,
    avg_duration_seconds: 95,
  },
  {
    id: 3,
    zone_name: "Khu trưng bày B",
    zone_type: "display",
    description: "Kệ hàng thời trang",
    polygon: [
      { x: 0.65, y: 0.1 },
      { x: 0.95, y: 0.1 },
      { x: 0.95, y: 0.45 },
      { x: 0.65, y: 0.45 },
    ],
    color: "#8b5cf6",
    created_at: "2024-01-16T08:00:00Z",
    updated_at: null,
    total_visits: 142,
    avg_duration_seconds: 78,
  },
  {
    id: 4,
    zone_name: "Quầy thanh toán",
    zone_type: "checkout",
    description: "Khu vực thu ngân",
    polygon: [
      { x: 0.3, y: 0.6 },
      { x: 0.7, y: 0.6 },
      { x: 0.7, y: 0.9 },
      { x: 0.3, y: 0.9 },
    ],
    color: "#f59e0b",
    created_at: "2024-01-15T08:00:00Z",
    updated_at: null,
    total_visits: 198,
    avg_duration_seconds: 145,
  },
];

// ─── Movement Tracks ──────────────────────────────────────────────────────────
const TRACK_COLORS = [
  "#3b82f6", "#ef4444", "#10b981", "#f59e0b",
  "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16",
];

function makeTrack(
  id: number,
  personId: number,
  anonId: string,
  points: { x: number; y: number; zone_id: number | null }[],
  baseTime: string,
  durationS: number,
): MovementTrack {
  const base = new Date(baseTime).getTime();
  const step = (durationS * 1000) / (points.length - 1 || 1);

  return {
    id,
    person_profile_id: personId,
    anonymous_id: anonId,
    visit_session_id: id + 100,
    color: TRACK_COLORS[id % TRACK_COLORS.length],
    entry_time: baseTime,
    exit_time: new Date(base + durationS * 1000).toISOString(),
    duration_seconds: durationS,
    zones_visited: [...new Set(points.map((p) => p.zone_id).filter(Boolean))] as number[],
    points: points.map((p, i) => ({
      x: p.x,
      y: p.y,
      zone_id: p.zone_id,
      timestamp: new Date(base + i * step).toISOString(),
    })),
  };
}

export const MOCK_TRACKS: MovementTrack[] = [
  makeTrack(1, 1, "ANON-00001", [
    { x: 0.12, y: 0.25, zone_id: 1 },
    { x: 0.20, y: 0.30, zone_id: 1 },
    { x: 0.35, y: 0.28, zone_id: 2 },
    { x: 0.45, y: 0.22, zone_id: 2 },
    { x: 0.50, y: 0.35, zone_id: 2 },
    { x: 0.55, y: 0.40, zone_id: 2 },
    { x: 0.48, y: 0.65, zone_id: 4 },
    { x: 0.50, y: 0.75, zone_id: 4 },
  ], "2024-06-09T09:05:00Z", 520),

  makeTrack(2, 2, "ANON-00002", [
    { x: 0.10, y: 0.20, zone_id: 1 },
    { x: 0.15, y: 0.35, zone_id: 1 },
    { x: 0.70, y: 0.25, zone_id: 3 },
    { x: 0.80, y: 0.30, zone_id: 3 },
    { x: 0.85, y: 0.40, zone_id: 3 },
    { x: 0.75, y: 0.38, zone_id: 3 },
    { x: 0.60, y: 0.65, zone_id: 4 },
    { x: 0.50, y: 0.75, zone_id: 4 },
  ], "2024-06-09T09:15:00Z", 680),

  makeTrack(3, 3, "KH-000001", [
    { x: 0.08, y: 0.22, zone_id: 1 },
    { x: 0.38, y: 0.20, zone_id: 2 },
    { x: 0.50, y: 0.25, zone_id: 2 },
    { x: 0.72, y: 0.22, zone_id: 3 },
    { x: 0.88, y: 0.35, zone_id: 3 },
    { x: 0.82, y: 0.28, zone_id: 3 },
    { x: 0.55, y: 0.62, zone_id: 4 },
    { x: 0.50, y: 0.78, zone_id: 4 },
  ], "2024-06-09T09:30:00Z", 740),

  makeTrack(4, 4, "ANON-00003", [
    { x: 0.12, y: 0.28, zone_id: 1 },
    { x: 0.18, y: 0.32, zone_id: 1 },
    { x: 0.35, y: 0.35, zone_id: 2 },
    { x: 0.42, y: 0.38, zone_id: 2 },
    { x: 0.40, y: 0.68, zone_id: 4 },
  ], "2024-06-09T10:00:00Z", 280),

  makeTrack(5, 5, "KH-000005", [
    { x: 0.10, y: 0.25, zone_id: 1 },
    { x: 0.72, y: 0.28, zone_id: 3 },
    { x: 0.82, y: 0.38, zone_id: 3 },
    { x: 0.68, y: 0.42, zone_id: 3 },
    { x: 0.35, y: 0.25, zone_id: 2 },
    { x: 0.45, y: 0.32, zone_id: 2 },
    { x: 0.50, y: 0.70, zone_id: 4 },
    { x: 0.50, y: 0.82, zone_id: 4 },
  ], "2024-06-09T10:30:00Z", 960),
];

// ─── Zone Visits ──────────────────────────────────────────────────────────────
export const MOCK_ZONE_VISITS: ZoneVisit[] = [
  { id: 1,  zone_id: 1, zone_name: "Lối vào chính",   person_profile_id: 1, anonymous_id: "ANON-00001", enter_time: "2024-06-09T09:05:00Z", leave_time: "2024-06-09T09:06:00Z", duration_seconds: 12 },
  { id: 2,  zone_id: 2, zone_name: "Khu trưng bày A", person_profile_id: 1, anonymous_id: "ANON-00001", enter_time: "2024-06-09T09:06:30Z", leave_time: "2024-06-09T09:12:00Z", duration_seconds: 330 },
  { id: 3,  zone_id: 4, zone_name: "Quầy thanh toán", person_profile_id: 1, anonymous_id: "ANON-00001", enter_time: "2024-06-09T09:12:00Z", leave_time: "2024-06-09T09:14:00Z", duration_seconds: 120 },
  { id: 4,  zone_id: 1, zone_name: "Lối vào chính",   person_profile_id: 2, anonymous_id: "ANON-00002", enter_time: "2024-06-09T09:15:00Z", leave_time: "2024-06-09T09:16:00Z", duration_seconds: 15 },
  { id: 5,  zone_id: 3, zone_name: "Khu trưng bày B", person_profile_id: 2, anonymous_id: "ANON-00002", enter_time: "2024-06-09T09:16:30Z", leave_time: "2024-06-09T09:24:00Z", duration_seconds: 450 },
  { id: 6,  zone_id: 4, zone_name: "Quầy thanh toán", person_profile_id: 2, anonymous_id: "ANON-00002", enter_time: "2024-06-09T09:24:00Z", leave_time: "2024-06-09T09:27:00Z", duration_seconds: 180 },
];

// ─── Counter ──────────────────────────────────────────────────────────────────
let zoneIdCounter = MOCK_ZONES.length + 1;
export function getNextZoneId(): number {
  return zoneIdCounter++;
}
