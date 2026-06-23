/**
 * Zone Service
 * USE_MOCK = true  → dùng mock data (test UI, không cần BE/DB)
 * USE_MOCK = false → gọi BE thật
 */

import { http } from "@/lib/http";
import {
  MOCK_TRACKS,
  MOCK_ZONE_VISITS,
  MOCK_ZONES,
} from "@/mocks/zones.mock";
import type {
  StoreZone,
  ZoneCreatePayload,
  ZoneUpdatePayload,
  MovementTrack,
  ZoneVisit,
  TrackFilterParams,
} from "@/types/zone.type";

// ─── Toggle ở đây ─────────────────────────────────────────────────────────────
// true  = dùng mock (test UI không cần DB tracking)
// false = gọi BE thật
const USE_MOCK_TRACKS = false;

const delay = (ms = 400) => new Promise<void>((r) => setTimeout(r, ms));

// ─── Zone CRUD ────────────────────────────────────────────────────────────────

export async function getZones(): Promise<StoreZone[]> {
  return http.get<StoreZone[]>("/zones");
}

export async function getZoneById(id: number): Promise<StoreZone> {
  return http.get<StoreZone>(`/zones/${id}`);
}

export async function createZone(payload: ZoneCreatePayload): Promise<StoreZone> {
  return http.post<StoreZone>("/zones", payload);
}

export async function updateZone(id: number, payload: ZoneUpdatePayload): Promise<StoreZone> {
  return http.patch<StoreZone>(`/zones/${id}`, payload);
}

export async function deleteZone(id: number): Promise<void> {
  return http.delete(`/zones/${id}`);
}

// ─── Check point (AI-11 debug / test trực tiếp UI) ───────────────────────────

export interface CheckPointResult {
  x: number;
  y: number;
  zone_id: number | null;
  zone_name: string | null;
  zone_type: string | null;
  color: string | null;
  is_inside: boolean;
}

export async function checkPoint(x: number, y: number): Promise<CheckPointResult> {
  return http.post<CheckPointResult>("/zones/check-point", { x, y });
}

// ─── Movement Tracks ──────────────────────────────────────────────────────────

export async function getMovementTracks(
  params: TrackFilterParams = {}
): Promise<MovementTrack[]> {
  if (USE_MOCK_TRACKS) {
    await delay(500);
    let result = [...MOCK_TRACKS];

    if (params.person_id?.trim()) {
      const q = params.person_id.toLowerCase();
      result = result.filter((t) =>
        t.anonymous_id.toLowerCase().includes(q)
      );
    }
    if (params.zone_id) {
      result = result.filter((t) =>
        t.zones_visited.includes(Number(params.zone_id))
      );
    }
    return result;
  }

  const query = new URLSearchParams();
  if (params.person_id?.trim()) query.set("person_id", params.person_id.trim());
  if (params.zone_id) query.set("zone_id", String(params.zone_id));
  const qs = query.toString();
  return http.get<MovementTrack[]>(`/tracks${qs ? `?${qs}` : ""}`);
}

export async function getTrackById(sessionId: number): Promise<MovementTrack> {
  if (USE_MOCK_TRACKS) {
    await delay(300);
    const t = MOCK_TRACKS.find((t) => t.id === sessionId);
    if (!t) throw new Error("Không tìm thấy track");
    return { ...t };
  }
  return http.get<MovementTrack>(`/tracks/${sessionId}`);
}

// ─── Zone Visits ──────────────────────────────────────────────────────────────

export async function getZoneVisits(zoneId?: number): Promise<ZoneVisit[]> {
  if (USE_MOCK_TRACKS) {
    await delay(300);
    if (zoneId) return MOCK_ZONE_VISITS.filter((v) => v.zone_id === zoneId);
    return [...MOCK_ZONE_VISITS];
  }
  if (zoneId) return http.get<ZoneVisit[]>(`/zones/${zoneId}/visits`);
  return [];
}
