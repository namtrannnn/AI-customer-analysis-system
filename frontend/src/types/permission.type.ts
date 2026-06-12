export interface Permission {
  id: number;
  permission_code: string;
  permission_name: string;
  module_name: string;
  description: string | null;
  created_at: string;

  // Optional để tương thích code cũ nếu có chỗ còn dùng module_group
  module_group?: string;
}

export type PermissionsByModule = Record<string, Permission[]>;

export interface RolePermissionMatrix {
  role: {
    id: number;
    role_code: string;
    role_name: string;
  };
  permission_ids: number[];
}

export interface UpdateRolePermissionsPayload {
  role_id: number;
  permission_ids: number[];
}
