import { http } from "@/lib/http";

export interface VisitHistoryItem {
  id: number;
  entry_time: string;
  exit_time: string | null;
  duration_seconds: number | null;
  camera_name: string;
}

export interface VisitorProfile {
  id: number;
  anonymous_code: string;
  person_type: "anonymous" | "identified";
  face_image_url: string;
  total_visits: number;
  first_seen_at: string;
  last_seen_at: string;
  customer_name: string | null;
  customer_code: string | null;
  customer_phone: string | null;
  customer_email: string | null;
  customer_gender: string | null;
  customer_spent: number;
  recent_visits: VisitHistoryItem[];
}

export interface VisitorFilters {
  search?: string;
  visitor_type?: "all" | "new" | "returning";
  start_date?: string;
  end_date?: string;
}

interface ApiMeta {
  total: number;
  skip: number;
  limit: number;
}

interface ApiResponse<T> {
  status: string;
  message: string;
  data: T;
  meta?: ApiMeta;
}

interface PersonProfileCustomerSummary {
  id: number;
  customer_code: string;
  full_name: string;
  phone: string | null;
  avatar_url: string | null;
}

interface PersonProfileListItem {
  id: number;
  anonymous_code: string;
  person_type: "anonymous" | "identified";
  visitor_type: "new" | "returning" | "unknown";
  first_seen_at: string | null;
  last_seen_at: string | null;
  total_visits: number;
  confidence_avg: number | null;
  face_image_url: string | null;
  created_at: string;
  customer: PersonProfileCustomerSummary | null;
}

interface PersonProfileVisitSession {
  id: number;
  entry_time: string;
  exit_time: string | null;
  duration_seconds: number | null;
  is_identified: boolean;
  created_at: string;
}

interface PersonProfileDetail extends PersonProfileListItem {
  visit_total: number;
  visit_sessions: PersonProfileVisitSession[];
}

const FALLBACK_FACE_IMAGE =
  "https://placehold.co/150x150/e2e8f0/64748b?text=Face";

function mapVisitSession(visit: PersonProfileVisitSession): VisitHistoryItem {
  return {
    id: visit.id,
    entry_time: visit.entry_time,
    exit_time: visit.exit_time,
    duration_seconds: visit.duration_seconds,
    camera_name: visit.is_identified ? "Camera định danh" : "Camera AI",
  };
}

function mapProfile(profile: PersonProfileListItem): VisitorProfile {
  return {
    id: profile.id,
    anonymous_code: profile.anonymous_code,
    person_type: profile.person_type,
    face_image_url: profile.face_image_url || FALLBACK_FACE_IMAGE,
    total_visits: profile.total_visits,
    first_seen_at: profile.first_seen_at || profile.created_at,
    last_seen_at: profile.last_seen_at || profile.created_at,
    customer_name: profile.customer?.full_name ?? null,
    customer_code: profile.customer?.customer_code ?? null,
    customer_phone: profile.customer?.phone ?? null,
    customer_email: null,
    customer_gender: null,
    customer_spent: 0,
    recent_visits: [],
  };
}

function mapProfileDetail(profile: PersonProfileDetail): VisitorProfile {
  return {
    ...mapProfile(profile),
    recent_visits: profile.visit_sessions.map(mapVisitSession),
  };
}

function buildProfileParams(
  filters: VisitorFilters,
  skip?: number,
  limit?: number,
) {
  return {
    skip,
    limit,
    sort_order: "desc",
    visitor_type: filters.visitor_type ?? "all",
    q: filters.search || undefined,
    start_date: filters.start_date || undefined,
    end_date: filters.end_date || undefined,
  };
}

async function fetchProfilePage(
  filters: VisitorFilters,
  skip = 0,
  limit = 20,
): Promise<{
  profiles: VisitorProfile[];
  total: number;
}> {
  const response = await http.raw.get<ApiResponse<PersonProfileListItem[]>>(
    "/person-profiles",
    {
      params: buildProfileParams(filters, skip, limit),
    },
  );

  return {
    profiles: response.data.data.map(mapProfile),
    total: response.data.meta?.total ?? response.data.data.length,
  };
}

export async function getVisitorProfiles(
  filters: VisitorFilters,
  skip = 0,
  limit = 20,
): Promise<VisitorProfile[]> {
  const { profiles } = await fetchProfilePage(filters, skip, limit);
  return profiles;
}

export async function getVisitorProfileDetail(
  profileId: number,
): Promise<VisitorProfile> {
  const response = await http.raw.get<ApiResponse<PersonProfileDetail>>(
    `/person-profiles/${profileId}`,
    {
      params: {
        visit_skip: 0,
        visit_limit: 100,
      },
    },
  );

  return mapProfileDetail(response.data.data);
}

export async function getVisitorStats(
  filters: VisitorFilters = {},
): Promise<{
  new_count: number;
  returning_count: number;
  total_count: number;
}> {
  const response = await http.raw.get<
    ApiResponse<{
      new_count: number;
      returning_count: number;
      total_count: number;
    }>
  >("/person-profiles/stats", {
    params: {
      q: filters.search || undefined,
      start_date: filters.start_date || undefined,
      end_date: filters.end_date || undefined,
    },
  });

  return response.data.data;
}
