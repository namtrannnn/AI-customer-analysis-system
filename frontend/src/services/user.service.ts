import { delay } from "./api";
import { MOCK_USERS, getNextUserId } from "@/mocks/users.mock";
import type {
  User,
  UserCreatePayload,
  UserUpdatePayload,
  UserFilterParams,
} from "@/types/user.type";
import type { PaginatedResponse } from "@/types/customer.type";

let users: User[] = [...MOCK_USERS];

export async function getUsers(
  params: UserFilterParams = {}
): Promise<PaginatedResponse<User>> {
  await delay();
  const { search = "", status = "", page = 1, limit = 10 } = params;

  let result = [...users];

  if (search.trim()) {
    const q = search.toLowerCase();
    result = result.filter(
      (u) =>
        u.full_name.toLowerCase().includes(q) ||
        u.username.toLowerCase().includes(q) ||
        u.email?.toLowerCase().includes(q)
    );
  }

  if (status) result = result.filter((u) => u.status === status);

  result.sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  const total = result.length;
  const total_pages = Math.ceil(total / limit);
  const data = result.slice((page - 1) * limit, page * limit);

  return { data, total, page, limit, total_pages };
}

export async function getUserById(id: number): Promise<User> {
  await delay();
  const found = users.find((u) => u.id === id);
  if (!found) throw new Error("Không tìm thấy người dùng");
  return { ...found };
}

export async function createUser(payload: UserCreatePayload): Promise<User> {
  await delay();

  const existsUsername = users.find((u) => u.username === payload.username);
  if (existsUsername) throw new Error("Tên đăng nhập đã tồn tại");

  const newId = getNextUserId();
  const newUser: User = {
    id: newId,
    full_name: payload.full_name,
    username: payload.username,
    email: payload.email ?? null,
    phone: payload.phone ?? null,
    status: payload.status ?? "active",
    avatar_url: `https://api.dicebear.com/7.x/personas/svg?seed=${payload.username}`,
    last_login_at: null,
    created_at: new Date().toISOString(),
    updated_at: null,
    roles: [],
  };

  users = [newUser, ...users];
  return { ...newUser };
}

export async function updateUser(
  id: number,
  payload: UserUpdatePayload
): Promise<User> {
  await delay();

  const idx = users.findIndex((u) => u.id === id);
  if (idx === -1) throw new Error("Không tìm thấy người dùng");

  const updated: User = {
    ...users[idx],
    ...payload,
    updated_at: new Date().toISOString(),
  };

  users[idx] = updated;
  return { ...updated };
}

export async function deleteUser(id: number): Promise<void> {
  await delay();
  const idx = users.findIndex((u) => u.id === id);
  if (idx === -1) throw new Error("Không tìm thấy người dùng");

  users[idx] = {
    ...users[idx],
    status: "inactive",
    updated_at: new Date().toISOString(),
  };
}
