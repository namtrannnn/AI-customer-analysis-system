import type { UserCreatePayload } from "@/types/user.type";

export type UserFormErrors = Partial<Record<keyof UserCreatePayload, string>>;

export function validateUserCreate(values: UserCreatePayload): UserFormErrors {
  const errors: UserFormErrors = {};

  if (!values.full_name?.trim()) {
    errors.full_name = "Họ tên không được để trống";
  } else if (values.full_name.trim().length < 2) {
    errors.full_name = "Họ tên tối thiểu 2 ký tự";
  }

  if (values.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) {
    errors.email = "Email không hợp lệ";
  }

  if (values.phone && !/^(0|\+84)[35789][0-9]{8}$/.test(values.phone)) {
    errors.phone = "Số điện thoại không đúng định dạng";
  }

  if (!values.role_ids || values.role_ids.length === 0) {
    errors.role_ids = "Vui lòng chọn ít nhất 1 vai trò";
  }

  return errors;
}
