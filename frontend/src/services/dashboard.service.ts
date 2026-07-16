import { http } from "@/lib/http";

export interface DashboardOverview {
  total_visits: number;
  new_visitors: number;
  returning_visitors: number;
  avg_duration_seconds: number;
}

export interface DashboardTrendPoint {
  label: string;
  total_visits: number;
  new_visitors: number;
  returning_visitors: number;
}

export interface DashboardTrendResponse {
  group_by: "day" | "month" | string;
  data: DashboardTrendPoint[];
}

export interface DashboardFilters {
  start_date?: string;
  end_date?: string;
  group_by?: "day" | "month";
}

function buildParams(filters: DashboardFilters) {
  const params: Record<string, string> = {};
  if (filters.start_date) params.start_date = filters.start_date;
  if (filters.end_date) params.end_date = filters.end_date;
  if (filters.group_by) params.group_by = filters.group_by;
  return params;
}

export async function getDashboardOverview(
  filters: DashboardFilters,
): Promise<DashboardOverview> {
  return http.get<DashboardOverview>("/statistics/overview", {
    params: buildParams(filters),
  });
}

export async function getDashboardTrend(
  filters: DashboardFilters,
): Promise<DashboardTrendResponse> {
  return http.get<DashboardTrendResponse>("/statistics/trend", {
    params: buildParams(filters),
  });
}
