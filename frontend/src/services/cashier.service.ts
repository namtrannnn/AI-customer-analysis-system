/**
 * Cashier Service — Thu ngân
 * 
 * Đã kết nối thực tế với Backend API:
 * - GET  /cashier/in-store-visitors   -> CASH-01 & CASH-02
 * - POST /cashier/link-customer       -> CASH-05 
 * - POST /cashier/orders              -> CASH-08
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
  person_profile_id: number | null;
  customer_id?: number | null;
  total_amount: number;
  item_summary?: string;
  payment_method: "cash" | "card" | "transfer" | "e_wallet";
  order_time?: string;
  ai_session_code?: string;
}

export interface LinkProfilePayload {
  person_profile_id: number;
  customer_id: number;
  ai_session_code?: string;
}

export const PAYMENT_METHOD_LABELS: Record<string, string> = {
  cash:      "Tiền mặt",
  card:      "Thẻ ngân hàng",
  transfer:  "Chuyển khoản",
  e_wallet:  "Ví điện tử",
};

// ─── API functions ────────────────────────────────────────────────────────────

/**
 * Lấy danh sách khách đang trong cửa hàng (exit_time IS NULL)
 * Được gọi liên tục (polling) từ giao diện thu ngân
 */
export async function getInStoreVisitors(
  skip = 0,
  limit = 50,
): Promise<{ data: InStoreVisitor[]; total: number }> {
  const res = await http.raw.get<any>("/cashier/in-store-visitors", { 
    params: { skip, limit } 
  });
  
  // Dựa theo format success_response(data={"total": x, "items": []}) của Backend
  const payloadData = res.data?.data || res.data;
  
  return { 
    data: payloadData?.items || [], 
    total: payloadData?.total || 0 
  };
}

/**
 * Link profile ẩn danh với khách hàng có sẵn
 */
export async function linkProfileToCustomer(
  payload: LinkProfilePayload
): Promise<void> {
  // Gọi API đổi trạng thái person_type và insert bảng customer_identities
  await http.post("/cashier/link-customer", payload);
  
  // Không cần mock update local state nữa. Component gọi API này xong 
  // nên gọi lại fetchVisitors() (hoặc trigger polling) để lấy data mới nhất từ BE.
}

/**
 * Tạo đơn hàng mới tại quầy
 */
export async function createOrder(
  payload: CreateOrderPayload
): Promise<{ order_code: string }> {
  // Gửi thông tin đơn hàng xuống BE, nhận về cục data
  const res = await http.post<any>("/cashier/orders", payload);
  
  // NẾU INTERCEPTOR ĐÃ BÓC VỎ SẴN THÌ res CHÍNH LÀ DATA
  // Thêm "|| res" ở cuối để phòng hờ trường hợp này
  return res?.data?.data || res?.data || res; 
}