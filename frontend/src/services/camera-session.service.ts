import { http } from "@/lib/http";
import { getToken } from "@/utils/storage";
import type {
  CameraSessionCreatePayload,
  CameraSessionResponse,
} from "@/types/camera-session.type";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export async function createCameraSession(
  payload: CameraSessionCreatePayload,
): Promise<CameraSessionResponse> {
  return http.post<CameraSessionResponse>("/camera-sessions", payload);
}

export async function startCameraSession(
  sessionId: string,
): Promise<CameraSessionResponse> {
  return http.post<CameraSessionResponse>(`/camera-sessions/${sessionId}/start`);
}

export async function stopCameraSession(
  sessionId: string,
): Promise<CameraSessionResponse> {
  return http.post<CameraSessionResponse>(`/camera-sessions/${sessionId}/stop`);
}

export async function getCameraSession(
  sessionId: string,
): Promise<CameraSessionResponse> {
  return http.get<CameraSessionResponse>(`/camera-sessions/${sessionId}`);
}

export function buildCameraSessionWsUrl(
  relativePath: string,
  token = getToken(),
): string {
  const apiUrl = new URL(API_BASE_URL);
  const wsProtocol = apiUrl.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = new URL(relativePath, `${wsProtocol}//${apiUrl.host}`);

  if (token) {
    wsUrl.searchParams.set("token", token);
  }

  return wsUrl.toString();
}

export function createDefaultCenterRoi(
  width: number,
  height: number,
) {
  const marginX = width * 0.2;
  const marginY = height * 0.18;

  return [
    {
      zone_key: "center_zone",
      zone_name: "Trung tam",
      points: [
        { x: marginX, y: marginY },
        { x: width - marginX, y: marginY },
        { x: width - marginX, y: height - marginY },
        { x: marginX, y: height - marginY },
      ],
    },
  ];
}
