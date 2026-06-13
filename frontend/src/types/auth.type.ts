export interface LoginRequest {
  username: string;
  password: string;
}

export interface AuthRole {
  id: number;
  role_code: string;
  role_name: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  is_first_login: boolean;
  user_info: AuthUser;
}

export interface AuthUser {
  id: number;
  full_name: string;
  username: string;
  email: string | null;
  phone?: string | null;
  avatar_url?: string | null;
  status: string;

  role: AuthRole | null;
  permissions: string[];

  last_login_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
  confirm_password: string;
}
