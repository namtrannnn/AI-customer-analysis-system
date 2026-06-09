export type UserStatus = "active" | "inactive" | "locked";

export interface User {
  id: number;
  full_name: string;
  username: string;
  email: string | null;
  phone: string | null;
  status: UserStatus;
  avatar_url: string | null;
  last_login_at: string | null;
  created_at: string;
  updated_at: string | null;
  // Roles gán cho user
  roles: UserRole[];
}

export interface UserRole {
  id: number;
  role_id: number;
  role_code: string;
  role_name: string;
  assigned_at: string;
}

export interface UserCreatePayload {
  full_name: string;
  username: string;
  email?: string;
  phone?: string;
  password: string;
  status?: UserStatus;
  role_ids?: number[];
}

export interface UserUpdatePayload {
  full_name?: string;
  email?: string;
  phone?: string;
  status?: UserStatus;
  role_ids?: number[];
}

export interface UserFilterParams {
  search?: string;
  status?: UserStatus | "";
  page?: number;
  limit?: number;
}
