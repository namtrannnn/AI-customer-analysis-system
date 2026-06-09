import type { RoleCreatePayload } from "@/types/role.type";

export type RoleFormErrors = Partial<Record<keyof RoleCreatePayload, string>>;

export function validateRole(values: RoleCreatePayload): RoleFormErrors {
  const errors: RoleFormErrors = {};

  if (!values.role_code?.trim()) {
    errors.role_code = "Mã nhóm quyền không được để trống";
  } else if (!/^[A-Z0-9_]{2,50}$/.test(values.role_code.toUpperCase())) {
    errors.role_code = "Mã chỉ gồm chữ HOA, số, gạch dưới (VD: ADMIN, STAFF_01)";
  }

  if (!values.role_name?.trim()) {
    errors.role_name = "Tên nhóm quyền không được để trống";
  }

  return errors;
}
