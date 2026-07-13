/**
 * Trang quản lý phân nhóm khách hàng bằng AI (PB08)
 * Sử dụng Recharts PieChart để hiển thị trực quan và Master-Detail layout cho danh sách thành viên.
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Sparkles, Users, RefreshCw, AlertCircle, ShoppingBag,
  Clock, Calendar, User, Eye, Search, CheckCircle2
} from "lucide-react";
import {
  PieChart, Pie, Cell, Tooltip as RTooltip, ResponsiveContainer, Legend
} from "recharts";

import { formatDuration } from "@/utils/formatDate";
import {
  getSegments,
  getSegmentMembers,
  runClustering,
  type SegmentItem,
  type SegmentMember
} from "@/services/segment.service";

// Màu sắc cho các nhóm cụm
const COLORS = ["#f59e0b", "#10b981", "#6366f1", "#ec4899", "#8b5cf6", "#06b6d4"];

export default function CustomerSegmentsPage() {
  // ─── State ──────────────────────────────────────────────
  const [segments, setSegments] = useState<SegmentItem[]>([]);
  const [selectedSegment, setSelectedSegment] = useState<SegmentItem | null>(null);
  const [members, setMembers] = useState<SegmentMember[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [nClusters, setNClusters] = useState(3);

  const [loadingSegments, setLoadingSegments] = useState(true);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [runningAI, setRunningAI] = useState(false);
  const [aiMessage, setAiMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  // ─── Fetch danh sách Segments ──────────────────────────
  const fetchSegmentsList = useCallback(async (selectFirst = false) => {
    setLoadingSegments(true);
    setError(null);
    try {
      const data = await getSegments();
      setSegments(data);
      if (data.length > 0) {
        // Chọn cụm đầu tiên hoặc giữ cụm đã chọn trước đó
        const nextSelect = selectFirst
          ? data[0]
          : (data.find(s => s.id === selectedSegment?.id) || data[0]);
        setSelectedSegment(nextSelect);
      } else {
        setSelectedSegment(null);
      }
    } catch (err) {
      console.error("Lỗi lấy danh sách nhóm:", err);
      setError("Không thể tải danh sách phân nhóm khách hàng.");
    } finally {
      setLoadingSegments(false);
    }
  }, [selectedSegment]);

  // ─── Fetch danh sách thành viên của cụm được chọn ───────
  const fetchMembersList = useCallback(async (segmentId: number) => {
    setLoadingMembers(true);
    try {
      const data = await getSegmentMembers(segmentId);
      setMembers(data);
    } catch (err) {
      console.error("Lỗi lấy thành viên cụm:", err);
    } finally {
      setLoadingMembers(false);
    }
  }, []);

  // Gọi lần đầu
  useEffect(() => {
    fetchSegmentsList(true);
  }, []);

  // Cập nhật thành viên khi chọn cụm thay đổi
  useEffect(() => {
    if (selectedSegment) {
      fetchMembersList(selectedSegment.id);
    } else {
      setMembers([]);
    }
  }, [selectedSegment, fetchMembersList]);

  // ─── Kích hoạt chạy thuật toán AI phân cụm ──────────────
  const handleRunClustering = async () => {
    setRunningAI(true);
    setAiMessage("");
    try {
      const res = await runClustering(nClusters);
      setAiMessage(`✅ ${res.message}`);
      await fetchSegmentsList(true);
    } catch (err: any) {
      console.error("Lỗi chạy AI:", err);
      setAiMessage("❌ Phân cụm thất bại. Hãy chắc chắn DB của bạn có đủ khách hàng (> 3 người).");
    } finally {
      setRunningAI(false);
      setTimeout(() => setAiMessage(""), 5000);
    }
  };

  // ─── Lọc tìm kiếm thành viên ────────────────────────────
  const filteredMembers = members.filter(m => {
    const codeMatch = m.anonymous_code.toLowerCase().includes(searchTerm.toLowerCase());
    const nameMatch = m.customer_name?.toLowerCase().includes(searchTerm.toLowerCase()) || false;
    return codeMatch || nameMatch;
  });

  // Dữ liệu biểu đồ Pie Chart
  const pieData = segments.map((seg, idx) => ({
    name: seg.segment_name,
    value: seg.member_count,
    color: COLORS[idx % COLORS.length]
  }));

  // ─── Render ─────────────────────────────────────────────
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-800 dark:text-white tracking-tight flex items-center gap-2.5">
            <Sparkles className="h-7 w-7 text-amber-500 animate-pulse" />
            Phân nhóm khách hàng AI
          </h1>
          <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">
            Hệ thống tự động phân loại khách hàng dựa trên Tần suất ghé thăm, Thời lượng lưu trú và Lịch sử chi tiêu (K-Means)
          </p>
        </div>

        {/* Cấu hình chạy AI */}
        <div className="flex items-center gap-2 bg-white dark:bg-slate-800 p-2 rounded-2xl border border-slate-100 dark:border-slate-700/60 shadow-2xs">
          <label className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wide px-2">Số cụm:</label>
          <select
            value={nClusters}
            onChange={(e) => setNClusters(Number(e.target.value))}
            className="px-2.5 py-1.5 text-xs font-bold rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 outline-none"
          >
            <option value={2}>2 cụm</option>
            <option value={3}>3 cụm</option>
            <option value={4}>4 cụm</option>
            <option value={5}>5 cụm</option>
          </select>
          <button
            onClick={handleRunClustering}
            disabled={runningAI}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-amber-500 hover:bg-amber-600 text-white transition disabled:opacity-50 shadow-xs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${runningAI ? "animate-spin" : ""}`} />
            {runningAI ? "Đang xử lý..." : "Chạy Phân nhóm"}
          </button>
        </div>
      </div>

      {/* Thông báo tiến trình AI */}
      {aiMessage && (
        <div className="px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700 text-sm font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          {aiMessage}
        </div>
      )}

      {error && (
        <div className="px-4 py-3 rounded-xl bg-red-50 dark:bg-red-900/20 text-sm font-semibold text-red-600 dark:text-red-400 flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {/* Grid Dashboard Phân Nhóm */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Cột trái & giữa: Thẻ Card hiển thị các Segment */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-sm font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
            Danh sách cụm khách hàng ({segments.length})
          </h2>

          {loadingSegments ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-40 bg-slate-50 dark:bg-slate-900/30 animate-pulse rounded-2xl" />
              ))}
            </div>
          ) : segments.length === 0 ? (
            <div className="p-12 text-center bg-white dark:bg-slate-800 rounded-2xl border border-slate-100 dark:border-slate-700/60">
              <Users className="h-12 w-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
              <p className="text-sm text-slate-500 font-semibold">Chưa có dữ liệu phân nhóm nào.</p>
              <p className="text-xs text-slate-400 mt-1 mb-4">Hãy cấu hình số cụm và click nút &quot;Chạy Phân nhóm&quot; để AI tự động phân tích dữ liệu.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {segments.map((seg, idx) => {
                const isSelected = selectedSegment?.id === seg.id;
                const color = COLORS[idx % COLORS.length];

                return (
                  <button
                    key={seg.id}
                    onClick={() => setSelectedSegment(seg)}
                    className={`text-left relative overflow-hidden rounded-2xl border p-5 transition duration-300 shadow-2xs group flex flex-col justify-between h-44 ${isSelected
                        ? "border-amber-500 bg-amber-500/5 dark:bg-amber-500/10 shadow-sm"
                        : "border-slate-100 dark:border-slate-700/60 bg-white dark:bg-slate-800 hover:border-slate-300 dark:hover:border-slate-600"
                      }`}
                  >
                    <div className="relative z-10 w-full">
                      {/* Name & Count */}
                      <div className="flex items-start justify-between gap-3 mb-2">
                        <h3 className="font-extrabold text-slate-800 dark:text-white group-hover:text-amber-500 transition text-sm">
                          {seg.segment_name}
                        </h3>
                        <span
                          className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold text-white shadow-xs"
                          style={{ backgroundColor: color }}
                        >
                          {seg.member_count} khách
                        </span>
                      </div>

                      {/* Description */}
                      <p className="text-xs text-slate-400 dark:text-slate-500 leading-relaxed line-clamp-2">
                        {seg.description || "Chưa có mô tả chi tiết đặc điểm."}
                      </p>
                    </div>

                    {/* Stats Summary */}
                    <div className="relative z-10 grid grid-cols-3 gap-2 pt-3 border-t border-slate-100 dark:border-slate-700/50 mt-3 text-center">
                      <div>
                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-center gap-0.5"><Calendar className="h-3 w-3" /> Ghé thăm</p>
                        <p className="text-xs font-extrabold text-slate-700 dark:text-slate-300 mt-0.5">{seg.avg_visits} lượt</p>
                      </div>
                      <div>
                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-center gap-0.5"><Clock className="h-3 w-3" /> Thời gian</p>
                        <p className="text-xs font-extrabold text-slate-700 dark:text-slate-300 mt-0.5">{formatDuration(Math.round(seg.avg_duration))}</p>
                      </div>
                      <div>
                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-center gap-0.5"><ShoppingBag className="h-3 w-3" /> Chi tiêu</p>
                        <p className="text-xs font-extrabold text-slate-700 dark:text-slate-300 mt-0.5">{seg.avg_spent.toLocaleString()}đ</p>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Cột phải: Biểu đồ tròn trực quan tỷ lệ các cụm */}
        <div className="p-6 bg-white dark:bg-slate-800 rounded-2xl border border-slate-100 dark:border-slate-700/60 shadow-2xs flex flex-col justify-between min-h-[350px]">
          <div>
            <h2 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wide flex items-center gap-2 mb-2">
              <Users className="h-4 w-4 text-amber-500" />
              Tỷ lệ phân bố nhóm
            </h2>
            <p className="text-xs text-slate-400">Tỷ trọng số lượng khách hàng của từng phân cụm trong hệ thống</p>
          </div>

          <div className="h-56 relative flex items-center justify-center">
            {loadingSegments ? (
              <div className="h-36 w-36 rounded-full border-4 border-dashed border-slate-200 dark:border-slate-700 animate-spin" />
            ) : segments.length === 0 ? (
              <div className="text-xs text-slate-400">Không có dữ liệu biểu đồ</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <RTooltip
                    contentStyle={{ background: "#1e293b", border: "none", borderRadius: 8, fontSize: 11, color: "#fff" }}
                    formatter={(value: any) => value !== undefined ? [`${value} khách`, "Số lượng"] : ["", ""]}
                  />
                  <Legend
                    verticalAlign="bottom"
                    iconType="circle"
                    iconSize={8}
                    wrapperStyle={{ fontSize: 10, fontWeight: 600 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* ── Chi tiết thành viên của Segment được chọn (Detail Table) ── */}
      {selectedSegment && (
        <div className="bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700/60 rounded-2xl overflow-hidden shadow-2xs">
          <div className="px-6 py-5 border-b border-slate-100 dark:border-slate-700/60 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wide flex items-center gap-2">
                <User className="h-4 w-4 text-amber-500" />
                Thành viên cụm: {selectedSegment.segment_name}
              </h3>
              <p className="text-xs text-slate-400 mt-1">{selectedSegment.description}</p>
            </div>

            {/* Thanh tìm kiếm */}
            <div className="relative w-full sm:w-64">
              <span className="absolute inset-y-0 left-0 flex items-center pl-3">
                <Search className="h-4 w-4 text-slate-400" />
              </span>
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Tìm mã ẩn danh / tên..."
                className="w-full pl-9 pr-4 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-900 text-slate-700 dark:text-slate-300 outline-none focus:ring-2 focus:ring-amber-500/30 transition"
              />
            </div>
          </div>

          {loadingMembers ? (
            <div className="p-6">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-10 bg-slate-50 dark:bg-slate-900/30 animate-pulse rounded-lg mb-2" />
              ))}
            </div>
          ) : filteredMembers.length === 0 ? (
            <div className="p-12 text-center text-xs text-slate-400">
              Không tìm thấy thành viên nào khớp với từ khóa tìm kiếm.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wider text-slate-400 dark:text-slate-500 bg-slate-50/50 dark:bg-slate-900/30">
                    <th className="px-5 py-3 font-bold">Mã ẩn danh</th>
                    <th className="px-4 py-3 font-bold">Tên khách hàng</th>
                    <th className="px-4 py-3 font-bold text-center">Phân loại</th>
                    <th className="px-4 py-3 font-bold text-center">Tổng số lần ghé</th>
                    <th className="px-4 py-3 font-bold text-center">TB thời gian</th>
                    <th className="px-4 py-3 font-bold text-right">Tổng chi tiêu</th>
                    <th className="px-4 py-3 font-bold text-center">Confidence Score</th>
                    <th className="px-5 py-3 font-bold text-center">Chi tiết</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50 dark:divide-slate-800">
                  {filteredMembers.map((m) => (
                    <tr key={m.person_profile_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-750/30 transition">
                      <td className="px-5 py-3 font-semibold text-slate-700 dark:text-slate-300 font-mono text-xs whitespace-nowrap">
                        {m.anonymous_code}
                      </td>
                      <td className="px-4 py-3 font-semibold text-slate-800 dark:text-slate-200">
                        {m.customer_name || <span className="text-slate-400 text-xs italic">Chưa định danh</span>}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${m.person_type === "identified"
                            ? "bg-indigo-50 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400"
                            : "bg-slate-50 text-slate-500 dark:bg-slate-900/30"
                          }`}>
                          {m.person_type === "identified" ? "Đã định danh" : "Ẩn danh"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center font-bold text-slate-700 dark:text-slate-300">
                        {m.total_visits}
                      </td>
                      <td className="px-4 py-3 text-center text-slate-500 text-xs">
                        {formatDuration(m.avg_duration_seconds)}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-emerald-600 dark:text-emerald-400">
                        {m.total_spent.toLocaleString()}đ
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="text-xs font-bold text-slate-500 bg-slate-100 dark:bg-slate-700 px-2 py-0.5 rounded">
                          {m.score ? `${Math.round(m.score * 100)}%` : "-"}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-center">
                        {m.customer_code ? (
                          <Link
                            href={`/customers/${m.customer_code}`}
                            className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-slate-50 dark:bg-slate-900 text-slate-400 hover:text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-950/20 transition"
                            title="Xem chi tiết hồ sơ khách hàng"
                          >
                            <Eye className="h-4 w-4" />
                          </Link>
                        ) : (
                          <span className="text-slate-300 dark:text-slate-700">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
