import axios from "axios";

const BASE_URL =
  // process.env.NEXT_PUBLIC_API_URL ||
  // "http://localhost:8000/api" ||
  "http://127.0.0.1:8000/api";

const axiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

axiosInstance.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }

  return config;
});

axiosInstance.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    const message =
      error.response?.data?.message ||
      error.response?.data?.detail ||
      "Có lỗi xảy ra khi gọi API";

    return Promise.reject(new Error(message));
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
