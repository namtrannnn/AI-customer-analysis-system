import { http } from "@/lib/http";

import type {
  LoginRequest,
  LoginResponse,
  ChangePasswordRequest,
  AuthUser,
} from "@/types/auth.type";
import { setToken, removeToken, USER_KEY } from "@/utils/storage";

// export async function login(payload: LoginRequest): Promise<LoginResponse> {
//   const response = await http.post<LoginResponse>("/auth/login", payload);

//   setToken(response.access_token);

//   if (typeof window !== "undefined") {
//     localStorage.setItem(USER_KEY, JSON.stringify(response.user_info));
//   }

//   return response;
// }

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  const response = await http.post<LoginResponse>("/auth/login", payload);

  console.log("LOGIN RESPONSE:", response);
  console.log("USER INFO:", response.user_info);
  console.log("USER PERMISSIONS:", response.user_info?.permissions);

  setToken(response.access_token);

  if (typeof window !== "undefined") {
    localStorage.setItem(USER_KEY, JSON.stringify(response.user_info));
  }

  return response;
}

export async function changePassword(
  payload: ChangePasswordRequest,
): Promise<void> {
  await http.post<null>("/auth/change-password", payload);
}

export async function logout(): Promise<void> {
  try {
    await http.post<null>("/auth/logout", {});
  } catch {
    // BE logout hiện tại chưa xử lý blacklist token nên lỗi cũng vẫn cho FE logout local
  } finally {
    removeToken();

    if (typeof window !== "undefined") {
      localStorage.removeItem(USER_KEY);
    }
  }
}

export function getCurrentUser(): AuthUser | null {
  if (typeof window === "undefined") return null;

  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
