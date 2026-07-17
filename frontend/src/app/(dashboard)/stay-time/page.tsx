/**
 * Trang báo cáo Thống kê Thời gian lưu trú của khách hàng (PB05)
 * Dùng Recharts cho biểu đồ chuyên nghiệp, Lucide cho icon.
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Clock, Calendar, Video, BarChart2, TrendingUp, Users, Info, ChevronLeft, ChevronRight, User } from "lucide-react";
import {
  AreaChart, Area, BarChart as RBarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, LabelList,
} from "recharts";

import { formatDuration, formatDateTime } from "@/utils/formatDate";
import {
  getCamerasList,
  getVisitDurations,
  getDurationStats,
  getDurationDistribution,
  type VisitDurationDetail,
  type DurationStatsResponse,
  type DistributionBucket,
  type CameraListItem,
  type StayTimeFilters
} from "@/services/duration.service";

export default function StayTimePage() {
  const [cameras, setCameras] = useState<CameraListItem[]>([]);
  
  // Bộ lọc tìm kiếm
  const [filters, setFilters] = useState<StayTimeFilters>({
    start_date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split("T")[0], // Mặc định 7 ngày trước
    end_date: new Date().toISOString().split("T")[0], // Hôm nay
    camera_id: undefined,
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // States lưu kết quả phân tích
  const [visits, setVisits] = useState<VisitDurationDetail[]>([]);
  const [stats, setStats] = useState<DurationStatsResponse | null>(null);
  const [distribution, setDistribution] = useState<DistributionBucket[]>([]);

  // Quản lý phân trang cho bảng danh sách
  const [page, setPage] = useState(1);
  const limit = 10;

  // Lấy danh sách camera cho dropdown lọc
  useEffect(() => {
    getCamerasList()
      .then((data) => setCameras(data))
      .catch((err) => console.error("Lỗi lấy danh sách camera:", err));
  }, []);

  // ⚡ BẬT chế độ xem thử biểu đồ với dữ liệu giả (đổi thành false khi có dữ liệu thật)
  const DEMO_CHARTS = false;

  // Fetch dữ liệu từ API mỗi khi bộ lọc thay đổi
  const fetchData = useCallback(() => {
    setLoading(true);
    setError(null);

    Promise.all([
      getVisitDurations(filters, (page - 1) * limit, limit),
      getDurationStats(filters),
      getDurationDistribution(filters),
    ])
      .then(([visitsData, statsData, distributionData]) => {
        setVisits(visitsData);

        // Nếu đang ở chế độ demo → dùng dữ liệu giả cho biểu đồ
        if (DEMO_CHARTS) {
          const start = filters.start_date || new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split("T")[0];
          const end = filters.end_date || new Date().toISOString().split("T")[0];
          
          const generatedTrend = [];
          const startDate = new Date(start);
          const endDate = new Date(end);
          const diffTime = endDate.getTime() - startDate.getTime();
          const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
          const daysToGen = Math.min(Math.max(diffDays + 1, 1), 31); // Limit to max 31 days to keep chart readable
          
          for (let i = 0; i < daysToGen; i++) {
            const tempDate = new Date(startDate);
            tempDate.setDate(startDate.getDate() + i);
            const dateStr = tempDate.toISOString().split("T")[0];
            
            // Generate deterministic but realistic values using a date hash
            const hash = dateStr.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0);
            const avg_dur = 160 + (hash % 260); // 160s to 420s
            const visits = 40 + (hash % 60);    // 40 to 100 visits
            
            generatedTrend.push({
              date: dateStr,
              avg_duration_seconds: avg_dur,
              visit_count: visits
            });
          }

          setStats({
            avg_duration_seconds: 342,
            total_visits: 1247,
            max_duration_seconds: 2460,
            trend: generatedTrend,
          });
          setDistribution([
            { bucket_name: "Dưới 1 phút", visit_count: 187 },
            { bucket_name: "1 - 5 phút", visit_count: 423 },
            { bucket_name: "5 - 10 phút", visit_count: 312 },
            { bucket_name: "10 - 30 phút", visit_count: 245 },
            { bucket_name: "Trên 30 phút", visit_count: 80 },
          ]);
        } else {
          setStats(statsData);
          setDistribution(distributionData);
        }
      })
      .catch((err) => {
        console.error("Lỗi tải báo cáo thời gian lưu trú:", err);
        setError("Không thể tải dữ liệu báo cáo. Vui lòng kiểm tra kết nối.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [filters, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Handler khi thay đổi ô lọc
  const handleFilterChange = (key: keyof StayTimeFilters, value: any) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value === "" ? undefined : value,
    }));
    setPage(1); // Reset về trang 1
  };

  // Tính toán tổng số lượng trang giả định cho phân trang
  const totalVisits = stats?.total_visits || 0;
  const totalPages = Math.max(1, Math.ceil(totalVisits / limit));

  return (
    <div className="space-y-6">
      {/* ── Page Header (Tiêu đề trang) ── */}
      <div>
        <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-indigo-50 dark:bg-indigo-950/40 px-3 py-1 text-xs font-semibold text-indigo-700 dark:text-indigo-400">
          <Clock className="h-3.5 w-3.5" />
          Phân tích hành vi
        </div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
          Thời gian lưu trú của khách
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Phân tích thời lượng ở lại cửa hàng, theo dõi lưu lượng và hành trình ra vào chi tiết.
        </p>
      </div>

      {/* ── Filter Bar (Thanh bộ lọc) ── */}
      <div className="flex flex-wrap items-center gap-4 p-4 bg-white dark:bg-slate-800 rounded-2xl border border-slate-100 dark:border-slate-700/60 shadow-2xs">
        {/* Lọc ngày bắt đầu */}
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-500">Từ:</span>
          <input
            type="date"
            value={filters.start_date || ""}
            onChange={(e) => handleFilterChange("start_date", e.target.value)}
            className="text-xs px-2 py-1.5 border border-slate-200 dark:border-slate-750 dark:bg-slate-900 rounded-lg text-slate-700 dark:text-slate-300"
          />
        </div>

        {/* Lọc ngày kết thúc */}
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-500">Đến:</span>
          <input
            type="date"
            value={filters.end_date || ""}
            onChange={(e) => handleFilterChange("end_date", e.target.value)}
            className="text-xs px-2 py-1.5 border border-slate-200 dark:border-slate-750 dark:bg-slate-900 rounded-lg text-slate-700 dark:text-slate-300"
          />
        </div>

        {/* Lọc theo Camera */}
        <div className="flex items-center gap-2">
          <Video className="h-4 w-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-500">Camera:</span>
          <select
            value={filters.camera_id ?? ""}
            onChange={(e) => handleFilterChange("camera_id", e.target.value ? Number(e.target.value) : "")}
            className="text-xs px-2.5 py-1.5 border border-slate-200 dark:border-slate-750 dark:bg-slate-900 rounded-lg text-slate-700 dark:text-slate-300 bg-white"
          >
            <option value="">Tất cả Camera</option>
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>
                {c.camera_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 text-red-700 rounded-2xl border border-red-200 text-sm">
          {error}
        </div>
      )}

      {/* ── KPI Cards (Chỉ số đo lường) ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* KPI: Thời gian ở lại trung bình */}
        <div className="p-5 bg-white dark:bg-slate-800 rounded-2xl border border-slate-100 dark:border-slate-750 shadow-2xs flex items-center gap-4">
          <div className="h-12 w-12 rounded-2xl bg-indigo-50 dark:bg-indigo-950/40 flex items-center justify-center shrink-0">
            <Clock className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div>
            <p className="text-[10px] font-bold text-slate-450 dark:text-slate-500 uppercase tracking-wide">Trung bình lưu trú</p>
            <p className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 mt-1">
              {loading ? "..." : formatDuration(stats?.avg_duration_seconds)}
            </p>
          </div>
        </div>

        {/* KPI: Tổng lượt khách hàng */}
        <div className="p-5 bg-white dark:bg-slate-800 rounded-2xl border border-slate-100 dark:border-slate-750 shadow-2xs flex items-center gap-4">
          <div className="h-12 w-12 rounded-2xl bg-emerald-50 dark:bg-emerald-950/40 flex items-center justify-center shrink-0">
            <Users className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div>
            <p className="text-[10px] font-bold text-slate-450 dark:text-slate-500 uppercase tracking-wide">Tổng lượt khách hàng</p>
            <p className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 mt-1">
              {loading ? "..." : totalVisits.toLocaleString("vi-VN")}
            </p>
          </div>
        </div>

        {/* KPI: Thời gian lưu trú lâu nhất */}
        <div className="p-5 bg-white dark:bg-slate-800 rounded-2xl border border-slate-100 dark:border-slate-750 shadow-2xs flex items-center gap-4">
          <div className="h-12 w-12 rounded-2xl bg-amber-50 dark:bg-amber-950/40 flex items-center justify-center shrink-0">
            <TrendingUp className="h-6 w-6 text-amber-600 dark:text-amber-400" />
          </div>
          <div>
            <p className="text-[10px] font-bold text-slate-450 dark:text-slate-500 uppercase tracking-wide">Lưu trú lâu nhất</p>
            <p className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 mt-1">
              {loading ? "..." : formatDuration(stats?.max_duration_seconds)}
            </p>
          </div>
        </div>
      </div>

      {/* ── Charts Grid (Khu vực biểu đồ) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* ====== BIỂU ĐỒ ĐƯỜNG (Area Chart) — Xu hướng trung bình ====== */}
        <div className="p-6 bg-white dark:bg-slate-800 rounded-2xl border border-slate-100 dark:border-slate-700/60 shadow-2xs">
          <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wide flex items-center gap-2 mb-4">
            <TrendingUp className="h-4 w-4 text-indigo-500" />
            Biến động thời gian ở lại trung bình (giây)
          </h3>
          
          {loading ? (
            <div className="h-72 bg-slate-50 dark:bg-slate-900/30 animate-pulse rounded-xl" />
          ) : !stats || stats.trend.length === 0 ? (
            <div className="h-72 flex items-center justify-center text-xs text-slate-400">Không có dữ liệu hiển thị</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={stats.trend.map(t => ({ ...t, date: t.date.slice(5) }))}>
                <defs>
                  <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} width={40} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: 'none', borderRadius: 10, fontSize: 12, color: '#fff' }}
                  labelStyle={{ color: '#94a3b8', fontWeight: 600 }}
                  formatter={(value: any) => value !== undefined ? [`${Math.round(Number(value))}s`, 'Trung bình'] : ['', '']}
                />
                <Area
                  type="monotone"
                  dataKey="avg_duration_seconds"
                  stroke="#6366f1"
                  strokeWidth={2.5}
                  fill="url(#trendGrad)"
                  dot={{ r: 4, fill: '#fff', stroke: '#6366f1', strokeWidth: 2.5 }}
                  activeDot={{ r: 6, fill: '#6366f1', stroke: '#fff', strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* ====== BIỂU ĐỒ CỘT (Bar Chart) — Phân bố thời gian ====== */}
        <div className="p-6 bg-white dark:bg-slate-800 rounded-2xl border border-slate-100 dark:border-slate-700/60 shadow-2xs">
          <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wide flex items-center gap-2 mb-4">
            <BarChart2 className="h-4 w-4 text-indigo-500" />
            Phân bố khoảng thời gian ở lại (lượt khách)
          </h3>

          {loading ? (
            <div className="h-72 bg-slate-50 dark:bg-slate-900/30 animate-pulse rounded-xl" />
          ) : distribution.length === 0 ? (
            <div className="h-72 flex items-center justify-center text-xs text-slate-400">Không có dữ liệu hiển thị</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <RBarChart data={distribution} barSize={48}>
                <defs>
                  <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#818cf8" stopOpacity={1} />
                    <stop offset="100%" stopColor="#6366f1" stopOpacity={1} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="bucket_name" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} width={35} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: 'none', borderRadius: 10, fontSize: 12, color: '#fff' }}
                  formatter={(value: any) => value !== undefined ? [`${value} lượt`, 'Số khách'] : ['', '']}
                  cursor={{ fill: '#6366f120' }}
                />
                <Bar dataKey="visit_count" fill="url(#barGrad)" radius={[8, 8, 0, 0]}>
                  <LabelList dataKey="visit_count" position="top" style={{ fontSize: 11, fontWeight: 700, fill: '#6366f1' }} />
                </Bar>
              </RBarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>


      {/* ── Visit Detail Table (Bảng danh sách chi tiết) ── */}
      <div className="bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700/60 rounded-2xl overflow-hidden shadow-2xs">
        <div className="px-6 py-5 border-b border-slate-100 dark:border-slate-750 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wide flex items-center gap-2">
            <Info className="h-4.5 w-4.5 text-indigo-500" />
            Nhật ký ra vào & Thời lượng chi tiết
          </h3>
        </div>

        {loading ? (
          <div className="p-6 space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-10 animate-pulse bg-slate-50 dark:bg-slate-900/30 rounded-xl" />
            ))}
          </div>
        ) : visits.length === 0 ? (
          <div className="p-12 text-center text-sm text-slate-400">Không tìm thấy lượt ghé thăm nào khớp bộ lọc.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/50 dark:bg-slate-900/30 border-b border-slate-100 dark:border-slate-750 text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                  <th className="px-6 py-4">Khách hàng</th>
                  <th className="px-6 py-4">Mã ẩn danh</th>
                  <th className="px-6 py-4">Thời gian vào (Entry)</th>
                  <th className="px-6 py-4">Thời gian ra (Exit)</th>
                  <th className="px-6 py-4">Thời gian ở lại (Duration)</th>
                  <th className="px-6 py-4">Trạng thái</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-750 text-xs">
                {visits.map((v) => (
                  <tr key={v.id} className="hover:bg-slate-50/40 dark:hover:bg-slate-900/25 transition duration-150">
                    <td className="px-6 py-4 flex items-center gap-3">
                      <div className="relative h-8 w-8 rounded-full border border-slate-100 dark:border-slate-700 overflow-hidden bg-slate-50 dark:bg-slate-800 flex items-center justify-center shrink-0">
                        {v.customer_avatar ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={v.customer_avatar} alt="Avatar" className="h-full w-full object-cover" />
                        ) : (
                          <User className="h-4 w-4 text-slate-400" />
                        )}
                      </div>
                      <div>
                        {v.customer_name ? (
                          <Link
                            href={`/customers/${v.anonymous_id}`}
                            className="font-bold text-indigo-600 dark:text-indigo-400 hover:underline hover:text-indigo-700 transition"
                          >
                            {v.customer_name}
                          </Link>
                        ) : (
                          <span className="font-bold text-slate-700 dark:text-slate-300">Khách ẩn danh</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 font-mono font-bold text-slate-500 dark:text-slate-450">
                      {v.anonymous_id}
                    </td>
                    <td className="px-6 py-4 text-slate-600 dark:text-slate-350">
                      {formatDateTime(v.entry_time)}
                    </td>
                    <td className="px-6 py-4 text-slate-600 dark:text-slate-350">
                      {v.exit_time ? formatDateTime(v.exit_time) : "Đang trong quầy"}
                    </td>
                    <td className="px-6 py-4 font-bold text-slate-800 dark:text-slate-200">
                      {v.duration_seconds !== null ? formatDuration(v.duration_seconds) : "—"}
                    </td>
                    <td className="px-6 py-4">
                      {v.is_identified ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-50 text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-400 border border-indigo-100/50">
                          Đã định danh
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-450">
                          Ẩn danh
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Pagination (Phân trang bảng) ── */}
        {!loading && totalVisits > limit && (
          <div className="px-6 py-4 border-t border-slate-100 dark:border-slate-750 flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-450 uppercase tracking-wide">
              Hiển thị {(page - 1) * limit + 1} - {Math.min(page * limit, totalVisits)} trong tổng số {totalVisits} lượt
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-750 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-900 transition shrink-0"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-xs font-bold px-3">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-750 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-900 transition shrink-0"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
