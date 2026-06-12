import type { RoleCreatePayload } from "@/types/role.type";

export type RoleFormErrors = Partial<Record<keyof RoleCreatePayload, string>>;

export function validateRole(values: RoleCreatePayload): RoleFormErrors {
  const errors: RoleFormErrors = {};

  const roleCode = values.role_code?.trim().toLowerCase() ?? "";
  const roleName = values.role_name?.trim() ?? "";

  if (!roleCode) {
    errors.role_code = "Mã nhóm quyền không được để trống";
  } else if (roleCode.length < 2 || roleCode.length > 50) {
    errors.role_code = "Mã nhóm quyền phải từ 2 đến 50 ký tự";
  } else if (!/^[a-z0-9_]+$/.test(roleCode)) {
    errors.role_code =
      "Mã chỉ gồm chữ thường không dấu, số và gạch dưới (VD: admin, staff_01)";
  }

  if (!roleName) {
    errors.role_name = "Tên nhóm quyền không được để trống";
  } else if (roleName.length < 2 || roleName.length > 100) {
    errors.role_name = "Tên nhóm quyền phải từ 2 đến 100 ký tự";
  }

  return errors;
}
