import { http } from "@/lib/http";
import type {
  Role,
  RoleCreatePayload,
  RoleUpdatePayload,
  RoleFilterParams,
} from "@/types/role.type";
import type {
  Permission,
  RolePermissionMatrix,
  UpdateRolePermissionsPayload,
  PermissionsByModule,
} from "@/types/permission.type";
import type { PaginatedResponse } from "@/types/customer.type";

// ─── List roles: search + pagination ─────────────────────────────────────────
// BE: GET /roles/full-details?q=&skip=&limit=
export async function getRoles(
  params: RoleFilterParams = {},
): Promise<PaginatedResponse<Role>> {
  const { page = 1, limit = 10, search = "" } = params;

  const keyword = search.trim();
  const skip = (page - 1) * limit;

  const response = await http.raw.get("/roles/full-details", {
    params: {
      q: keyword || undefined,
      skip,
      limit,
    },
  });

  const json = response.data;

  const data: Role[] = Array.isArray(json.data) ? json.data : [];
  const total = json.total ?? json.meta?.total ?? data.length;

  return {
    data,
    total,
    page,
    limit,
    total_pages: Math.max(1, Math.ceil(total / limit)),
  };
}

// ─── Get by ID ───────────────────────────────────────────────────────────────
// BE: GET /roles/{role_id}
export async function getRoleById(id: number): Promise<Role> {
  return http.get<Role>(`/roles/${id}`);
}

// ─── Create ──────────────────────────────────────────────────────────────────
// BE: POST /roles/
export async function createRole(payload: RoleCreatePayload): Promise<Role> {
  return http.post<Role>("/roles/", {
    role_code: payload.role_code.trim().toLowerCase(),
    role_name: payload.role_name.trim(),
    description: payload.description?.trim() || null,
    permission_ids: payload.permission_ids ?? [],
  });
}

// ─── Update ──────────────────────────────────────────────────────────────────
// BE: PATCH /roles/{role_id}
export async function updateRole(
  id: number,
  payload: RoleUpdatePayload,
): Promise<Role> {
  return http.patch<Role>(`/roles/${id}`, {
    role_code: payload.role_code?.trim().toLowerCase(),
    role_name: payload.role_name?.trim(),
    description:
      payload.description !== undefined
        ? payload.description?.trim() || null
        : undefined,
    permission_ids: payload.permission_ids,
  });
}

// ─── Delete ──────────────────────────────────────────────────────────────────
// BE: DELETE /roles/{role_id}
export async function deleteRole(id: number): Promise<null> {
  return http.delete<null>(`/roles/${id}`);
}

// ─── Permissions: gọi API thật từ BE ─────────────────────────────────────────
// BE: GET /permissions/
export async function getAllPermissions(): Promise<Permission[]> {
  const response = await http.raw.get("/permissions/");
  const json = response.data;

  return Array.isArray(json.data) ? json.data : [];
}

export async function getPermissionsByModule(): Promise<PermissionsByModule> {
  const permissions = await getAllPermissions();

  return permissions.reduce<PermissionsByModule>((acc, permission) => {
    const moduleKey = permission.module_name || "Khác";

    if (!acc[moduleKey]) acc[moduleKey] = [];
    acc[moduleKey].push(permission);

    return acc;
  }, {});
}

// ─── Role-Permission Matrix: build từ Role API thật ──────────────────────────
export async function getRolePermissionMatrix(): Promise<
  RolePermissionMatrix[]
> {
  const response = await getRoles({
    page: 1,
    limit: 1000,
  });

  return response.data.map((role) => ({
    role: {
      id: role.id,
      role_code: role.role_code,
      role_name: role.role_name,
    },
    permission_ids:
      role.permissions?.map((permission) => permission.id) ??
      role.permission_ids ??
      [],
  }));
}

// BE chưa có API riêng update role-permissions,
// nên dùng PATCH /roles/{id} với permission_ids
export async function updateRolePermissions(
  payload: UpdateRolePermissionsPayload,
): Promise<void> {
  await updateRole(payload.role_id, {
    permission_ids: payload.permission_ids,
  });
}

export async function getRolePermissions(roleId: number): Promise<number[]> {
  const role = await getRoleById(roleId);

  return (
    role.permission_ids ??
    role.permissions?.map((permission) => permission.id) ??
    []
  );
}
