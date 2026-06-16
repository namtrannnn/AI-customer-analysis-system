import type { UserCreatePayload, UserUpdatePayload } from "@/types/user.type";

export type UserFormErrors = Partial<
  Record<keyof UserCreatePayload | keyof UserUpdatePayload, string>
>;

const fullNameRegex = /^[A-Za-zÀ-ỹ\s]+$/;
const phoneRegex = /^(0|\+84)[35789][0-9]{8}$/;
const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validateFullName(fullName?: string): string | undefined {
  const value = fullName?.trim();

  if (!value) return "Họ tên không được để trống";
  if (value.length < 2) return "Họ tên tối thiểu 2 ký tự";
  if (!fullNameRegex.test(value)) {
    return "Họ tên không được chứa số hoặc ký tự đặc biệt";
  }

  return undefined;
}

export function validateUserCreate(values: UserCreatePayload): UserFormErrors {
  const errors: UserFormErrors = {};

  const fullNameError = validateFullName(values.full_name);
  if (fullNameError) errors.full_name = fullNameError;

  if (values.email && !emailRegex.test(values.email)) {
    errors.email = "Email không hợp lệ";
  }

  if (values.phone && !phoneRegex.test(values.phone)) {
    errors.phone = "Số điện thoại không đúng định dạng";
  }

  if (!values.role_id) {
    errors.role_id = "Vui lòng chọn 1 vai trò";
  }

  return errors;
}

export function validateUserUpdate(values: UserUpdatePayload): UserFormErrors {
  const errors: UserFormErrors = {};

  const fullNameError = validateFullName(values.full_name);
  if (fullNameError) errors.full_name = fullNameError;

  if (values.email && !emailRegex.test(values.email)) {
    errors.email = "Email không hợp lệ";
  }

  if (values.phone && !phoneRegex.test(values.phone)) {
    errors.phone = "Số điện thoại không đúng định dạng";
  }

  if (!values.role_id) {
    errors.role_id = "Vui lòng chọn 1 vai trò";
  }

  if (values.status && !["active", "inactive"].includes(values.status)) {
    errors.status = "Trạng thái không hợp lệ";
  }

  return errors;
}
