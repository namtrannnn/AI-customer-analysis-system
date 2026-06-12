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

// ─── Mock Permissions tạm thời vì BE chưa có Permission API ───────────────────
const MOCK_PERMISSIONS: Permission[] = [
  {
    id: 1,
    permission_code: "dashboard.view",
    permission_name: "Xem dashboard",
    module_group: "Dashboard",
  },
  {
    id: 2,
    permission_code: "users.view",
    permission_name: "Xem danh sách nhân viên",
    module_group: "Nhân viên",
  },
  {
    id: 3,
    permission_code: "users.create",
    permission_name: "Thêm nhân viên",
    module_group: "Nhân viên",
  },
  {
    id: 4,
    permission_code: "users.update",
    permission_name: "Cập nhật nhân viên",
    module_group: "Nhân viên",
  },
  {
    id: 5,
    permission_code: "users.delete",
    permission_name: "Xóa nhân viên",
    module_group: "Nhân viên",
  },
  {
    id: 6,
    permission_code: "roles.view",
    permission_name: "Xem nhóm quyền",
    module_group: "Phân quyền",
  },
  {
    id: 7,
    permission_code: "roles.create",
    permission_name: "Thêm nhóm quyền",
    module_group: "Phân quyền",
  },
  {
    id: 8,
    permission_code: "roles.update",
    permission_name: "Cập nhật nhóm quyền",
    module_group: "Phân quyền",
  },
  {
    id: 9,
    permission_code: "roles.delete",
    permission_name: "Xóa nhóm quyền",
    module_group: "Phân quyền",
  },
  {
    id: 10,
    permission_code: "customers.view",
    permission_name: "Xem khách hàng",
    module_group: "Khách hàng",
  },
  {
    id: 11,
    permission_code: "customers.update",
    permission_name: "Cập nhật khách hàng",
    module_group: "Khách hàng",
  },
];

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

    // Chú ý: permission_ids phải tồn tại thật trong DB BE.
    // Nếu permission mock không khớp DB thì BE sẽ báo permission không tồn tại.
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
    ...payload,
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

// ─── Permissions: mock tạm ───────────────────────────────────────────────────
export async function getAllPermissions(): Promise<Permission[]> {
  return MOCK_PERMISSIONS;
}

export async function getPermissionsByModule(): Promise<PermissionsByModule> {
  return MOCK_PERMISSIONS.reduce<PermissionsByModule>((acc, permission) => {
    const moduleKey =
      permission.module_group || permission.module_name || "Khác";

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
