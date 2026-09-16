"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import {
  Eye, Search, Calendar, Filter, Users, UserPlus, UserCheck,
  X, Clock, ChevronLeft, ChevronRight, ExternalLink,
  Wifi, WifiOff, MapPin, CheckCircle2, XCircle, Loader2,
  Activity, ListFilter, RefreshCw, User,
} from "lucide-react";

import { formatDuration, formatDateTime } from "@/utils/formatDate";
import {
  getVisitorProfiles,
  getVisitorProfileDetail,
  getVisitorStats,
  type VisitorProfile,
  type VisitorFilters,
  type ZoneVisitItem,
} from "@/services/visit-profiles.service";

// ─── WebSocket URL — đổi thành WS endpoint thật khi có camera ────────────────
// TODO: thay bằng `wss://intership-api.hqsolutions.vn/api/cameras/live/stream`
const REALTIME_WS_URL: string | null = null; // null = chưa có camera

// ─── Mock data để demo UI ─────────────────────────────────────────────────────
// Xóa MOCK_PERSONS khi có camera thật
const MOCK_PERSONS: RealtimePerson[] = [
  {
    track_id: 1,
    anonymous_code: "ANON_0001",
    person_type: "identified",
    customer_name: "Nguyễn Văn An",
    face_image_url: "https://api.dicebear.com/7.x/personas/svg?seed=An",
    zone_name: "Khu trưng bày",
    zone_color: "#6366f1",
    entered_at: new Date(Date.now() - 8 * 60 * 1000).toISOString(),
    confidence: 0.94,
  },
  {
    track_id: 2,
    anonymous_code: "ANON_0002",
    person_type: "anonymous",
    customer_name: null,
    face_image_url: "https://api.dicebear.com/7.x/personas/svg?seed=B2",
    zone_name: "Quầy thanh toán",
    zone_color: "#22c55e",
    entered_at: new Date(Date.now() - 3 * 60 * 1000).toISOString(),
    confidence: 0.81,
  },
  {
    track_id: 3,
    anonymous_code: "ANON_0003",
    person_type: "identified",
    customer_name: "Trần Thị Bích",
    face_image_url: "https://api.dicebear.com/7.x/personas/svg?seed=Bich",
    zone_name: "Khu khuyến mãi",
    zone_color: "#f59e0b",
    entered_at: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
    confidence: 0.97,
  },
  {
    track_id: 4,
    anonymous_code: "ANON_0004",
    person_type: "anonymous",
    customer_name: null,
    face_image_url: "https://api.dicebear.com/7.x/personas/svg?seed=D4",
    zone_name: "Lối vào",
    zone_color: "#14b8a6",
    entered_at: new Date(Date.now() - 1 * 60 * 1000).toISOString(),
    confidence: 0.76,
  },
];

type TabKey = "realtime" | "all";

// ─── Realtime person đang có mặt ─────────────────────────────────────────────
interface RealtimePerson {
  track_id: number;
  anonymous_code: string;
  person_type: "anonymous" | "identified";
  customer_name: string | null;
  face_image_url: string | null;
  zone_name: string | null;
  zone_color: string | null;
  entered_at: string;
  confidence: number;
}

// ─── Zone color dot ──────────────────────────────────────────────────────────
function ZoneDot({ color, name }: { color: string | null; name: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="h-2 w-2 rounded-full shrink-0"
        style={{ background: color ?? "#94a3b8" }}
      />
      <span>{name}</span>
    </span>
  );
}

// ─── Detail drawer ────────────────────────────────────────────────────────────
function ProfileDetail({
  profile,
  onClose,
}: {
  profile: VisitorProfile;
  onClose: () => void;
}) {
  const [activeTab, setActiveTab] = useState<"visits" | "zones">("visits");
  const isNew = profile.total_visits === 1;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-900/60 backdrop-blur-sm">
      <div className="relative w-full sm:max-w-2xl bg-white dark:bg-slate-800 rounded-t-3xl sm:rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">

        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4 shrink-0"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <div className="flex items-center gap-3 min-w-0">
            <div className="relative h-10 w-10 shrink-0">
              <img
                src={profile.face_image_url}
                alt="face"
                className="h-10 w-10 rounded-xl object-cover ring-2 ring-slate-200 dark:ring-slate-700"
              />
              <span className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white dark:border-slate-800 ${
                profile.person_type === "identified" ? "bg-emerald-500" : "bg-slate-400"
              }`} />
            </div>
            <div className="min-w-0">
              <p className="font-bold text-sm truncate" style={{ color: "var(--text-primary)" }}>
                {profile.customer_name ?? profile.anonymous_code}
              </p>
              <p className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
                {profile.anonymous_code}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
              isNew
                ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400"
                : "bg-violet-50 text-violet-600 dark:bg-violet-900/30 dark:text-violet-400"
            }`}>
              {isNew ? "Khách mới" : "Khách cũ"}
            </span>
            <button
              onClick={onClose}
              className="h-8 w-8 flex items-center justify-center rounded-xl hover:bg-slate-100 dark:hover:bg-slate-700 transition"
              style={{ color: "var(--text-muted)" }}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-3 px-5 py-3 shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
          {[
            { label: "Tổng ghé", value: profile.total_visits },
            { label: "Lần đầu", value: formatDateTime(profile.first_seen_at).split(" ")[0] },
            { label: "Lần cuối", value: formatDateTime(profile.last_seen_at).split(" ")[0] },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <p className="text-lg font-black" style={{ color: "var(--text-primary)" }}>{s.value}</p>
              <p className="text-[10px] font-semibold uppercase" style={{ color: "var(--text-muted)" }}>{s.label}</p>
            </div>
          ))}
        </div>

        {/* Customer link */}
        {profile.customer_name ? (
          <div className="mx-5 my-3 rounded-2xl p-3 bg-indigo-50 dark:bg-indigo-950/20 shrink-0">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[10px] font-bold uppercase text-indigo-600 dark:text-indigo-400 mb-0.5">Đã nhận diện</p>
                <p className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>{profile.customer_name}</p>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  {profile.customer_code} · {profile.customer_phone ?? "—"}
                </p>
              </div>
              <Link
                href={`/customers`}
                className="flex items-center gap-1 rounded-xl bg-indigo-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-indigo-700"
              >
                Xem KH <ExternalLink className="h-3 w-3" />
              </Link>
            </div>
          </div>
        ) : (
          <div className="mx-5 my-3 rounded-2xl p-3 shrink-0" style={{ background: "var(--bg-surface-2)" }}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <User className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
                <p className="text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
                  Chưa liên kết với khách hàng
                </p>
              </div>
              {/* TODO: Khi có camera live → bật nút xác nhận danh tính */}
              <button
                disabled
                className="flex items-center gap-1 rounded-xl bg-emerald-600/20 px-3 py-1.5 text-xs font-bold text-emerald-600 dark:text-emerald-400 opacity-50 cursor-not-allowed"
                title="Tính năng này sẽ hoạt động khi có camera live"
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                Xác nhận danh tính
              </button>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div
          className="flex gap-1 mx-5 mb-2 rounded-xl p-1 shrink-0"
          style={{ background: "var(--bg-surface-2)" }}
        >
          {([
            { key: "visits", label: `Lịch sử ghé (${profile.recent_visits.length})` },
            { key: "zones",  label: `Vùng đã đến (${profile.zone_visits.length})` },
          ] as { key: "visits" | "zones"; label: string }[]).map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={`flex-1 rounded-lg py-2 text-xs font-semibold transition-all ${
                activeTab === t.key
                  ? "bg-white shadow-sm text-slate-900 dark:bg-slate-700 dark:text-slate-100"
                  : "text-slate-500 hover:text-slate-700 dark:text-slate-400"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="overflow-y-auto flex-1 px-5 pb-5">
          {activeTab === "visits" ? (
            profile.recent_visits.length === 0 ? (
              <p className="py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>Chưa có lịch sử ghé thăm</p>
            ) : (
              <div className="space-y-2">
                {profile.recent_visits.map((v) => (
                  <div
                    key={v.id}
                    className="flex items-center justify-between rounded-xl px-3 py-2.5"
                    style={{ background: "var(--bg-surface-2)" }}
                  >
                    <div>
                      <p className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                        {formatDateTime(v.entry_time)}
                      </p>
                      <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                        {v.exit_time
                          ? `Ra: ${formatDateTime(v.exit_time)}`
                          : <span className="text-amber-500 font-bold">Đang ở cửa hàng</span>
                        }
                      </p>
                    </div>
                    <span className="text-xs font-bold rounded-lg px-2 py-1 bg-sky-50 text-sky-600 dark:bg-sky-500/10 dark:text-sky-400">
                      {v.duration_seconds ? formatDuration(v.duration_seconds) : "—"}
                    </span>
                  </div>
                ))}
              </div>
            )
          ) : (
            profile.zone_visits.length === 0 ? (
              <p className="py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>Chưa có dữ liệu vùng</p>
            ) : (
              <div className="space-y-2">
                {profile.zone_visits.map((z) => (
                  <div
                    key={z.id}
                    className="flex items-center justify-between rounded-xl px-3 py-2.5"
                    style={{ background: "var(--bg-surface-2)" }}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className="h-3 w-3 shrink-0 rounded-full"
                        style={{ background: z.zone_color ?? "#94a3b8" }}
                      />
                      <div className="min-w-0">
                        <p className="text-xs font-semibold truncate" style={{ color: "var(--text-primary)" }}>
                          {z.zone_name}
                        </p>
                        <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                          {formatDateTime(z.enter_time)}
                        </p>
                      </div>
                    </div>
                    <span className="text-xs font-bold rounded-lg px-2 py-1 bg-teal-50 text-teal-600 dark:bg-teal-500/10 dark:text-teal-400 shrink-0 ml-2">
                      {z.duration_seconds ? formatDuration(z.duration_seconds) : "—"}
                    </span>
                  </div>
                ))}
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Realtime tab ─────────────────────────────────────────────────────────────
function RealtimeTab() {
  const [connected, setConnected] = useState(false);
  const [persons, setPersons] = useState<RealtimePerson[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const isMock = !REALTIME_WS_URL;

  useEffect(() => {
    if (isMock) {
      // Dùng mock data — simulate "connected" sau 800ms
      const t = setTimeout(() => {
        setConnected(true);
        setPersons(MOCK_PERSONS);
      }, 800);
      return () => clearTimeout(t);
    }

    // Khi có camera thật, uncomment:
    // wsRef.current = new WebSocket(REALTIME_WS_URL!);
    // wsRef.current.onopen = () => setConnected(true);
    // wsRef.current.onclose = () => setConnected(false);
    // wsRef.current.onmessage = (e) => {
    //   const data = JSON.parse(e.data);
    //   if (data.type === "presence_update") setPersons(data.persons);
    // };
    // return () => wsRef.current?.close();
  }, [isMock]);

  if (!connected) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 rounded-2xl"
        style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
      >
        <Loader2 className="h-5 w-5 animate-spin" style={{ color: "var(--text-muted)" }} />
        <span className="text-sm" style={{ color: "var(--text-muted)" }}>Đang kết nối...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Connection status */}
      <div className="flex items-center justify-between rounded-2xl px-4 py-3"
        style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${connected ? "bg-emerald-500 animate-pulse" : "bg-red-400"}`} />
          <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            {connected ? "Đang kết nối realtime" : "Mất kết nối"}
          </span>
          {isMock && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-600 dark:bg-amber-900/30 dark:text-amber-400">
              Mock data
            </span>
          )}
        </div>
        <span className="text-xs font-bold rounded-full bg-sky-50 px-2.5 py-0.5 text-sky-600 dark:bg-sky-500/10 dark:text-sky-400">
          {persons.length} người trong cửa hàng
        </span>
      </div>

      {/* Persons grid */}
      {persons.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl py-16"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
        >
          <Activity className="h-8 w-8 text-slate-300" />
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            {connected ? "Không có ai trong cửa hàng lúc này" : "Đang chờ kết nối..."}
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {persons.map((p) => (
            <div key={p.track_id} className="rounded-2xl p-4"
              style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
            >
              <div className="flex items-center gap-3 mb-3">
                <img
                  src={p.face_image_url ?? "https://placehold.co/48x48/e2e8f0/64748b?text=Face"}
                  alt="face"
                  className="h-12 w-12 rounded-xl object-cover ring-2 ring-slate-200 dark:ring-slate-700"
                />
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                    {p.customer_name ?? p.anonymous_code}
                  </p>
                  <p className="text-[11px] font-mono" style={{ color: "var(--text-muted)" }}>{p.anonymous_code}</p>
                </div>
              </div>
              {p.zone_name && (
                <div className="flex items-center gap-1.5 text-xs" style={{ color: "var(--text-secondary)" }}>
                  <MapPin className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-muted)" }} />
                  <ZoneDot color={p.zone_color} name={p.zone_name} />
                </div>
              )}
              <p className="mt-1 text-[11px]" style={{ color: "var(--text-muted)" }}>
                Vào lúc {formatDateTime(p.entered_at)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function VisitorProfilesPage() {
  const [tab, setTab] = useState<TabKey>("all");
  const [profiles, setProfiles] = useState<VisitorProfile[]>([]);
  const [stats, setStats] = useState<{ new_count: number; returning_count: number; total_count: number } | null>(null);
  const [selectedProfile, setSelectedProfile] = useState<VisitorProfile | null>(null);
  const [filters, setFilters] = useState<VisitorFilters>({ search: "", visitor_type: "all", start_date: "", end_date: "" });
  const [loading, setLoading] = useState(true);
  const [detailLoadingId, setDetailLoadingId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const limit = 10;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [profilesData, statsData] = await Promise.all([
        getVisitorProfiles(filters, (page - 1) * limit, limit),
        getVisitorStats(filters),
      ]);
      setProfiles(profilesData);
      setStats(statsData);
    } catch (err) {
      console.error("Lỗi lấy dữ liệu:", err);
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleFilterChange = <K extends keyof VisitorFilters>(key: K, value: VisitorFilters[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const handleViewProfile = async (profile: VisitorProfile) => {
    setDetailLoadingId(profile.id);
    try {
      const detail = await getVisitorProfileDetail(profile.id);
      setSelectedProfile(detail);
    } catch {
      setSelectedProfile(profile);
    } finally {
      setDetailLoadingId(null);
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="mb-1.5 inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
            <Eye className="h-3 w-3" />
            Camera AI
          </div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
            Khách ghé thăm
          </h1>
          <p className="mt-0.5 text-sm" style={{ color: "var(--text-muted)" }}>
            Hồ sơ nhận diện tự động từ camera AI
          </p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-semibold transition hover:bg-slate-50 dark:hover:bg-slate-800"
          style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Làm mới
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Tổng hồ sơ", value: stats.total_count, icon: <Users className="h-5 w-5" />, color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-500/10" },
            { label: "Khách mới",  value: stats.new_count,   icon: <UserPlus className="h-5 w-5" />, color: "text-sky-600 dark:text-sky-400",     bg: "bg-sky-50 dark:bg-sky-500/10" },
            { label: "Quay lại",   value: stats.returning_count, icon: <UserCheck className="h-5 w-5" />, color: "text-violet-600 dark:text-violet-400", bg: "bg-violet-50 dark:bg-violet-500/10" },
          ].map((s) => (
            <div key={s.label} className="rounded-2xl p-4 flex items-center gap-3"
              style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
            >
              <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${s.bg} ${s.color}`}>
                {s.icon}
              </div>
              <div>
                <p className={`text-xl font-black ${s.color}`}>{s.value}</p>
                <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>{s.label}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div
        className="flex gap-1 rounded-xl p-1"
        style={{ background: "var(--bg-surface-2)", border: "1px solid var(--border)" }}
      >
        {([
          { key: "realtime", label: "Đang có mặt", icon: <Activity className="h-4 w-4" />, badge: REALTIME_WS_URL ? "LIVE" : null },
          { key: "all",      label: "Tất cả hồ sơ", icon: <ListFilter className="h-4 w-4" /> },
        ] as { key: TabKey; label: string; icon: React.ReactNode; badge?: string | null }[]).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-semibold transition-all ${
              tab === t.key
                ? "bg-white shadow-sm text-slate-900 dark:bg-slate-700 dark:text-slate-100"
                : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
          >
            {t.icon}
            {t.label}
            {t.badge && (
              <span className="rounded-full bg-red-500 px-1.5 py-0.5 text-[9px] font-black text-white">
                {t.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "realtime" && <RealtimeTab />}

      {tab === "all" && (
        <>
          {/* Filter bar */}
          <div className="flex flex-wrap items-center gap-3 rounded-2xl p-4"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
          >
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: "var(--text-muted)" }} />
              <input
                type="text"
                value={filters.search}
                onChange={(e) => handleFilterChange("search", e.target.value)}
                placeholder="Tìm theo mã ANON hoặc tên khách..."
                className="w-full pl-9 pr-4 py-2 rounded-xl border text-sm outline-none focus:ring-2 focus:ring-emerald-500/30"
                style={{ borderColor: "var(--border)", background: "var(--bg-surface-2)", color: "var(--text-primary)" }}
              />
            </div>
            <select
              value={filters.visitor_type}
              onChange={(e) => handleFilterChange("visitor_type", e.target.value as VisitorFilters["visitor_type"])}
              className="rounded-xl border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500/30"
              style={{ borderColor: "var(--border)", background: "var(--bg-surface-2)", color: "var(--text-primary)" }}
            >
              <option value="all">Tất cả</option>
              <option value="new">Khách mới</option>
              <option value="returning">Khách cũ</option>
            </select>
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 shrink-0" style={{ color: "var(--text-muted)" }} />
              <input type="date" value={filters.start_date}
                onChange={(e) => handleFilterChange("start_date", e.target.value)}
                className="rounded-xl border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500/30"
                style={{ borderColor: "var(--border)", background: "var(--bg-surface-2)", color: "var(--text-primary)" }}
              />
              <span className="text-xs font-semibold" style={{ color: "var(--text-muted)" }}>—</span>
              <input type="date" value={filters.end_date}
                onChange={(e) => handleFilterChange("end_date", e.target.value)}
                className="rounded-xl border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500/30"
                style={{ borderColor: "var(--border)", background: "var(--bg-surface-2)", color: "var(--text-primary)" }}
              />
            </div>
            <button
              onClick={() => { setFilters({ search: "", visitor_type: "all", start_date: "", end_date: "" }); setPage(1); }}
              className="text-xs font-semibold transition hover:text-red-500"
              style={{ color: "var(--text-muted)" }}
            >
              Xóa lọc
            </button>
          </div>

          {/* Table */}
          <div className="overflow-hidden rounded-2xl" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            {loading ? (
              <div className="flex items-center justify-center gap-2 py-16" style={{ color: "var(--text-muted)" }}>
                <Loader2 className="h-5 w-5 animate-spin" />
                <span className="text-sm">Đang tải...</span>
              </div>
            ) : profiles.length === 0 ? (
              <p className="py-12 text-center text-sm" style={{ color: "var(--text-muted)" }}>Không tìm thấy hồ sơ nào</p>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr
                        className="text-left text-[11px] font-bold uppercase tracking-wide"
                        style={{ color: "var(--text-muted)", borderBottom: "1px solid var(--border)", background: "var(--bg-surface-2)" }}
                      >
                        <th className="px-5 py-3">Khuôn mặt</th>
                        <th className="px-4 py-3">Mã ẩn danh</th>
                        <th className="px-4 py-3">Phân loại</th>
                        <th className="px-4 py-3 text-center">Ghé thăm</th>
                        <th className="px-4 py-3">Khách hàng</th>
                        <th className="px-4 py-3">Lần cuối</th>
                        <th className="px-5 py-3 text-center">Chi tiết</th>
                      </tr>
                    </thead>
                    <tbody>
                      {profiles.map((p) => {
                        const isNew = p.total_visits === 1;
                        return (
                          <tr
                            key={p.id}
                            className="transition hover:bg-slate-50/50 dark:hover:bg-white/[0.02]"
                            style={{ borderBottom: "1px solid var(--border)" }}
                          >
                            <td className="px-5 py-3">
                              <img
                                src={p.face_image_url}
                                alt="face"
                                className="h-10 w-10 rounded-xl object-cover ring-2 ring-slate-100 dark:ring-slate-700"
                              />
                            </td>
                            <td className="px-4 py-3 font-mono text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
                              {p.anonymous_code}
                            </td>
                            <td className="px-4 py-3">
                              <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                                isNew
                                  ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400"
                                  : "bg-violet-50 text-violet-600 dark:bg-violet-900/30 dark:text-violet-400"
                              }`}>
                                {isNew ? "Khách mới" : "Khách cũ"}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-center font-black" style={{ color: "var(--text-primary)" }}>
                              {p.total_visits}
                            </td>
                            <td className="px-4 py-3">
                              {p.customer_name ? (
                                <span className="flex items-center gap-1.5 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                                  {p.customer_name}
                                </span>
                              ) : (
                                <span className="text-xs italic" style={{ color: "var(--text-muted)" }}>Chưa liên kết</span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-xs" style={{ color: "var(--text-muted)" }}>
                              {formatDateTime(p.last_seen_at)}
                            </td>
                            <td className="px-5 py-3 text-center">
                              <button
                                onClick={() => handleViewProfile(p)}
                                disabled={detailLoadingId === p.id}
                                className="inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold transition hover:bg-emerald-50 hover:text-emerald-600 dark:hover:bg-emerald-500/10 disabled:opacity-50"
                                style={{ color: "var(--text-secondary)" }}
                              >
                                {detailLoadingId === p.id
                                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                  : <Eye className="h-3.5 w-3.5" />
                                }
                                Xem
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                <div className="flex items-center justify-between px-5 py-3" style={{ borderTop: "1px solid var(--border)" }}>
                  <span className="text-xs font-semibold" style={{ color: "var(--text-muted)" }}>Trang {page}</span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      className="rounded-lg px-3 py-1.5 text-xs font-bold transition disabled:opacity-30"
                      style={{ background: "var(--bg-surface-2)", color: "var(--text-secondary)" }}
                    >
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => setPage((p) => p + 1)}
                      disabled={profiles.length < limit}
                      className="rounded-lg px-3 py-1.5 text-xs font-bold transition disabled:opacity-30"
                      style={{ background: "var(--bg-surface-2)", color: "var(--text-secondary)" }}
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </>
      )}

      {/* Profile detail drawer */}
      {selectedProfile && (
        <ProfileDetail profile={selectedProfile} onClose={() => setSelectedProfile(null)} />
      )}
    </div>
  );
}
