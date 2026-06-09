// Re-export từ role.service để dùng độc lập
export {
  getAllPermissions,
  getPermissionsByModule,
  getRolePermissionMatrix,
  updateRolePermissions,
  getRolePermissions,
} from "./role.service";
