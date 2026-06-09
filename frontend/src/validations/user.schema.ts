import type { UserCreatePayload } from "@/types/user.type";

export type UserFormErrors = Partial<Record<keyof UserCreatePayload, string>>;

export function validateUserCreate(values: UserCreatePayload): UserFormErrors {
  const errors: UserFormErrors = {};

  if (!values.full_name?.trim()) {
    errors.full_name = "Họ tên không được để trống";
  }

  if (!values.username?.trim()) {
    errors.username = "Tên đăng nhập không được để trống";
  } else if (!/^[a-zA-Z0-9_]{3,50}$/.test(values.username)) {
    errors.username = "Chỉ dùng chữ, số, gạch dưới, tối thiểu 3 ký tự";
  }

  if (!values.password) {
    errors.password = "Mật khẩu không được để trống";
  } else if (values.password.length < 6) {
    errors.password = "Mật khẩu tối thiểu 6 ký tự";
  }

  if (values.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) {
    errors.email = "Email không hợp lệ";
  }

  if (values.phone && !/^(0[3-9]\d{8})$/.test(values.phone)) {
    errors.phone = "Số điện thoại không hợp lệ";
  }

  return errors;
}
