/**
 * Zone Service — kết nối BE thật
 * API: /api/zones, /api/tracks
 */

import { http } from "@/lib/http";
import type {
  StoreZone,
  ZoneCreatePayload,
  ZoneUpdatePayload,
  MovementTrack,
  ZoneVisit,
  TrackFilterParams,
} from "@/types/zone.type";

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
  const query = new URLSearchParams();
  if (params.person_id?.trim()) query.set("person_id", params.person_id.trim());
  if (params.zone_id) query.set("zone_id", String(params.zone_id));

  const qs = query.toString();
  return http.get<MovementTrack[]>(`/tracks${qs ? `?${qs}` : ""}`);
}

export async function getTrackById(sessionId: number): Promise<MovementTrack> {
  return http.get<MovementTrack>(`/tracks/${sessionId}`);
}

// ─── Zone Visits ──────────────────────────────────────────────────────────────

export async function getZoneVisits(zoneId?: number): Promise<ZoneVisit[]> {
  if (zoneId) return http.get<ZoneVisit[]>(`/zones/${zoneId}/visits`);
  return [];
}
