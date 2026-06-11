import { http } from "@/lib/http";
import type {
  User,
  UserCreatePayload,
  UserCreateResponse,
  UserUpdatePayload,
  UserFilterParams,
} from "@/types/user.type";
import type { PaginatedResponse } from "@/types/customer.type";

// ─── List users: search + filter + pagination ────────────────────────────────
export async function getUsers(
  params: UserFilterParams = {},
): Promise<PaginatedResponse<User>> {
  const { page = 1, limit = 10, search = "", status = "" } = params;

  const keyword = search.trim();
  const skip = (page - 1) * limit;

  const response = await http.raw.get("/users/", {
    params: {
      q: keyword || undefined,
      status: status || undefined,
      skip,
      limit,
    },
  });

  const json = response.data;

  const data: User[] = Array.isArray(json.data) ? json.data : [];
  const total = json.total ?? json.meta?.total ?? data.length;

  return {
    data,
    total,
    page,
    limit,
    total_pages: Math.max(1, Math.ceil(total / limit)),
  };
}

// ─── Get by ID ────────────────────────────────────────────────────────────────
export async function getUserById(id: number): Promise<User> {
  return http.get<User>(`/users/${id}`);
}

// ─── Create ───────────────────────────────────────────────────────────────────
// BE tự sinh username + temporary_password
export async function createUser(
  payload: UserCreatePayload,
): Promise<UserCreateResponse> {
  return http.post<UserCreateResponse>("/users/", payload);
}

// ─── Update ───────────────────────────────────────────────────────────────────
export async function updateUser(
  id: number,
  payload: UserUpdatePayload,
): Promise<User> {
  return http.patch<User>(`/users/${id}`, payload);
}

// ─── Soft delete ──────────────────────────────────────────────────────────────
export async function deleteUser(id: number): Promise<null> {
  return http.delete<null>(`/users/${id}`);
}

// ─── Upload avatar ────────────────────────────────────────────────────────────
export async function uploadUserAvatar(
  userId: number,
  file: File,
): Promise<User> {
  const formData = new FormData();
  formData.append("file", file);

  return http.post<User>(`/users/${userId}/avatar`, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
}
