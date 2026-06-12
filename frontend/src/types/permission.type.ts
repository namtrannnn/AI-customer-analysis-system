// src/types/permission.type.ts

export interface Permission {
  id: number;
  permission_code: string;
  permission_name: string;
  module_group: string;

  // Dự phòng nếu BE sau này đặt tên module_name
  module_name?: string;
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
