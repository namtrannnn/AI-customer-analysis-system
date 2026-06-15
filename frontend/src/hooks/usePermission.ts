import { getCurrentUser } from "@/services/auth.service";

export function usePermission() {
  const user = getCurrentUser();

  const permissions = user?.permissions ?? [];

  function hasPermission(permissionCode: string): boolean {
    return permissions.includes(permissionCode);
  }

  function hasAnyPermission(permissionCodes: string[]): boolean {
    return permissionCodes.some((code) => permissions.includes(code));
  }

  function hasAllPermissions(permissionCodes: string[]): boolean {
    return permissionCodes.every((code) => permissions.includes(code));
  }

  return {
    user,
    permissions,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
  };
}
