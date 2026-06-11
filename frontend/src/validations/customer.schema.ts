import { z } from "zod";

export const customerGenderSchema = z.enum(["male", "female", "other"], {
  message: "Giới tính không hợp lệ",
});

export const customerStatusSchema = z.enum(["active", "inactive"], {
  message: "Trạng thái không hợp lệ",
});

export const customerCreateSchema = z.object({
  full_name: z
    .string()
    .trim()
    .min(2, "Tên khách hàng phải có ít nhất 2 ký tự")
    .max(100, "Tên khách hàng không được vượt quá 100 ký tự"),

  phone: z
    .string()
    .trim()
    .optional()
    .or(z.literal(""))
    .refine(
      (value) => !value || /^(0[35789]\d{8})$/.test(value),
      "Số điện thoại không hợp lệ (VD: 0901234567)",
    ),

  email: z
    .string()
    .trim()
    .optional()
    .or(z.literal(""))
    .refine(
      (value) => !value || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
      "Email không hợp lệ",
    ),

  gender: customerGenderSchema,

  note: z.string().trim().optional().or(z.literal("")),

  avatar_url: z.string().trim().optional().or(z.literal("")),

  person_profile_id: z.number().positive().optional(),
});

export const customerUpdateSchema = customerCreateSchema.partial().extend({
  status: customerStatusSchema.optional(),
});

export type CustomerCreateFormValues = z.infer<typeof customerCreateSchema>;
export type CustomerUpdateFormValues = z.infer<typeof customerUpdateSchema>;
