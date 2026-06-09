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
