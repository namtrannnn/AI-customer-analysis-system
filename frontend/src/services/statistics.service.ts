/**
 * Dịch vụ gọi API Thống kê khách theo ngày (PB06)
 * Liên kết tới daily_statistics_router.py
 */

import { http } from "@/lib/http";

// ─── Types ──────────────────────────────────────────────

export interface DailyStatisticItem {
  id: number;
  statistic_date: string;
  total_visitors: number;
  new_visitors: number;
  returning_visitors: number;
  identified_visitors: number;
  avg_duration_seconds: number;
  total_orders: number;
  total_revenue: number;
  conversion_rate: number;
}

export interface DailyTrendItem {
  date: string;
  total_visitors: number;
  new_visitors: number;
  returning_visitors: number;
  avg_duration_seconds: number;
}

export interface DailyStatisticsSummary {
  total_visitors: number;
  new_visitors: number;
  returning_visitors: number;
  avg_duration_seconds: number;
  total_orders: number;
  total_revenue: number;
  avg_conversion_rate: number;
  trend: DailyTrendItem[];
}

export interface StatsFilters {
  start_date?: string;
  end_date?: string;
  group_by?: "day" | "week" | "month";
}

// ─── API Requests ──────────────────────────────────────

/**
 * Lấy danh sách thống kê chi tiết theo ngày (phân trang)
 */
export async function getDailyStats(
  filters: StatsFilters,
  skip = 0,
  limit = 30
): Promise<DailyStatisticItem[]> {
  const params: Record<string, any> = { skip, limit };
  if (filters.start_date) params.start_date = filters.start_date;
  if (filters.end_date) params.end_date = filters.end_date;
  return http.get<DailyStatisticItem[]>("/statistics/daily", { params });
}

/**
 * Lấy tổng hợp KPIs + Dữ liệu xu hướng cho biểu đồ
 */
export async function getStatsSummary(
  filters: StatsFilters
): Promise<DailyStatisticsSummary> {
  const params: Record<string, any> = {};
  if (filters.start_date) params.start_date = filters.start_date;
  if (filters.end_date) params.end_date = filters.end_date;
  if (filters.group_by) params.group_by = filters.group_by;
  return http.get<DailyStatisticsSummary>("/statistics/summary", { params });
}

/**
 * Kích hoạt Job đồng bộ dữ liệu cho khoảng ngày
 */
export async function syncStats(
  startDate: string,
  endDate: string
): Promise<{ synced_count: number; dates: string[] }> {
  return http.post<{ synced_count: number; dates: string[] }>(
    "/statistics/sync",
    { start_date: startDate, end_date: endDate }
  );
}

/**
 * Tạo URL download file CSV báo cáo
 */
export function getExportUrl(filters: StatsFilters): string {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "/api";
  const params = new URLSearchParams();
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);
  return `${baseUrl}/statistics/export?${params.toString()}`;
}
