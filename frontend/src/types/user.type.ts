export type UserStatus = "active" | "inactive" | "deleted";

export type UserFilterStatus = "active" | "inactive" | "";

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

  // BE hiện trả role_ids thay vì roles object
  role_ids: number[];
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
  email?: string | null;
  phone?: string | null;
  avatar_url?: string | null;
  role_ids: number[];
}

export interface UserCreateResponse {
  id: number;
  full_name: string;
  username: string;
  temporary_password: string;
}

export interface UserUpdatePayload {
  full_name?: string;
  email?: string | null;
  phone?: string | null;
  avatar_url?: string | null;
  status?: "active" | "inactive";
  role_ids?: number[];
}

export interface UserFilterParams {
  search?: string;
  status?: UserFilterStatus;
  page?: number;
  limit?: number;
}
