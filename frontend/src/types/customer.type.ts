// ─── Person Profile (khách ẩn danh từ camera) ────────────────────────────────
export interface PersonProfile {
  id: number;
  anonymous_code: string;
  person_type: "anonymous" | "identified";
  first_seen_at: string | null;
  last_seen_at: string | null;
  total_visits: number;
  confidence_avg: number | null;
  created_at: string;
}

// ─── Customer (khách đã định danh) ───────────────────────────────────────────
export type CustomerStatus = "active" | "inactive" | "vip";
export type CustomerGender = "male" | "female" | "other";

export interface Customer {
  id: number;
  customer_code: string;
  full_name: string;
  phone: string | null;
  email: string | null;
  gender: CustomerGender | null;
  status: CustomerStatus;
  avatar_url: string | null;
  note: string | null;
  created_at: string;
  updated_at: string | null;

  // Thống kê cơ bản (join từ visit_sessions / orders)
  total_visits: number;
  total_orders: number;
  total_spent: number;
  last_visited_at: string | null;

  // Mapping với person_profile
  person_profile_id: number | null;
}

// ─── Visit Session ────────────────────────────────────────────────────────────
export interface VisitSession {
  id: number;
  person_profile_id: number;
  entry_time: string;
  exit_time: string | null;
  duration_seconds: number | null;
  is_identified: boolean;
  created_at: string;
}

// ─── Order ────────────────────────────────────────────────────────────────────
export interface Order {
  id: number;
  customer_id: number | null;
  order_code: string;
  total_amount: number;
  item_summary: string | null;
  payment_method: string | null;
  order_time: string;
  created_at: string;
}

// ─── DTO / Payload ────────────────────────────────────────────────────────────
export interface CustomerCreatePayload {
  full_name: string;
  phone?: string;
  email?: string;
  gender?: CustomerGender;
  status?: CustomerStatus;
  note?: string;
  avatar_url?: string;
  person_profile_id?: number;
}

export interface CustomerUpdatePayload extends Partial<CustomerCreatePayload> {}

// ─── Filter / Query params ────────────────────────────────────────────────────
export interface CustomerFilterParams {
  search?: string;
  status?: CustomerStatus | "";
  gender?: CustomerGender | "";
  page?: number;
  limit?: number;
}

// ─── Paginated response ───────────────────────────────────────────────────────
export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}
