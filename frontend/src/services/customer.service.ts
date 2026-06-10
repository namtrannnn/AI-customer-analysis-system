import { http } from "@/lib/http";
import type {
  Customer,
  CustomerCreatePayload,
  CustomerUpdatePayload,
  CustomerFilterParams,
  PaginatedResponse,
  VisitSession,
  Order,
  PersonProfile,
  AnonymousCreatePayload,
} from "@/types/customer.type";

// ─── Anonymous profile: camera tạo khách ẩn danh ─────────────────────────────
export async function createAnonymousProfile(
  payload: AnonymousCreatePayload,
): Promise<PersonProfile> {
  return http.post<PersonProfile>("/customers/anonymous", payload);
}

// ─── List with client-side pagination ─────────────────────────────────────────
export async function getCustomers(
  params: CustomerFilterParams = {},
): Promise<PaginatedResponse<Customer>> {
  const { page = 1, limit = 10, search = "", status = "" } = params;

  const keyword = search.trim();
  const skip = (page - 1) * limit;

  const response = await http.raw.get("/customers/", {
    params: {
      q: keyword || undefined,
      status: status || undefined,
      skip,
      limit,
    },
  });

  const json = response.data;

  const data: Customer[] = Array.isArray(json.data) ? json.data : [];
  const total = json.total ?? json.meta?.total ?? data.length;

  return {
    data,
    total,
    page,
    limit,
    total_pages: Math.max(1, Math.ceil(total / limit)),
  };
}

// ─── Get by ID ────────────────────────────────────────────────────────────────
export async function getCustomerById(id: number): Promise<Customer> {
  return http.get<Customer>(`/customers/${id}`);
}

// ─── Create ───────────────────────────────────────────────────────────────────
export async function createCustomer(
  payload: CustomerCreatePayload,
): Promise<Customer> {
  return http.post<Customer>("/customers/", payload);
}

// ─── Update ───────────────────────────────────────────────────────────────────
export async function updateCustomer(
  id: number,
  payload: CustomerUpdatePayload,
): Promise<Customer> {
  return http.patch<Customer>(`/customers/${id}`, payload);
}

// ─── Soft delete ──────────────────────────────────────────────────────────────
export async function deleteCustomer(id: number): Promise<null> {
  return http.delete<null>(`/customers/${id}`);
}

// ─── Upload avatar / ảnh khuôn mặt ────────────────────────────────────────────
export async function uploadCustomerAvatar(
  customerId: number,
  file: File,
): Promise<Customer> {
  const formData = new FormData();
  formData.append("file", file);

  return http.post<Customer>(`/customers/${customerId}/avatar`, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
}

// ─── Visit sessions ───────────────────────────────────────────────────────────
export async function getCustomerVisitHistory(
  customerId: number,
): Promise<VisitSession[]> {
  return http.get<VisitSession[]>(`/customers/${customerId}/visits`);
}

// ─── Order history ────────────────────────────────────────────────────────────
export async function getCustomerOrderHistory(
  customerId: number,
): Promise<Order[]> {
  return http.get<Order[]>(`/customers/${customerId}/orders`);
}
