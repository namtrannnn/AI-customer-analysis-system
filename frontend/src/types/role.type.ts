export interface RoleUser {
  id: number;
  full_name: string;
  username: string;
  avatar_url: string | null;
}

export interface RolePermission {
  id: number;
  permission_code: string;
  permission_name: string;

  // BE mới dùng module_name
  module_name?: string;

  // Giữ optional để tương thích nếu role/full-details vẫn trả module_group
  module_group?: string;
}

export interface Role {
  id: number;
  role_code: string;
  role_name: string;
  description: string | null;
  created_at: string;
  updated_at?: string | null;

  permission_ids?: number[];

  users?: RoleUser[];
  permissions?: RolePermission[];
}

export interface RoleCreatePayload {
  role_code: string;
  role_name: string;
  description?: string | null;
  permission_ids: number[];
}

export interface RoleUpdatePayload {
  role_code?: string;
  role_name?: string;
  description?: string | null;
  permission_ids?: number[];
}

export interface RoleFilterParams {
  search?: string;
  page?: number;
  limit?: number;
}
