export interface Permission {
  id: number;
  permission_code: string;
  permission_name: string;
  module_name: string;
  description: string | null;
  created_at: string;
}

// Dùng cho trang Phân quyền — matrix role × permission
export interface RolePermissionMatrix {
  role: { id: number; role_code: string; role_name: string };
  permission_ids: number[];
}

export interface UpdateRolePermissionsPayload {
  role_id: number;
  permission_ids: number[];
}

// Nhóm permissions theo module
export type PermissionsByModule = Record<string, Permission[]>;
