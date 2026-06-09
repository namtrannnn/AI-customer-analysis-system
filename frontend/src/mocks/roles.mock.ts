import type { Role } from "@/types/role.type";
import type { Permission, RolePermissionMatrix } from "@/types/permission.type";

export const MOCK_PERMISSIONS: Permission[] = [
  // Module: Khách hàng
  { id: 1,  permission_code: "CUSTOMER_VIEW",   permission_name: "Xem khách hàng",        module_name: "Khách hàng", description: null, created_at: "2024-01-01T00:00:00Z" },
  { id: 2,  permission_code: "CUSTOMER_CREATE", permission_name: "Thêm khách hàng",       module_name: "Khách hàng", description: null, created_at: "2024-01-01T00:00:00Z" },
  { id: 3,  permission_code: "CUSTOMER_UPDATE", permission_name: "Sửa khách hàng",        module_name: "Khách hàng", description: null, created_at: "2024-01-01T00:00:00Z" },
  { id: 4,  permission_code: "CUSTOMER_DELETE", permission_name: "Xóa khách hàng",        module_name: "Khách hàng", description: null, created_at: "2024-01-01T00:00:00Z" },
  // Module: Người dùng
  { id: 5,  permission_code: "USER_VIEW",       permission_name: "Xem người dùng",        module_name: "Người dùng", description: null, created_at: "2024-01-01T00:00:00Z" },
  { id: 6,  permission_code: "USER_CREATE",     permission_name: "Thêm người dùng",       module_name: "Người dùng", description: null, created_at: "2024-01-01T00:00:00Z" },
  { id: 7,  permission_code: "USER_UPDATE",     permission_name: "Sửa người dùng",        module_name: "Người dùng", description: null, created_at: "2024-01-01T00:00:00Z" },
  { id: 8,  permission_code: "USER_DELETE",     permission_name: "Xóa người dùng",        module_name: "Người dùng", description: null, created_at: "2024-01-01T00:00:00Z" },
  // Module: Nhóm quyền
  { id: 9,  permission_code: "ROLE_VIEW",       permission_name: "Xem nhóm quyền",        module_name: "Nhóm quyền", description: null, created_at: "2024-01-01T00:00:00Z" },
  { id: 10, permission_code: "ROLE_CREATE",     permission_name: "Thêm nhóm quyền",       module_name: "Nhóm quyền", description: null, created_at: "2024-01-01T00:00:00Z" },
  { id: 11, permission_code: "ROLE_UPDATE",     permission_name: "Sửa nhóm quyền",        module_name: "Nhóm quyền", description: null, created_at: "2024-01-01T00:00:00Z" },
  { id: 12, permission_code: "ROLE_DELETE",     permission_name: "Xóa nhóm quyền",        module_name: "Nhóm quyền", description: null, created_at: "2024-01-01T00:00:00Z" },
  // Module: Phân quyền
  { id: 13, permission_code: "PERMISSION_VIEW", permission_name: "Xem phân quyền",        module_name: "Phân quyền", description: null, created_at: "2024-01-01T00:00:00Z" },
  { id: 14, permission_code: "PERMISSION_EDIT", permission_name: "Cập nhật phân quyền",   module_name: "Phân quyền", description: null, created_at: "2024-01-01T00:00:00Z" },
  // Module: Báo cáo
  { id: 15, permission_code: "REPORT_VIEW",     permission_name: "Xem báo cáo",           module_name: "Báo cáo",    description: null, created_at: "2024-01-01T00:00:00Z" },
  { id: 16, permission_code: "REPORT_EXPORT",   permission_name: "Xuất báo cáo",          module_name: "Báo cáo",    description: null, created_at: "2024-01-01T00:00:00Z" },
];

export const MOCK_ROLES: Role[] = [
  {
    id: 1,
    role_code: "ADMIN",
    role_name: "Quản trị viên",
    description: "Toàn quyền hệ thống",
    created_at: "2024-01-01T00:00:00Z",
    permission_count: 16,
    user_count: 1,
  },
  {
    id: 2,
    role_code: "MANAGER",
    role_name: "Quản lý",
    description: "Quản lý khách hàng, xem báo cáo, quản lý nhân viên",
    created_at: "2024-01-01T00:00:00Z",
    permission_count: 10,
    user_count: 2,
  },
  {
    id: 3,
    role_code: "STAFF",
    role_name: "Nhân viên",
    description: "Xem và thêm khách hàng",
    created_at: "2024-01-01T00:00:00Z",
    permission_count: 3,
    user_count: 2,
  },
  {
    id: 4,
    role_code: "VIEWER",
    role_name: "Xem báo cáo",
    description: "Chỉ xem báo cáo và danh sách",
    created_at: "2024-01-15T00:00:00Z",
    permission_count: 3,
    user_count: 1,
  },
];

// Role → Permission IDs mapping
export const MOCK_ROLE_PERMISSIONS: Record<number, number[]> = {
  1: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16], // ADMIN: tất cả
  2: [1, 2, 3, 5, 6, 7, 9, 10, 15, 16],                        // MANAGER
  3: [1, 2, 3],                                                 // STAFF
  4: [1, 5, 9, 13, 15],                                        // VIEWER
};

export const MOCK_ROLE_PERMISSION_MATRIX: RolePermissionMatrix[] = MOCK_ROLES.map((r) => ({
  role: { id: r.id, role_code: r.role_code, role_name: r.role_name },
  permission_ids: MOCK_ROLE_PERMISSIONS[r.id] ?? [],
}));

let roleIdCounter = MOCK_ROLES.length + 1;
export function getNextRoleId(): number {
  return roleIdCounter++;
}
