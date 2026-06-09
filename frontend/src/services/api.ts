// ─── Base API helper ──────────────────────────────────────────────────────────
// Hiện tại dùng mock data. Khi có backend thật, chỉ cần thay BASE_URL
// và uncomment các fetch call bên dưới.

export const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// Simulate network delay (ms) — xóa khi dùng API thật
const FAKE_DELAY = 400;

export function delay(ms = FAKE_DELAY): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ─── Standard API response shape (khớp với backend FastAPI) ──────────────────
export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

export interface ApiError {
  success: false;
  message: string;
  errors?: Record<string, string[]>;
}

// ─── HTTP client (dùng khi có backend) ───────────────────────────────────────
async function request<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const res = await fetch(`${BASE_URL}${endpoint}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const error: ApiError = await res.json().catch(() => ({
      success: false,
      message: `HTTP ${res.status}: ${res.statusText}`,
    }));
    throw new Error(error.message ?? "Có lỗi xảy ra");
  }

  const body: ApiResponse<T> = await res.json();
  return body.data;
}

export const http = {
  get: <T>(url: string) => request<T>(url),
  post: <T>(url: string, body: unknown) =>
    request<T>(url, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(url: string, body: unknown) =>
    request<T>(url, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(url: string, body: unknown) =>
    request<T>(url, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(url: string) => request<T>(url, { method: "DELETE" }),
};
