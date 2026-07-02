"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Users,
  UserPlus,
  RefreshCw,
  DollarSign,
  Camera,
  Clock,
  TrendingUp,
} from "lucide-react";
import StatCard from "@/components/common/StatCard";
import CustomerSummaryStats from "@/components/common/CustomerSummaryStats";
import { getCustomers } from "@/services/customer.service";
import { formatCurrency } from "@/utils/formatCurrency";
import { timeAgo } from "@/utils/formatDate";
import type { Customer } from "@/types/customer.type";

// ─── Activity item ─────────────────────────────────────────────────────────────
function ActivityItem({
  color,
  title,
  sub,
  time,
}: {
  color: string;
  title: string;
  sub: string;
  time: string;
}) {
  return (
    <div className="flex items-start gap-3 py-3">
      <div className={`mt-1 h-2 w-2 shrink-0 rounded-full ${color}`} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          {title}
        </p>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>{sub}</p>
      </div>
      <span className="shrink-0 text-xs" style={{ color: "var(--text-muted)" }}>
        {time}
      </span>
    </div>
  );
}

export default function DashboardPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCustomers({ page: 1, limit: 10 })
      .then((res) => {
        setCustomers(res.data);
        setTotal(res.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Compute stats từ dữ liệu thật
  const activeCount = customers.filter((c) => c.status === "active").length;
  const vipCount = customers.filter((c) => c.note?.includes("VIP")).length;
  const returningCount = customers.filter((c) => (c.total_visits ?? 0) > 1).length;
  const newCount = customers.filter((c) => (c.total_visits ?? 0) <= 1).length;
  const totalRevenue = customers.reduce((s, c) => s + (Number(c.total_spent) || 0), 0);

  // Recent visits — khách ghé gần nhất
  const recentVisits = [...customers]
    .filter((c) => c.last_visited_at)
    .sort((a, b) =>
      new Date(b.last_visited_at!).getTime() - new Date(a.last_visited_at!).getTime()
    )
    .slice(0, 5);

  return (
    <div className="space-y-6">
      {/* ── Page title ── */}
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
          Tổng quan
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
          Theo dõi hoạt động hệ thống và chỉ số khách hàng hôm nay.
        </p>
      </div>

      {/* ── FE-10: Customer Summary Stats (tái dụng component) ── */}
      {!loading && (
        <CustomerSummaryStats
          stats={{
            total_customers: total,
            new_customers: newCount,
            returning_customers: returningCount,
          }}
          extraCard={
            <StatCard
              label="Tổng doanh thu"
              value={totalRevenue > 0 ? formatCurrency(totalRevenue) : "—"}
              sub={`${vipCount} khách VIP`}
              gradient="from-amber-500 to-orange-500"
              icon={<DollarSign className="h-5 w-5 text-white" />}
            />
          }
        />
      )}

      {loading && (
        <div className="grid gap-3 sm:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-2xl"
              style={{ background: "var(--bg-surface-2)" }}
            />
          ))}
        </div>
      )}

      {/* ── Content grid ── */}
      <div className="grid gap-5 lg:grid-cols-3">
        {/* ─ Recent visits (2/3) ─ */}
        <div
          className="rounded-2xl p-6 lg:col-span-2"
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Khách hàng gần đây
            </h2>
            <Link href="/customers" className="text-xs font-medium text-blue-600 hover:underline dark:text-blue-400">
              Xem tất cả →
            </Link>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-12 animate-pulse rounded-xl" style={{ background: "var(--bg-surface-2)" }} />
              ))}
            </div>
          ) : recentVisits.length === 0 ? (
            <p className="py-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>
              Chưa có dữ liệu khách hàng
            </p>
          ) : (
            <div className="divide-y" style={{ borderColor: "var(--border)" }}>
              {recentVisits.map((c) => (
                <div key={c.id} className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-slate-100 to-slate-200 text-xs font-bold text-slate-600 dark:from-slate-700 dark:to-slate-600 dark:text-slate-300">
                      {(c.full_name || "K").charAt(0)}
                    </div>
                    <div>
                      <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                        {c.full_name || "Khách ẩn danh"}
                      </p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                        {c.customer_code}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {c.note?.includes("VIP") && (
                      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                        VIP
                      </span>
                    )}
                    <div className="text-right">
                      <p className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                        {timeAgo(c.last_visited_at)}
                      </p>
                      <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                        {c.total_visits} lượt ghé
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ─ Activity feed (1/3) ─ */}
        <div
          className="rounded-2xl p-6"
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Hoạt động
            </h2>
            <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
              Hôm nay
            </span>
          </div>

          <div className="divide-y" style={{ borderColor: "var(--border)" }}>
            <ActivityItem color="bg-green-500"  title="Hệ thống hoạt động bình thường" sub="AI pipeline sẵn sàng" time="Vừa xong" />
            <ActivityItem color="bg-blue-500"   title={`${total} khách đã được phân tích`} sub="Từ dữ liệu hệ thống" time="Hôm nay" />
            <ActivityItem color="bg-amber-500"  title={`${vipCount} khách VIP`} sub="Tỷ lệ cao nhất tuần" time="Tuần này" />
            <ActivityItem color="bg-violet-500" title="Video AI đang chạy" sub="Camera pipeline active" time="Liên tục" />
            <ActivityItem color="bg-teal-500"   title="Zones đang theo dõi" sub="ROI tracking bật" time="Liên tục" />
          </div>
        </div>
      </div>

      {/* ── Bottom metric cards ── */}
      <div className="grid gap-5 sm:grid-cols-3">
        {/* Camera */}
        <div className="rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-700 p-5 text-white shadow-lg shadow-blue-500/20">
          <div className="flex items-center gap-2 mb-2">
            <Camera className="h-4 w-4 text-blue-200" />
            <p className="text-xs font-medium text-blue-200">Camera hoạt động</p>
          </div>
          <p className="text-3xl font-bold">4</p>
          <p className="mt-1 text-xs text-blue-300">/ 6 camera tổng</p>
          <div className="mt-3 flex gap-1">
            {[1,1,1,1,0,0].map((on, i) => (
              <div key={i} className={`h-1.5 w-1.5 rounded-full ${on ? "bg-white" : "bg-blue-400/40"}`} />
            ))}
          </div>
        </div>

        {/* Avg time */}
        <div
          className="rounded-2xl p-5"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", boxShadow: "var(--shadow-sm)" }}
        >
          <div className="flex items-center gap-2 mb-2">
            <Clock className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
            <p className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>Thời gian ở lại TB</p>
          </div>
          <p className="text-3xl font-bold" style={{ color: "var(--text-primary)" }}>42 phút</p>
          <div className="mt-1.5 inline-flex items-center gap-1 rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-600 dark:bg-green-900/30 dark:text-green-400">
            <svg className="h-3 w-3" viewBox="0 0 12 12" fill="currentColor"><path d="M6 2l4 6H2l4-6z" /></svg>
            +5 phút vs tuần trước
          </div>
        </div>

        {/* Conversion */}
        <div
          className="rounded-2xl p-5"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", boxShadow: "var(--shadow-sm)" }}
        >
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="h-4 w-4" style={{ color: "var(--text-muted)" }} />
            <p className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>Tỷ lệ chuyển đổi</p>
          </div>
          <p className="text-3xl font-bold" style={{ color: "var(--text-primary)" }}>
            {total > 0 ? `${Math.round((activeCount / total) * 100)}%` : "—"}
          </p>
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full" style={{ background: "var(--bg-surface-3)" }}>
            <div
              className="h-2 rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 transition-all"
              style={{ width: total > 0 ? `${(activeCount / total) * 100}%` : "0%" }}
            />
          </div>
          <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
            {activeCount} / {total} khách hoạt động
          </p>
        </div>
      </div>
    </div>
  );
}
