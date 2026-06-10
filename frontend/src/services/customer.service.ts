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
  const {
    page = 1,
    limit = 10,
    search = "",
    status = "",
    gender = "",
  } = params;

  const keyword = search.trim();
  const skip = (page - 1) * limit;

  let endpoint = "/customers/";
  let queryParams: Record<string, string | number> = {
    skip,
    limit,
  };

  // BE search dùng /customers/search?q=
  if (keyword) {
    endpoint = "/customers/search";
    queryParams = {
      q: keyword,
      skip,
      limit,
    };
  }

  // BE filter status dùng /customers/filter?status=
  // Chỉ dùng khi không search, vì BE chưa có API gộp search + status.
  else if (status) {
    endpoint = "/customers/filter";
    queryParams = {
      status,
      skip,
      limit,
    };
  }

  const response = await http.raw.get(endpoint, {
    params: queryParams,
  });

  const json = response.data;

  let data: Customer[] = Array.isArray(json.data) ? json.data : [];

  // BE hiện tại chưa có filter gender, nên gender vẫn phải lọc FE.
  if (gender) {
    data = data.filter((customer) => customer.gender === gender);
  }

  /**
   * Lưu ý:
   * BE hiện tại đang trả total = len(customers),
   * tức là total chỉ bằng số bản ghi của trang hiện tại,
   * không phải tổng toàn bộ DB.
   */
  const total = json.total ?? json.meta?.total ?? data.length;

  return {
    data,
    total,
    page,
    limit,
    total_pages: Math.max(1, Math.ceil(total / limit)),
  };
}

// ─── Filter by status từ BE ───────────────────────────────────────────────────
export async function filterCustomersByStatus(
  status: "active" | "inactive",
  params: Pick<CustomerFilterParams, "page" | "limit"> = {},
): Promise<PaginatedResponse<Customer>> {
  const { page = 1, limit = 10 } = params;

  const skip = (page - 1) * limit;

  const response = await http.raw.get("/customers/filter", {
    params: {
      status,
      skip,
      limit,
    },
  });

  const json = response.data;
  const data: Customer[] = Array.isArray(json.data) ? json.data : [];

  const total = json.total ?? json.meta?.total ?? data.length;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  return {
    data,
    total,
    page,
    limit,
    total_pages: totalPages,
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
