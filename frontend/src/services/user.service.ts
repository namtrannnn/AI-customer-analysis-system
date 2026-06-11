import { delay } from "./api";
import { MOCK_USERS, getNextUserId } from "@/mocks/users.mock";
import type {
  User,
  UserCreatePayload,
  UserUpdatePayload,
  UserFilterParams,
  UserRole,
} from "@/types/user.type";
import type { PaginatedResponse } from "@/types/customer.type";

let users: User[] = [...MOCK_USERS];

const MOCK_ROLE_MAP: Record<number, Omit<UserRole, "id" | "assigned_at">> = {
  1: {
    role_id: 1,
    role_code: "admin",
    role_name: "Quản trị viên",
  },
  2: {
    role_id: 2,
    role_code: "manager",
    role_name: "Quản lý",
  },
  3: {
    role_id: 3,
    role_code: "staff",
    role_name: "Nhân viên",
  },
};

function buildUserRoles(roleIds: number[] = []): UserRole[] {
  return roleIds
    .filter((roleId) => MOCK_ROLE_MAP[roleId])
    .map((roleId, index) => ({
      id: Date.now() + index,
      ...MOCK_ROLE_MAP[roleId],
      assigned_at: new Date().toISOString(),
    }));
}

export async function getUsers(
  params: UserFilterParams = {},
): Promise<PaginatedResponse<User>> {
  await delay();

  const { search = "", status = "", page = 1, limit = 10 } = params;

  let result = [...users];

  if (search.trim()) {
    const q = search.trim().toLowerCase();

    result = result.filter(
      (user) =>
        user.full_name.toLowerCase().includes(q) ||
        user.username.toLowerCase().includes(q) ||
        user.email?.toLowerCase().includes(q) ||
        user.phone?.toLowerCase().includes(q),
    );
  }

  if (status) {
    result = result.filter((user) => user.status === status);
  }

  result.sort(
    (a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  const total = result.length;
  const total_pages = Math.max(1, Math.ceil(total / limit));
  const safePage = Math.min(Math.max(page, 1), total_pages);

  const data = result.slice((safePage - 1) * limit, safePage * limit);

  return {
    data,
    total,
    page: safePage,
    limit,
    total_pages,
  };
}

export async function getUserById(id: number): Promise<User> {
  await delay();

  const found = users.find((user) => user.id === id);

  if (!found) {
    throw new Error("Không tìm thấy người dùng");
  }

  return { ...found };
}

export async function createUser(payload: UserCreatePayload): Promise<User> {
  await delay();

  const username = payload.username.trim();
  const email = payload.email?.trim();

  const existsUsername = users.find(
    (user) => user.username.toLowerCase() === username.toLowerCase(),
  );

  if (existsUsername) {
    throw new Error("Tên đăng nhập đã tồn tại");
  }

  if (email) {
    const existsEmail = users.find(
      (user) => user.email?.toLowerCase() === email.toLowerCase(),
    );

    if (existsEmail) {
      throw new Error("Email đã tồn tại");
    }
  }

  const newId = getNextUserId();

  const newUser: User = {
    id: newId,
    full_name: payload.full_name.trim(),
    username,
    email: email || null,
    phone: payload.phone?.trim() || null,
    status: payload.status ?? "active",
    avatar_url: `https://api.dicebear.com/7.x/personas/svg?seed=${username}`,
    last_login_at: null,
    created_at: new Date().toISOString(),
    updated_at: null,
    roles: buildUserRoles(payload.role_ids ?? []),
  };

  users = [newUser, ...users];

  return { ...newUser };
}

export async function updateUser(
  id: number,
  payload: UserUpdatePayload,
): Promise<User> {
  await delay();

  const idx = users.findIndex((user) => user.id === id);

  if (idx === -1) {
    throw new Error("Không tìm thấy người dùng");
  }

  const email = payload.email?.trim();

  if (email) {
    const existsEmail = users.find(
      (user) =>
        user.id !== id && user.email?.toLowerCase() === email.toLowerCase(),
    );

    if (existsEmail) {
      throw new Error("Email đã tồn tại");
    }
  }

  const updated: User = {
    ...users[idx],
    full_name: payload.full_name?.trim() ?? users[idx].full_name,
    email: email || null,
    phone: payload.phone?.trim() || null,
    status: payload.status ?? users[idx].status,
    roles:
      payload.role_ids !== undefined
        ? buildUserRoles(payload.role_ids)
        : users[idx].roles,
    updated_at: new Date().toISOString(),
  };

  users[idx] = updated;

  return { ...updated };
}

export async function deleteUser(id: number): Promise<void> {
  await delay();

  const idx = users.findIndex((user) => user.id === id);

  if (idx === -1) {
    throw new Error("Không tìm thấy người dùng");
  }

  users[idx] = {
    ...users[idx],
    status: "inactive",
    updated_at: new Date().toISOString(),
  };
}
