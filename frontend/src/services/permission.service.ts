import { http } from "@/lib/http";
import type {
  Permission,
  PermissionsByModule,
  PermissionMatrixResponse,
  RolePermissionsBulkUpdate,
  PermissionUpdatePayload,
  RolePermissionMatrix,
  UpdateRolePermissionsPayload,
} from "@/types/permission.type";

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

// BE: GET /permissions/matrix
export async function getPermissionMatrix(): Promise<PermissionMatrixResponse> {
  return http.get<PermissionMatrixResponse>("/permissions/matrix");
}

// BE: POST /permissions/matrix/bulk
export async function bulkUpdatePermissionMatrix(
  payload: RolePermissionsBulkUpdate[],
): Promise<null> {
  return http.post<null>("/permissions/matrix/bulk", payload);
}

// BE: PATCH /permissions/{permission_id}
export async function updatePermission(
  permissionId: number,
  payload: PermissionUpdatePayload,
): Promise<Permission> {
  return http.patch<Permission>(`/permissions/${permissionId}`, payload);
}

/**
 * Adapter giữ tên cũ để page hiện tại chưa phải sửa quá nhiều.
 * Chuyển BE matrix mới về dạng cũ:
 * [{ role, permission_ids }]
 */
export async function getRolePermissionMatrix(): Promise<
  RolePermissionMatrix[]
> {
  const matrix = await getPermissionMatrix();

  return matrix.roles.map((role) => ({
    role,
    permission_ids: matrix.role_permissions[String(role.id)] ?? [],
  }));
}

/**
 * Adapter tên cũ. Chỉ dùng khi muốn update 1 role.
 * Nhưng trang matrix nên dùng bulkUpdatePermissionMatrix để lưu 1 lần.
 */
export async function updateRolePermissions(
  payload: UpdateRolePermissionsPayload,
): Promise<void> {
  await bulkUpdatePermissionMatrix([
    {
      role_id: payload.role_id,
      permission_ids: payload.permission_ids,
    },
  ]);
}
