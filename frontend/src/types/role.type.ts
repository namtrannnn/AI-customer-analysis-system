export interface Role {
  id: number;
  role_code: string;
  role_name: string;
  description: string | null;
  created_at: string;
  // Số permissions được gán
  permission_count: number;
  // Số users được gán role này
  user_count: number;
}

export interface RoleCreatePayload {
  role_code: string;
  role_name: string;
  description?: string;
  permission_ids?: number[];
}

export interface RoleUpdatePayload extends Partial<RoleCreatePayload> {}

export interface RoleFilterParams {
  search?: string;
  page?: number;
  limit?: number;
}
