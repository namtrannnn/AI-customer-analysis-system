export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface AuthUser {
  id: number;
  full_name: string;
  username: string;
  email: string | null;
  status: string;
  roles: string[];
}
