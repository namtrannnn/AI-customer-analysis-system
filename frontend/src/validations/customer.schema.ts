import type { CustomerCreatePayload } from "@/types/customer.type";

export type FormErrors = Partial<Record<keyof CustomerCreatePayload, string>>;

export function validateCustomer(values: CustomerCreatePayload): FormErrors {
  const errors: FormErrors = {};

  if (!values.full_name?.trim()) {
    errors.full_name = "Tên khách hàng không được để trống";
  } else if (values.full_name.trim().length < 2) {
    errors.full_name = "Tên phải có ít nhất 2 ký tự";
  } else if (values.full_name.trim().length > 100) {
    errors.full_name = "Tên không được vượt quá 100 ký tự";
  }

  if (values.phone && !/^(0[3-9]\d{8})$/.test(values.phone.trim())) {
    errors.phone = "Số điện thoại không hợp lệ (VD: 0901234567)";
  }

  if (values.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) {
    errors.email = "Email không hợp lệ";
  }

  return errors;
}
