/**
 * Cashier Service — Thu ngân
 * 
 * Hiện tại: mock data
 * Khi BE xong: uncomment các API call và xóa mock
 * 
 * TODO endpoints cần BE làm:
 * - GET  /api/cashier/in-store          → CASH-01
 * - POST /api/cashier/identify          → CASH-05 (link profile với customer có sẵn)
 * - POST /api/orders/                   → CASH-08
 */

import { http } from "@/lib/http";
import type { Customer } from "@/types/customer.type";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface InStoreVisitor {
  session_id: number;
  entry_time: string;
  profile_id: number;
  anonymous_code: string;
  person_type: "anonymous" | "identified";
  face_image_url: string | null;
  customer: {
    id: number;
    customer_code: string;
    full_name: string;
    phone: string | null;
  } | null;
}

export interface CreateOrderPayload {
  person_profile_id: number;
  customer_id?: number | null;
  total_amount: number;
  item_summary?: string;
  payment_method: "cash" | "card" | "transfer" | "e_wallet";
  order_time?: string;
}

export interface LinkProfilePayload {
  person_profile_id: number;
  customer_id: number;
}

// ─── Mock data ────────────────────────────────────────────────────────────────
// Khi BE xong: xóa toàn bộ MOCK và uncomment API calls bên dưới

const MOCK_IN_STORE: InStoreVisitor[] = [
  {
    session_id: 101,
    entry_time: new Date(Date.now() - 18 * 60 * 1000).toISOString(),
    profile_id: 7,
    anonymous_code: "P_0001",
    person_type: "identified",
    face_image_url: "https://api.dicebear.com/7.x/personas/svg?seed=Tuan",
    customer: {
      id: 1,
      customer_code: "CUS000001",
      full_name: "Nguyễn Văn An",
      phone: "0901234567",
    },
  },
  {
    session_id: 102,
    entry_time: new Date(Date.now() - 7 * 60 * 1000).toISOString(),
    profile_id: 10,
    anonymous_code: "P_0002",
    person_type: "anonymous",
    face_image_url: "https://api.dicebear.com/7.x/personas/svg?seed=B2",
    customer: null,
  },
  {
    session_id: 103,
    entry_time: new Date(Date.now() - 3 * 60 * 1000).toISOString(),
    profile_id: 15,
    anonymous_code: "P_0003",
    person_type: "identified",
    face_image_url: "https://api.dicebear.com/7.x/personas/svg?seed=Bich",
    customer: {
      id: 3,
      customer_code: "CUS000003",
      full_name: "Lê Minh Cường",
      phone: "0907654321",
    },
  },
  {
    session_id: 104,
    entry_time: new Date(Date.now() - 1 * 60 * 1000).toISOString(),
    profile_id: 22,
    anonymous_code: "P_0004",
    person_type: "anonymous",
    face_image_url: "https://api.dicebear.com/7.x/personas/svg?seed=D4",
    customer: null,
  },
];

let _mockStore = [...MOCK_IN_STORE];

// ─── API / Mock functions ─────────────────────────────────────────────────────

/**
 * Lấy danh sách khách đang trong cửa hàng (exit_time IS NULL)
 * Mock: polling 5s sẽ gọi hàm này
 */
export async function getInStoreVisitors(
  skip = 0,
  limit = 50,
): Promise<{ data: InStoreVisitor[]; total: number }> {
  // TODO: thay bằng API call khi BE xong CASH-01
  // const res = await http.raw.get("/cashier/in-store", { params: { skip, limit } });
  // return { data: res.data.data, total: res.data.meta?.total ?? 0 };

  await new Promise((r) => setTimeout(r, 200)); // simulate latency
  const sliced = _mockStore.slice(skip, skip + limit);
  return { data: sliced, total: _mockStore.length };
}

/**
 * Link profile ẩn danh với khách hàng có sẵn
 * Mock: cập nhật local state
 */
export async function linkProfileToCustomer(
  payload: LinkProfilePayload,
  customerInfo: { id: number; customer_code: string; full_name: string; phone: string | null },
): Promise<void> {
  // TODO: thay bằng API call khi BE xong CASH-05
  // await http.post("/cashier/identify", payload);

  await new Promise((r) => setTimeout(r, 400));
  _mockStore = _mockStore.map((v) =>
    v.profile_id === payload.person_profile_id
      ? { ...v, person_type: "identified" as const, customer: customerInfo }
      : v,
  );
}

/**
 * Tạo đơn hàng
 * Mock: không lưu gì, chỉ trả success
 */
export async function createOrder(payload: CreateOrderPayload): Promise<{ order_code: string }> {
  // TODO: thay bằng API call khi BE xong CASH-08
  // return http.post<{ order_code: string }>("/orders/", payload);

  await new Promise((r) => setTimeout(r, 500));
  const code = `ORD${String(Date.now()).slice(-8)}`;
  return { order_code: code };
}

export const PAYMENT_METHOD_LABELS: Record<string, string> = {
  cash:      "Tiền mặt",
  card:      "Thẻ ngân hàng",
  transfer:  "Chuyển khoản",
  e_wallet:  "Ví điện tử",
};
