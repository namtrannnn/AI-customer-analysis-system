export type CameraSessionStatus = "CREATED" | "RUNNING" | "STOPPED" | "FAILED";

export interface RoiPoint {
  x: number;
  y: number;
}

export interface RoiPolygonConfig {
  zone_key: string;
  zone_name?: string | null;
  points: RoiPoint[];
}

export interface CameraSessionWebSocketEndpoints {
  ingest: string;
  events: string;
  debug_frame: string;
}

export interface CameraSessionResponse {
  stream_session_id: string;
  camera_id: number;
  source_type: "browser_webcam";
  status: CameraSessionStatus;
  target_fps: number;
  debug_enabled: boolean;
  debug_interval_ms: number;
  roi_count: number;
  current_count: number;
  active_track_count: number;
  started_at: string | null;
  stopped_at: string | null;
  failure_reason: string | null;
  ws_endpoints: CameraSessionWebSocketEndpoints;
}

export interface CameraSessionCreatePayload {
  camera_id: number;
  source_type: "browser_webcam";
  target_fps: number;
  debug_enabled: boolean;
  debug_interval_ms: number;
  roi_config: RoiPolygonConfig[];
}

export interface RealtimeTrackSnapshot {
  track_id: number;
  bbox: number[];
  centroid: number[];
  confidence: number | null;
  active_roi_ids: string[];
  last_seen_at: string | null;
}

export interface RealtimeEventEnvelope<T = unknown> {
  event_type: string;
  event_timestamp: string;
  session_id: string;
  payload: T;
}

export interface RealtimeStateSnapshotPayload {
  session_state: CameraSessionStatus;
  current_count: number;
  tracks: RealtimeTrackSnapshot[];
  roi_events: RealtimeEventEnvelope[];
  track_events: RealtimeEventEnvelope[];
}
