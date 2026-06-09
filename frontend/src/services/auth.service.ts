import { delay } from "./api";
import { MOCK_USERS } from "@/mocks/users.mock";
import type { LoginRequest, LoginResponse } from "@/types/auth.type";
import { setToken, removeToken, USER_KEY } from "@/utils/storage";

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  await delay(600);

  // Tìm user trong mock (password không check — mock)
  const user = MOCK_USERS.find(
    (u) => u.username === payload.username && u.status === "active"
  );

  if (!user) {
    throw new Error("Tên đăng nhập hoặc mật khẩu không đúng");
  }

  const token = `mock_token_${user.id}_${Date.now()}`;

  const response: LoginResponse = {
    access_token: token,
    token_type: "bearer",
    user: {
      id: user.id,
      full_name: user.full_name,
      username: user.username,
      email: user.email,
      status: user.status,
      roles: user.roles.map((r) => r.role_code),
    },
  };

  setToken(token);
  if (typeof window !== "undefined") {
    localStorage.setItem(USER_KEY, JSON.stringify(response.user));
  }

  return response;

  // ── Khi có backend ──
  // return http.post<LoginResponse>("/auth/login", payload);
}

export async function logout(): Promise<void> {
  await delay(200);
  removeToken();
  // ── Khi có backend ──
  // await http.post("/auth/logout", {});
}

export function getCurrentUser() {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
