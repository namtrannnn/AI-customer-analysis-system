import { delay } from "./api";
import {
  MOCK_ROLES,
  MOCK_PERMISSIONS,
  MOCK_ROLE_PERMISSIONS,
  MOCK_ROLE_PERMISSION_MATRIX,
  getNextRoleId,
} from "@/mocks/roles.mock";
import type { Role, RoleCreatePayload, RoleUpdatePayload, RoleFilterParams } from "@/types/role.type";
import type { Permission, RolePermissionMatrix, UpdateRolePermissionsPayload, PermissionsByModule } from "@/types/permission.type";
import type { PaginatedResponse } from "@/types/customer.type";

let roles: Role[] = [...MOCK_ROLES];
let rolePermissions: Record<number, number[]> = { ...MOCK_ROLE_PERMISSIONS };
let matrix: RolePermissionMatrix[] = [...MOCK_ROLE_PERMISSION_MATRIX];

// ─── Roles ────────────────────────────────────────────────────────────────────
export async function getRoles(
  params: RoleFilterParams = {}
): Promise<PaginatedResponse<Role>> {
  await delay();
  const { search = "", page = 1, limit = 10 } = params;

  let result = [...roles];

  if (search.trim()) {
    const q = search.toLowerCase();
    result = result.filter(
      (r) =>
        r.role_name.toLowerCase().includes(q) ||
        r.role_code.toLowerCase().includes(q)
    );
  }

  const total = result.length;
  const total_pages = Math.ceil(total / limit);
  const data = result.slice((page - 1) * limit, page * limit);

  return { data, total, page, limit, total_pages };
}

export async function getRoleById(id: number): Promise<Role> {
  await delay();
  const found = roles.find((r) => r.id === id);
  if (!found) throw new Error("Không tìm thấy nhóm quyền");
  return { ...found };
}

export async function createRole(payload: RoleCreatePayload): Promise<Role> {
  await delay();

  const exists = roles.find(
    (r) => r.role_code.toUpperCase() === payload.role_code.toUpperCase()
  );
  if (exists) throw new Error("Mã nhóm quyền đã tồn tại");

  const newId = getNextRoleId();
  const newRole: Role = {
    id: newId,
    role_code: payload.role_code.toUpperCase(),
    role_name: payload.role_name,
    description: payload.description ?? null,
    created_at: new Date().toISOString(),
    permission_count: payload.permission_ids?.length ?? 0,
    user_count: 0,
  };

  roles = [newRole, ...roles];
  rolePermissions[newId] = payload.permission_ids ?? [];

  return { ...newRole };
}

export async function updateRole(
  id: number,
  payload: RoleUpdatePayload
): Promise<Role> {
  await delay();

  const idx = roles.findIndex((r) => r.id === id);
  if (idx === -1) throw new Error("Không tìm thấy nhóm quyền");

  const updated: Role = {
    ...roles[idx],
    ...payload,
    permission_count:
      payload.permission_ids?.length ?? roles[idx].permission_count,
  };

  roles[idx] = updated;
  if (payload.permission_ids) {
    rolePermissions[id] = payload.permission_ids;
  }

  return { ...updated };
}

export async function deleteRole(id: number): Promise<void> {
  await delay();
  const idx = roles.findIndex((r) => r.id === id);
  if (idx === -1) throw new Error("Không tìm thấy nhóm quyền");
  roles = roles.filter((r) => r.id !== id);
  delete rolePermissions[id];
}

// ─── Permissions ──────────────────────────────────────────────────────────────
export async function getAllPermissions(): Promise<Permission[]> {
  await delay();
  return [...MOCK_PERMISSIONS];
}

export async function getPermissionsByModule(): Promise<PermissionsByModule> {
  await delay();
  return MOCK_PERMISSIONS.reduce<PermissionsByModule>((acc, p) => {
    if (!acc[p.module_name]) acc[p.module_name] = [];
    acc[p.module_name].push(p);
    return acc;
  }, {});
}

// ─── Role-Permission Matrix ───────────────────────────────────────────────────
export async function getRolePermissionMatrix(): Promise<RolePermissionMatrix[]> {
  await delay();
  // Rebuild từ state hiện tại
  return roles.map((r) => ({
    role: { id: r.id, role_code: r.role_code, role_name: r.role_name },
    permission_ids: rolePermissions[r.id] ?? [],
  }));
}

export async function updateRolePermissions(
  payload: UpdateRolePermissionsPayload
): Promise<void> {
  await delay();

  const idx = roles.findIndex((r) => r.id === payload.role_id);
  if (idx === -1) throw new Error("Không tìm thấy nhóm quyền");

  rolePermissions[payload.role_id] = payload.permission_ids;
  roles[idx] = {
    ...roles[idx],
    permission_count: payload.permission_ids.length,
  };

  // Sync matrix
  const matrixIdx = matrix.findIndex((m) => m.role.id === payload.role_id);
  if (matrixIdx !== -1) {
    matrix[matrixIdx] = {
      ...matrix[matrixIdx],
      permission_ids: payload.permission_ids,
    };
  }
}

export async function getRolePermissions(roleId: number): Promise<number[]> {
  await delay();
  return rolePermissions[roleId] ?? [];
}
