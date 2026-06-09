import type { User } from "@/types/user.type";

export const MOCK_USERS: User[] = [
  {
    id: 1,
    full_name: "Nguyễn Quản Trị",
    username: "admin",
    email: "admin@company.com",
    phone: "0901111111",
    status: "active",
    avatar_url: "https://api.dicebear.com/7.x/personas/svg?seed=admin",
    last_login_at: "2024-06-09T08:00:00Z",
    created_at: "2024-01-01T07:00:00Z",
    updated_at: null,
    roles: [
      {
        id: 1,
        role_id: 1,
        role_code: "ADMIN",
        role_name: "Quản trị viên",
        assigned_at: "2024-01-01T07:00:00Z",
      },
    ],
  },
  {
    id: 2,
    full_name: "Trần Thị Manager",
    username: "manager01",
    email: "manager@company.com",
    phone: "0902222222",
    status: "active",
    avatar_url: "https://api.dicebear.com/7.x/personas/svg?seed=manager01",
    last_login_at: "2024-06-09T09:15:00Z",
    created_at: "2024-01-15T08:00:00Z",
    updated_at: null,
    roles: [
      {
        id: 2,
        role_id: 2,
        role_code: "MANAGER",
        role_name: "Quản lý",
        assigned_at: "2024-01-15T08:00:00Z",
      },
    ],
  },
  {
    id: 3,
    full_name: "Lê Văn Staff",
    username: "staff01",
    email: "staff01@company.com",
    phone: "0903333333",
    status: "active",
    avatar_url: "https://api.dicebear.com/7.x/personas/svg?seed=staff01",
    last_login_at: "2024-06-08T14:00:00Z",
    created_at: "2024-02-01T08:00:00Z",
    updated_at: null,
    roles: [
      {
        id: 3,
        role_id: 3,
        role_code: "STAFF",
        role_name: "Nhân viên",
        assigned_at: "2024-02-01T08:00:00Z",
      },
    ],
  },
  {
    id: 4,
    full_name: "Phạm Thị Viewer",
    username: "viewer01",
    email: "viewer@company.com",
    phone: null,
    status: "inactive",
    avatar_url: null,
    last_login_at: "2024-05-01T10:00:00Z",
    created_at: "2024-03-01T08:00:00Z",
    updated_at: "2024-05-20T09:00:00Z",
    roles: [
      {
        id: 4,
        role_id: 4,
        role_code: "VIEWER",
        role_name: "Xem báo cáo",
        assigned_at: "2024-03-01T08:00:00Z",
      },
    ],
  },
  {
    id: 5,
    full_name: "Hoàng Văn Analyst",
    username: "analyst01",
    email: "analyst@company.com",
    phone: "0905555555",
    status: "active",
    avatar_url: "https://api.dicebear.com/7.x/personas/svg?seed=analyst01",
    last_login_at: "2024-06-09T07:30:00Z",
    created_at: "2024-02-15T08:00:00Z",
    updated_at: null,
    roles: [
      {
        id: 5,
        role_id: 2,
        role_code: "MANAGER",
        role_name: "Quản lý",
        assigned_at: "2024-02-15T08:00:00Z",
      },
      {
        id: 6,
        role_id: 3,
        role_code: "STAFF",
        role_name: "Nhân viên",
        assigned_at: "2024-02-15T08:00:00Z",
      },
    ],
  },
];

let userIdCounter = MOCK_USERS.length + 1;
export function getNextUserId(): number {
  return userIdCounter++;
}
