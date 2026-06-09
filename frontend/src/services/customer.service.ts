/**
 * Customer Service
 *
 * Hiện tại dùng mock data với delay giả lập.
 * Khi có backend: xóa toàn bộ phần mock và uncomment các dòng `http.*`
 */

import { delay } from "./api";
import {
  MOCK_CUSTOMERS,
  MOCK_VISIT_SESSIONS,
  MOCK_ORDERS,
  getNextCustomerId,
  getNextCustomerCode,
} from "@/mocks/customers.mock";
import type {
  Customer,
  CustomerCreatePayload,
  CustomerUpdatePayload,
  CustomerFilterParams,
  PaginatedResponse,
  VisitSession,
  Order,
} from "@/types/customer.type";

// In-memory store (reset khi reload trang — đúng hành vi mock)
let customers: Customer[] = [...MOCK_CUSTOMERS];

// ─── List with filter + pagination ───────────────────────────────────────────
export async function getCustomers(
  params: CustomerFilterParams = {}
): Promise<PaginatedResponse<Customer>> {
  await delay();

  const { search = "", status = "", gender = "", page = 1, limit = 10 } = params;

  let result = [...customers];

  if (search.trim()) {
    const q = search.toLowerCase();
    result = result.filter(
      (c) =>
        c.full_name.toLowerCase().includes(q) ||
        c.customer_code.toLowerCase().includes(q) ||
        c.phone?.includes(q) ||
        c.email?.toLowerCase().includes(q)
    );
  }

  if (status) result = result.filter((c) => c.status === status);
  if (gender) result = result.filter((c) => c.gender === gender);

  // Sort: mới nhất trước
  result.sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  const total = result.length;
  const total_pages = Math.ceil(total / limit);
  const data = result.slice((page - 1) * limit, page * limit);

  return { data, total, page, limit, total_pages };

  // ── Khi có backend ──
  // const query = new URLSearchParams({ ...params } as Record<string, string>);
  // return http.get<PaginatedResponse<Customer>>(`/customers?${query}`);
}

// ─── Get by ID ────────────────────────────────────────────────────────────────
export async function getCustomerById(id: number): Promise<Customer> {
  await delay();

  const found = customers.find((c) => c.id === id);
  if (!found) throw new Error("Không tìm thấy khách hàng");

  return { ...found };

  // ── Khi có backend ──
  // return http.get<Customer>(`/customers/${id}`);
}

// ─── Create ───────────────────────────────────────────────────────────────────
export async function createCustomer(
  payload: CustomerCreatePayload
): Promise<Customer> {
  await delay();

  // Validate phone unique
  if (payload.phone) {
    const exists = customers.find((c) => c.phone === payload.phone);
    if (exists) throw new Error("Số điện thoại đã tồn tại");
  }

  const isAnonymous = !payload.full_name || payload.full_name.startsWith("Khách ẩn danh");
  const newId = getNextCustomerId();

  const newCustomer: Customer = {
    id: newId,
    customer_code: getNextCustomerCode(isAnonymous),
    full_name: payload.full_name ?? `Khách ẩn danh #${newId}`,
    phone: payload.phone ?? null,
    email: payload.email ?? null,
    gender: payload.gender ?? null,
    status: payload.status ?? "active",
    avatar_url: payload.avatar_url ?? null,
    note: payload.note ?? null,
    created_at: new Date().toISOString(),
    updated_at: null,
    total_visits: 0,
    total_orders: 0,
    total_spent: 0,
    last_visited_at: null,
    person_profile_id: payload.person_profile_id ?? null,
  };

  customers = [newCustomer, ...customers];
  return { ...newCustomer };

  // ── Khi có backend ──
  // return http.post<Customer>("/customers", payload);
}

// ─── Update ───────────────────────────────────────────────────────────────────
export async function updateCustomer(
  id: number,
  payload: CustomerUpdatePayload
): Promise<Customer> {
  await delay();

  const idx = customers.findIndex((c) => c.id === id);
  if (idx === -1) throw new Error("Không tìm thấy khách hàng");

  // Validate phone unique (exclude self)
  if (payload.phone) {
    const exists = customers.find((c) => c.phone === payload.phone && c.id !== id);
    if (exists) throw new Error("Số điện thoại đã tồn tại");
  }

  const updated: Customer = {
    ...customers[idx],
    ...payload,
    updated_at: new Date().toISOString(),
  };

  customers[idx] = updated;
  return { ...updated };

  // ── Khi có backend ──
  // return http.patch<Customer>(`/customers/${id}`, payload);
}

// ─── Soft delete ──────────────────────────────────────────────────────────────
export async function deleteCustomer(id: number): Promise<void> {
  await delay();

  const idx = customers.findIndex((c) => c.id === id);
  if (idx === -1) throw new Error("Không tìm thấy khách hàng");

  // Soft delete: set status = inactive (giả lập deleted_at nếu cần)
  customers[idx] = {
    ...customers[idx],
    status: "inactive",
    updated_at: new Date().toISOString(),
  };

  // ── Khi có backend ──
  // return http.delete(`/customers/${id}`);
}

// ─── Visit sessions ───────────────────────────────────────────────────────────
export async function getCustomerVisitHistory(
  customerId: number
): Promise<VisitSession[]> {
  await delay();

  const sessions = MOCK_VISIT_SESSIONS[customerId] ?? [];
  return [...sessions].sort(
    (a, b) => new Date(b.entry_time).getTime() - new Date(a.entry_time).getTime()
  );

  // ── Khi có backend ──
  // return http.get<VisitSession[]>(`/customers/${customerId}/visits`);
}

// ─── Order history ────────────────────────────────────────────────────────────
export async function getCustomerOrderHistory(
  customerId: number
): Promise<Order[]> {
  await delay();

  const orders = MOCK_ORDERS[customerId] ?? [];
  return [...orders].sort(
    (a, b) => new Date(b.order_time).getTime() - new Date(a.order_time).getTime()
  );

  // ── Khi có backend ──
  // return http.get<Order[]>(`/customers/${customerId}/orders`);
}

// ─── Upload avatar (mock trả về URL giả) ──────────────────────────────────────
export async function uploadCustomerAvatar(
  _customerId: number,
  file: File
): Promise<string> {
  await delay(800);

  // Mock: trả về URL từ dicebear dựa trên tên file
  const seed = encodeURIComponent(file.name.replace(/\.[^.]+$/, ""));
  return `https://api.dicebear.com/7.x/personas/svg?seed=${seed}`;

  // ── Khi có backend ──
  // const form = new FormData();
  // form.append("file", file);
  // const res = await fetch(`${BASE_URL}/customers/${_customerId}/avatar`, {
  //   method: "POST",
  //   headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
  //   body: form,
  // });
  // const json = await res.json();
  // return json.data.avatar_url;
}
