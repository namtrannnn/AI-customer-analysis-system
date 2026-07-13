/**
 * Trang danh sách khách ghé thăm lọt camera AI (PB04)
 * Thiết kế theo chuẩn giao diện cao cấp, Master-Detail Popup và đầy đủ các bộ lọc phân loại cũ/mới.
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Eye, Search, Calendar, Filter, Users, UserPlus, UserCheck,
  X, Clock, Video, ChevronLeft, ChevronRight, Info, ExternalLink,
  Info as DetailsIcon
} from "lucide-react";

import { formatDuration, formatDateTime } from "@/utils/formatDate";
import {
  getVisitorProfiles,
  getVisitorStats,
  type VisitorProfile,
  type VisitorFilters
} from "@/services/visit-profiles.service";

export default function VisitorProfilesPage() {
  // ─── State ──────────────────────────────────────────────
  const [profiles, setProfiles] = useState<VisitorProfile[]>([]);
  const [stats, setStats] = useState<{ new_count: number; returning_count: number; total_count: number } | null>(null);
  const [selectedProfile, setSelectedProfile] = useState<VisitorProfile | null>(null);

  const [filters, setFilters] = useState<VisitorFilters>({
    search: "",
    visitor_type: "all",
    start_date: "",
    end_date: ""
  });

  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const limit = 10;

  // ─── Fetch data ─────────────────────────────────────────
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [profilesData, statsData] = await Promise.all([
        getVisitorProfiles(filters, (page - 1) * limit, limit),
        getVisitorStats()
      ]);
      setProfiles(profilesData);
      setStats(statsData);
    } catch (err) {
      console.error("Lỗi lấy dữ liệu khách ghé thăm:", err);
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ─── Handlers ───────────────────────────────────────────
  const handleFilterChange = (key: keyof VisitorFilters, value: any) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const resetFilters = () => {
    setFilters({
      search: "",
      visitor_type: "all",
      start_date: "",
      end_date: ""
    });
    setPage(1);
  };

  // ─── Render ─────────────────────────────────────────────
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold text-slate-800 dark:text-white tracking-tight flex items-center gap-2.5">
          <Eye className="h-7 w-7 text-emerald-500" />
          Khách ghé thăm camera
        </h1>
        <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">
          Hồ sơ nhận diện tự động từ camera AI, phân loại khách hàng cũ/mới và liên kết thông tin thẻ VIP
        </p>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white dark:bg-slate-800 p-4 rounded-2xl border border-slate-100 dark:border-slate-700/60 shadow-2xs flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Tổng nhận diện</p>
              <p className="text-lg font-extrabold text-slate-800 dark:text-white mt-0.5">{stats.total_count} hồ sơ</p>
            </div>
          </div>
          <div className="bg-white dark:bg-slate-800 p-4 rounded-2xl border border-slate-100 dark:border-slate-700/60 shadow-2xs flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-sky-500/10 text-sky-600 flex items-center justify-center">
              <UserPlus className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Khách mới (New)</p>
              <p className="text-lg font-extrabold text-slate-800 dark:text-white mt-0.5">{stats.new_count} hồ sơ</p>
            </div>
          </div>
          <div className="bg-white dark:bg-slate-800 p-4 rounded-2xl border border-slate-100 dark:border-slate-700/60 shadow-2xs flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-violet-500/10 text-violet-600 flex items-center justify-center">
              <UserCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Khách quay lại (Returning)</p>
              <p className="text-lg font-extrabold text-slate-800 dark:text-white mt-0.5">{stats.returning_count} hồ sơ</p>
            </div>
          </div>
        </div>
      )}

      {/* Filter Component */}
      <div className="flex flex-wrap items-center gap-3 p-4 bg-white dark:bg-slate-800 rounded-2xl border border-slate-100 dark:border-slate-700/60 shadow-2xs">
        {/* Search */}
        <div className="relative flex-1 min-w-[240px]">
          <span className="absolute inset-y-0 left-0 flex items-center pl-3">
            <Search className="h-4 w-4 text-slate-400" />
          </span>
          <input
            type="text"
            value={filters.search}
            onChange={(e) => handleFilterChange("search", e.target.value)}
            placeholder="Tìm theo mã ANON hoặc tên khách..."
            className="w-full pl-9 pr-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm text-slate-700 dark:text-slate-300 focus:ring-2 focus:ring-emerald-500/30 outline-none"
          />
        </div>

        {/* Filter Type */}
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-slate-400" />
          <select
            value={filters.visitor_type}
            onChange={(e) => handleFilterChange("visitor_type", e.target.value)}
            className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm text-slate-700 dark:text-slate-300 focus:ring-2 focus:ring-emerald-500/30 outline-none font-semibold"
          >
            <option value="all">Tất cả loại khách</option>
            <option value="new">Khách mới (New)</option>
            <option value="returning">Khách quay lại (Returning)</option>
          </select>
        </div>

        {/* Date Filters */}
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-slate-400" />
          <input
            type="date"
            value={filters.start_date}
            onChange={(e) => handleFilterChange("start_date", e.target.value)}
            className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm text-slate-700 dark:text-slate-300 focus:ring-2 focus:ring-emerald-500/30 outline-none"
          />
          <span className="text-slate-400 text-xs font-bold uppercase">đến</span>
          <input
            type="date"
            value={filters.end_date}
            onChange={(e) => handleFilterChange("end_date", e.target.value)}
            className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm text-slate-700 dark:text-slate-300 focus:ring-2 focus:ring-emerald-500/30 outline-none"
          />
        </div>

        {/* Clear Filters */}
        <button
          onClick={resetFilters}
          className="px-3 py-2 text-xs font-bold text-slate-400 hover:text-slate-600 dark:hover:text-white transition"
        >
          Xóa lọc
        </button>
      </div>

      {/* Main Visitor List Table */}
      <div className="bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700/60 rounded-2xl overflow-hidden shadow-2xs">
        {loading ? (
          <div className="p-6 space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-12 bg-slate-50 dark:bg-slate-900/30 animate-pulse rounded-lg" />
            ))}
          </div>
        ) : profiles.length === 0 ? (
          <div className="p-12 text-center text-sm text-slate-400 font-semibold">
            Không tìm thấy hồ sơ khách ghé thăm nào.
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wider text-slate-400 dark:text-slate-500 bg-slate-50/50 dark:bg-slate-900/30">
                    <th className="px-6 py-4 font-bold">Khuôn mặt</th>
                    <th className="px-4 py-4 font-bold">Mã ẩn danh</th>
                    <th className="px-4 py-4 font-bold">Phân loại</th>
                    <th className="px-4 py-4 font-bold text-center">Tổng số lần ghé</th>
                    <th className="px-4 py-4 font-bold">Thành viên liên kết</th>
                    <th className="px-4 py-4 font-bold">Lần cuối lọt camera</th>
                    <th className="px-6 py-4 font-bold text-center">Hành động</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50 dark:divide-slate-800">
                  {profiles.map((p) => {
                    const isNew = p.total_visits === 1;
                    return (
                      <tr key={p.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-750/30 transition">
                        {/* Chân dung */}
                        <td className="px-6 py-3 whitespace-nowrap">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={p.face_image_url}
                            alt="Face"
                            className="h-10 w-10 rounded-xl object-cover ring-2 ring-slate-100 dark:ring-slate-700 shadow-xs"
                          />
                        </td>
                        {/* Code */}
                        <td className="px-4 py-3 font-semibold text-slate-700 dark:text-slate-300 font-mono text-xs whitespace-nowrap">
                          {p.anonymous_code}
                        </td>
                        {/* Badge Phân loại */}
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                            isNew
                              ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400"
                              : "bg-violet-50 text-violet-600 dark:bg-violet-900/30 dark:text-violet-400"
                          }`}>
                            {isNew ? "Khách Mới (New)" : "Khách Cũ (Returning)"}
                          </span>
                        </td>
                        {/* Số lần ghé */}
                        <td className="px-4 py-3 text-center font-extrabold text-slate-700 dark:text-slate-300">
                          {p.total_visits}
                        </td>
                        {/* Member link */}
                        <td className="px-4 py-3 font-semibold text-slate-800 dark:text-slate-200 whitespace-nowrap">
                          {p.customer_name ? (
                            <span className="flex items-center gap-1.5 text-slate-800 dark:text-slate-200">
                              <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" />
                              {p.customer_name}
                            </span>
                          ) : (
                            <span className="text-slate-400 text-xs italic font-normal">Chưa liên kết VIP</span>
                          )}
                        </td>
                        {/* Lần cuối */}
                        <td className="px-4 py-3 text-xs text-slate-500 font-medium whitespace-nowrap">
                          {formatDateTime(p.last_seen_at)}
                        </td>
                        {/* Xem chi tiết */}
                        <td className="px-6 py-3 text-center whitespace-nowrap">
                          <button
                            onClick={() => setSelectedProfile(p)}
                            className="inline-flex h-8 px-3 items-center justify-center gap-1 rounded-lg bg-slate-50 dark:bg-slate-900 text-xs font-bold text-slate-500 hover:text-emerald-500 hover:bg-emerald-50 dark:hover:bg-emerald-950/20 transition"
                          >
                            <DetailsIcon className="h-3.5 w-3.5" />
                            Xem hồ sơ
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 dark:border-slate-700/60">
              <span className="text-xs font-semibold text-slate-400">Trang {page}</span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-50 dark:bg-slate-900/30 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-30 transition"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => setPage(p => p + 1)}
                  disabled={profiles.length < limit}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-50 dark:bg-slate-900/30 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-30 transition"
                >
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* ── Pop-up Modal Hồ sơ chi tiết (selectedProfile) ── */}
      {selectedProfile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="relative w-full max-w-2xl bg-white dark:bg-slate-800 rounded-3xl border border-slate-100 dark:border-slate-700/60 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            
            {/* Header / Close button */}
            <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100 dark:border-slate-700/60">
              <div className="flex items-center gap-2">
                <Eye className="h-5 w-5 text-emerald-500" />
                <h2 className="text-base font-extrabold text-slate-800 dark:text-white uppercase tracking-wide">
                  Chi tiết hồ sơ: {selectedProfile.anonymous_code}
                </h2>
              </div>
              <button
                onClick={() => setSelectedProfile(null)}
                className="h-8 w-8 flex items-center justify-center rounded-xl bg-slate-50 dark:bg-slate-900 hover:bg-red-50 text-slate-400 hover:text-red-500 dark:hover:bg-red-950/20 transition"
              >
                <X className="h-4.5 w-4.5" />
              </button>
            </div>

            {/* Content */}
            <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
              {/* Profile Card & Info */}
              <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6">
                {/* Face Image */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={selectedProfile.face_image_url}
                  alt="Profile"
                  className="h-28 w-28 rounded-2xl object-cover ring-4 ring-slate-100 dark:ring-slate-700 shadow-md"
                />

                {/* Core details */}
                <div className="flex-1 space-y-3 w-full">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                        <Clock className="h-3 w-3" /> Lần đầu ghé
                      </p>
                      <p className="text-xs font-semibold text-slate-700 dark:text-slate-300 mt-0.5">
                        {formatDateTime(selectedProfile.first_seen_at)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                        <Clock className="h-3 w-3" /> Lần cuối lọt camera
                      </p>
                      <p className="text-xs font-semibold text-slate-700 dark:text-slate-300 mt-0.5">
                        {formatDateTime(selectedProfile.last_seen_at)}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Tổng số lần xuất hiện</p>
                      <p className="text-sm font-extrabold text-slate-800 dark:text-white mt-0.5">
                        {selectedProfile.total_visits} lần
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Loại khách hàng</p>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold mt-0.5 ${
                        selectedProfile.total_visits === 1
                          ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30"
                          : "bg-violet-50 text-violet-600 dark:bg-violet-900/30"
                      }`}>
                        {selectedProfile.total_visits === 1 ? "Khách Mới (New)" : "Khách Cũ (Returning)"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* VIP Member connection details */}
              {selectedProfile.customer_name ? (
                <div className="p-4 bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-100/40 dark:border-indigo-900/40 rounded-2xl">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-xs font-extrabold text-indigo-600 dark:text-indigo-400 uppercase tracking-wide">
                      Thành viên VIP liên kết
                    </h4>
                    <Link
                      href={`/customers/${selectedProfile.customer_code}`}
                      className="text-xs font-bold text-indigo-500 hover:text-indigo-600 flex items-center gap-0.5"
                    >
                      Hồ sơ VIP <ExternalLink className="h-3 w-3" />
                    </Link>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                    <div>
                      <p className="text-[9px] font-bold text-slate-400 uppercase">Họ và tên</p>
                      <p className="font-semibold text-slate-700 dark:text-slate-300">{selectedProfile.customer_name}</p>
                    </div>
                    <div>
                      <p className="text-[9px] font-bold text-slate-400 uppercase">Mã khách hàng</p>
                      <p className="font-semibold text-slate-700 dark:text-slate-300">{selectedProfile.customer_code}</p>
                    </div>
                    <div>
                      <p className="text-[9px] font-bold text-slate-400 uppercase">Số điện thoại</p>
                      <p className="font-semibold text-slate-700 dark:text-slate-300">{selectedProfile.customer_phone}</p>
                    </div>
                    <div>
                      <p className="text-[9px] font-bold text-slate-400 uppercase">Tổng chi tiêu</p>
                      <p className="font-bold text-emerald-600 dark:text-emerald-400">{selectedProfile.customer_spent.toLocaleString()}đ</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-4 bg-slate-50 dark:bg-slate-900/50 border border-slate-100 dark:border-slate-700/60 rounded-2xl flex items-center gap-2">
                  <Info className="h-4 w-4 text-slate-400" />
                  <span className="text-xs text-slate-400 font-semibold">
                    Hồ sơ camera ẩn danh chưa được định danh liên kết với tài khoản thành viên VIP.
                  </span>
                </div>
              )}

              {/* Lịch sử di chuyển Timeline */}
              <div className="space-y-3">
                <h4 className="text-xs font-extrabold text-slate-800 dark:text-slate-200 uppercase tracking-wide flex items-center gap-1.5">
                  <Video className="h-4 w-4 text-emerald-500" />
                  Nhật ký lọt camera gần đây
                </h4>
                <div className="border border-slate-100 dark:border-slate-700/60 rounded-2xl overflow-hidden">
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="bg-slate-50/50 dark:bg-slate-900/30 text-slate-400 font-bold uppercase tracking-wider text-[9px] border-b border-slate-100 dark:border-slate-700/60">
                        <th className="px-4 py-2.5">Thời gian vào</th>
                        <th className="px-4 py-2.5">Thời gian ra</th>
                        <th className="px-4 py-2.5">Thời lượng ở lại</th>
                        <th className="px-4 py-2.5">Vị trí ghi nhận</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50 dark:divide-slate-800">
                      {selectedProfile.recent_visits.map((visit) => (
                        <tr key={visit.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-750/10">
                          <td className="px-4 py-2.5 font-medium text-slate-600 dark:text-slate-300">
                            {formatDateTime(visit.entry_time)}
                          </td>
                          <td className="px-4 py-2.5 font-medium text-slate-600 dark:text-slate-300">
                            {visit.exit_time ? formatDateTime(visit.exit_time) : <span className="text-amber-500 font-bold">Đang ở cửa hàng</span>}
                          </td>
                          <td className="px-4 py-2.5 text-slate-500 font-semibold">
                            {visit.duration_seconds ? formatDuration(visit.duration_seconds) : "-"}
                          </td>
                          <td className="px-4 py-2.5 text-slate-500 font-medium">
                            {visit.camera_name}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Bottom Actions */}
            <div className="flex justify-end gap-2 px-6 py-4 bg-slate-50/50 dark:bg-slate-900/30 border-t border-slate-100 dark:border-slate-700/60">
              <button
                onClick={() => setSelectedProfile(null)}
                className="px-4 py-2 rounded-xl text-xs font-bold bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-750 transition"
              >
                Đóng hồ sơ
              </button>
            </div>

          </div>
        </div>
      )}
    </div>
  );
}
