import { http } from "@/lib/http";
import type { Camera, CameraCreatePayload, CameraUpdatePayload } from "@/types/camera.type";

export async function getCameras(): Promise<Camera[]> {
  return http.get<Camera[]>("/cameras/");
}

export async function getCameraById(id: number): Promise<Camera> {
  return http.get<Camera>(`/cameras/${id}`);
}

export async function createCamera(payload: CameraCreatePayload): Promise<Camera> {
  return http.post<Camera>("/cameras/", payload);
}

export async function updateCamera(id: number, payload: CameraUpdatePayload): Promise<Camera> {
  return http.patch<Camera>(`/cameras/${id}`, payload);
}

export async function deleteCamera(id: number): Promise<void> {
  return http.delete(`/cameras/${id}`);
}
