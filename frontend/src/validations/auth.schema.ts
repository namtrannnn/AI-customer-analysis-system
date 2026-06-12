export interface LoginForm {
  username: string;
  password: string;
}

export type LoginErrors = Partial<Record<keyof LoginForm, string>>;

export function validateLogin(values: LoginForm): LoginErrors {
  const errors: LoginErrors = {};

  if (!values.username.trim()) {
    errors.username = "Tên đăng nhập không được để trống";
  }

  if (!values.password) {
    errors.password = "Mật khẩu không được để trống";
  } else if (values.password.length < 6) {
    errors.password = "Mật khẩu phải có ít nhất 6 ký tự";
  }

  return errors;
}

export interface ChangePasswordForm {
  old_password: string;
  new_password: string;
  confirm_password: string;
}

export type ChangePasswordErrors = Partial<
  Record<keyof ChangePasswordForm, string>
>;

export function validateChangePassword(
  values: ChangePasswordForm,
): ChangePasswordErrors {
  const errors: ChangePasswordErrors = {};

  if (!values.old_password) {
    errors.old_password = "Mật khẩu hiện tại không được để trống";
  }

  if (!values.new_password) {
    errors.new_password = "Mật khẩu mới không được để trống";
  } else if (values.new_password.length < 8) {
    errors.new_password = "Mật khẩu mới phải có ít nhất 8 ký tự";
  } else if (!/[A-Z]/.test(values.new_password)) {
    errors.new_password = "Mật khẩu mới phải chứa ít nhất 1 chữ cái viết hoa";
  } else if (!/\d/.test(values.new_password)) {
    errors.new_password = "Mật khẩu mới phải chứa ít nhất 1 chữ số";
  } else if (!/[@$!%*?&#^_-]/.test(values.new_password)) {
    errors.new_password =
      "Mật khẩu mới phải chứa ít nhất 1 ký tự đặc biệt (@, $, !, %, *, ?, &, #, ^, _, -)";
  }

  if (!values.confirm_password) {
    errors.confirm_password = "Vui lòng nhập lại mật khẩu mới";
  } else if (values.confirm_password !== values.new_password) {
    errors.confirm_password = "Mật khẩu nhập lại không khớp";
  }

  if (
    values.old_password &&
    values.new_password &&
    values.old_password === values.new_password
  ) {
    errors.new_password = "Mật khẩu mới không được trùng mật khẩu hiện tại";
  }

  return errors;
}
