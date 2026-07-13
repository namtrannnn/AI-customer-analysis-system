/**
 * Dịch vụ lấy dữ liệu phân tích Thời gian lưu trú (Stay Time Analytics)
 * Liên kết trực tiếp tới các router backend mới tạo (duration_router.py)
 */

import { http } from "@/lib/http";

// Định nghĩa các kiểu dữ liệu cho Frontend

export interface VisitDurationDetail {
  id: number;
  anonymous_id: string;
  customer_name: string | null;
  customer_avatar: string | null;
  entry_time: string;
  exit_time: string | null;
  duration_seconds: number | null;
  is_identified: boolean;
}

export interface DurationTrendItem {
  date: string;
  avg_duration_seconds: number;
  visit_count: number;
}

export interface DurationStatsResponse {
  avg_duration_seconds: number;
  total_visits: number;
  max_duration_seconds: number;
  trend: DurationTrendItem[];
}

export interface DistributionBucket {
  bucket_name: string;
  visit_count: number;
}

export interface CameraListItem {
  id: number;
  camera_name: string;
}

export interface StayTimeFilters {
  start_date?: string;
  end_date?: string;
  camera_id?: number;
}

// ─── API Requests ─────────────────────────────────────────────────────────────

/**
 * Lấy danh sách toàn bộ camera đang hoạt động trong hệ thống
 */
export async function getCamerasList(): Promise<CameraListItem[]> {
  return http.get<CameraListItem[]>("/durations/cameras");
}

/**
 * Lấy danh sách chi tiết các lượt ghé thăm và thời lượng lưu trú
 */
export async function getVisitDurations(
  filters: StayTimeFilters,
  skip = 0,
  limit = 100
): Promise<VisitDurationDetail[]> {
  const params: Record<string, any> = { skip, limit };
  if (filters.start_date) params.start_date = filters.start_date;
  if (filters.end_date) params.end_date = filters.end_date;
  if (filters.camera_id !== undefined && filters.camera_id !== null) {
    params.camera_id = filters.camera_id;
  }
  return http.get<VisitDurationDetail[]>("/durations/visits", { params });
}

/**
 * Lấy thông số KPI tổng hợp và dữ liệu xu hướng lưu trú trung bình theo ngày
 */
export async function getDurationStats(
  filters: StayTimeFilters
): Promise<DurationStatsResponse> {
  const params: Record<string, any> = {};
  if (filters.start_date) params.start_date = filters.start_date;
  if (filters.end_date) params.end_date = filters.end_date;
  if (filters.camera_id !== undefined && filters.camera_id !== null) {
    params.camera_id = filters.camera_id;
  }
  return http.get<DurationStatsResponse>("/durations/stats", { params });
}

/**
 * Lấy danh sách tần suất cho biểu đồ cột phân bố (Histogram)
 */
export async function getDurationDistribution(
  filters: StayTimeFilters
): Promise<DistributionBucket[]> {
  const params: Record<string, any> = {};
  if (filters.start_date) params.start_date = filters.start_date;
  if (filters.end_date) params.end_date = filters.end_date;
  if (filters.camera_id !== undefined && filters.camera_id !== null) {
    params.camera_id = filters.camera_id;
  }
  return http.get<DistributionBucket[]>("/durations/distribution", { params });
}
