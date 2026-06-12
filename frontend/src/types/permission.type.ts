export interface Permission {
  id: number;
  permission_code: string;
  permission_name: string;
  module_name: string;
  description: string | null;
  created_at: string;
}

export type PermissionsByModule = Record<string, Permission[]>;

export interface RoleMinInfo {
  id: number;
  role_code: string;
  role_name: string;
}

export interface PermissionMinInfo {
  id: number;
  permission_code: string;
  permission_name: string;
}

export interface ModulePermissions {
  module_name: string;
  permissions: PermissionMinInfo[];
}

export interface PermissionMatrixResponse {
  roles: RoleMinInfo[];
  modules: ModulePermissions[];

  // JSON key từ BE sẽ là string: "1", "2", ...
  role_permissions: Record<string, number[]>;
}

export interface RolePermissionsBulkUpdate {
  role_id: number;
  permission_ids: number[];
}

export interface PermissionUpdatePayload {
  permission_name?: string;
  module_name?: string;
  description?: string | null;
}

// Giữ lại nếu file RoleForm còn dùng
export interface RolePermissionMatrix {
  role: RoleMinInfo;
  permission_ids: number[];
}

export interface UpdateRolePermissionsPayload {
  role_id: number;
  permission_ids: number[];
}
