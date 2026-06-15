import axios, { AxiosError } from "axios";
import { getToken } from "@/utils/storage";
const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000/api";

const axiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

function getErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return error instanceof Error ? error.message : "Có lỗi xảy ra";
  }

  const axiosError = error as AxiosError<{
    message?: string;
    detail?: string | Array<{ msg?: string; loc?: unknown[] }>;
    details?: Array<{ msg?: string; loc?: unknown[]; type?: string }>;
  }>;

  const data = axiosError.response?.data;

  if (Array.isArray(data?.details)) {
    return data.details
      .map((item) => {
        const msg = item.msg?.replace(/^Value error,\s*/i, "");
        return msg;
      })
      .filter(Boolean)
      .join(", ");
  }

  if (data?.message) {
    return data.message;
  }

  if (typeof data?.detail === "string") {
    return data.detail;
  }

  if (Array.isArray(data?.detail)) {
    return data.detail
      .map((item) => item.msg)
      .filter(Boolean)
      .join(", ");
  }

  if (axiosError.code === "ERR_NETWORK") {
    return "Không kết nối được API. Kiểm tra backend đã chạy chưa.";
  }

  return "Có lỗi xảy ra khi gọi API";
}
axiosInstance.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = getToken();

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }

  return config;
});

axiosInstance.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    return Promise.reject(new Error(getErrorMessage(error)));
  },
);

export const http = {
  raw: axiosInstance,

  async get<T>(url: string, config = {}): Promise<T> {
    const response = await axiosInstance.get(url, config);
    return response.data.data;
  },

  async post<T>(url: string, data?: unknown, config = {}): Promise<T> {
    const response = await axiosInstance.post(url, data, config);
    return response.data.data;
  },

  async put<T>(url: string, data?: unknown, config = {}): Promise<T> {
    const response = await axiosInstance.put(url, data, config);
    return response.data.data;
  },

  async patch<T>(url: string, data?: unknown, config = {}): Promise<T> {
    const response = await axiosInstance.patch(url, data, config);
    return response.data.data;
  },

  async delete<T>(url: string, config = {}): Promise<T> {
    const response = await axiosInstance.delete(url, config);
    return response.data.data;
  },
};
