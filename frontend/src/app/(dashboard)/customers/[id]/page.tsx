"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import {
  CustomerEditModal,
  CustomerDeleteModal,
} from "@/components/customers/CustomerModal";
import Loading from "@/components/ui/Loading";
import Button from "@/components/ui/Button";
import {
  getCustomerById,
  updateCustomer,
  deleteCustomer,
  getCustomerVisitHistory,
  getCustomerOrderHistory,
} from "@/services/customer.service";
import type {
  Customer,
  CustomerCreatePayload,
  VisitSession,
  Order,
  CustomerStatus,
} from "@/types/customer.type";
import {
  formatDate,
  formatDateTime,
  formatDuration,
  timeAgo,
} from "@/utils/formatDate";
import { formatCurrency } from "@/utils/formatCurrency";

// ─── Status badge ─────────────────────────────────────────────────────────────
const statusConfig: Record<
  CustomerStatus,
  { label: string; className: string }
> = {
  active: {
    label: "Hoạt động",
    className:
      "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  },
  inactive: {
    label: "Ngừng HĐ",
    className:
      "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
  },
  vip: {
    label: "VIP ⭐",
    className:
      "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  },
};

const genderLabel: Record<string, string> = {
  male: "Nam",
  female: "Nữ",
  other: "Khác",
};

const paymentLabel: Record<string, string> = {
  cash: "Tiền mặt",
  credit_card: "Thẻ tín dụng",
  transfer: "Chuyển khoản",
};

type TabKey = "visits" | "orders";

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const customerId = Number(id);

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [visits, setVisits] = useState<VisitSession[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("visits");

  // Modals
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Toast
  const [toast, setToast] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);

  // ─── Load data ───────────────────────────────────────────────────────────────
  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [cust, visitData, orderData] = await Promise.all([
          getCustomerById(customerId),
          getCustomerVisitHistory(customerId),
          getCustomerOrderHistory(customerId),
        ]);
        setCustomer(cust);
        setVisits(visitData);
        setOrders(orderData);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Có lỗi xảy ra");
      } finally {
        setLoading(false);
      }
    }
    if (!isNaN(customerId)) load();
  }, [customerId]);

  // ─── Toast helper ─────────────────────────────────────────────────────────────
  function showToast(type: "success" | "error", msg: string) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  }

  // ─── Handlers ────────────────────────────────────────────────────────────────
  async function handleUpdate(payload: CustomerCreatePayload) {
    if (!customer) return;
    const updated = await updateCustomer(customer.id, payload);
    setCustomer(updated);
    showToast("success", "Cập nhật thông tin thành công");
  }

  async function handleDelete() {
    if (!customer) return;
    setDeleteLoading(true);
    try {
      await deleteCustomer(customer.id);
      showToast("success", `Đã xóa "${customer.full_name}"`);
      setTimeout(() => router.push("/customers"), 1000);
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "Xóa thất bại");
    } finally {
      setDeleteLoading(false);
      setDeleteOpen(false);
    }
  }

  // ─── Render ───────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div>
        <Loading text="Đang tải thông tin khách hàng..." />
      </div>
    );
  }

  if (error || !customer) {
    return (
      <div>
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <p className="text-sm text-red-500">
            {error ?? "Không tìm thấy khách hàng"}
          </p>
          <Link href="/customers">
            <Button variant="secondary">← Quay lại danh sách</Button>
          </Link>
        </div>
      </div>
    );
  }

  const status = statusConfig[customer.status];

  return (
    <div>
      {/* ── Breadcrumb ── */}
      <nav className="mb-4 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
        <Link href="/customers" className="hover:text-blue-600">
          Khách hàng
        </Link>
        <span>/</span>
        <span className="text-slate-900 dark:text-slate-100 font-medium">
          {customer.full_name}
        </span>
      </nav>

      {/* ── Header ── */}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          {/* Avatar */}
          <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700 ring-2 ring-white dark:ring-slate-800 shadow">
            {customer.avatar_url ? (
              <Image
                src={customer.avatar_url}
                alt={customer.full_name}
                fill
                className="object-cover"
                sizes="64px"
              />
            ) : (
              <span className="flex h-full w-full items-center justify-center text-2xl font-bold text-slate-500 dark:text-slate-400">
                {customer.full_name.charAt(0).toUpperCase()}
              </span>
            )}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                {customer.full_name}
              </h1>
              <span
                className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${status.className}`}
              >
                {status.label}
              </span>
            </div>
            <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
              {customer.customer_code}
              {customer.gender && (
                <span className="ml-2 text-slate-400 dark:text-slate-500">
                  · {genderLabel[customer.gender]}
                </span>
              )}
            </p>
          </div>
        </div>

        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setEditOpen(true)}
            icon={
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                />
              </svg>
            }
          >
            Chỉnh sửa
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => setDeleteOpen(true)}
            icon={
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                />
              </svg>
            }
          >
            Xóa
          </Button>
        </div>
      </div>

      {/* ── Stats row ── */}
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: "Lượt ghé", value: customer.total_visits.toString() },
          { label: "Đơn hàng", value: customer.total_orders.toString() },
          {
            label: "Tổng chi tiêu",
            value:
              customer.total_spent > 0
                ? formatCurrency(customer.total_spent)
                : "—",
          },
          { label: "Ghé gần nhất", value: timeAgo(customer.last_visited_at) },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl bg-white dark:bg-slate-800 p-4 shadow-sm dark:shadow-slate-900/50"
          >
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {stat.label}
            </p>
            <p className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">
              {stat.value}
            </p>
          </div>
        ))}
      </div>

      {/* ── Main grid ── */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* ─ Left: Personal info ─ */}
        <div className="rounded-xl bg-white dark:bg-slate-800 p-6 shadow-sm dark:shadow-slate-900/50 lg:col-span-1">
          <h2 className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-300">
            Thông tin cá nhân
          </h2>

          <dl className="space-y-3">
            <InfoRow label="Mã KH" value={customer.customer_code} />
            <InfoRow label="Họ tên" value={customer.full_name} />
            <InfoRow label="Điện thoại" value={customer.phone ?? "—"} />
            <InfoRow label="Email" value={customer.email ?? "—"} />
            <InfoRow
              label="Giới tính"
              value={customer.gender ? genderLabel[customer.gender] : "—"}
            />
            <InfoRow
              label="Trạng thái"
              value={
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${status.className}`}
                >
                  {status.label}
                </span>
              }
            />
            <InfoRow label="Ngày tạo" value={formatDate(customer.created_at)} />
            <InfoRow label="Cập nhật" value={formatDate(customer.updated_at)} />
          </dl>

          {customer.note && (
            <div className="mt-4 rounded-lg bg-slate-50 dark:bg-slate-700/50 p-3">
              <p className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400">
                Ghi chú
              </p>
              <p className="text-sm text-slate-700 dark:text-slate-300">
                {customer.note}
              </p>
            </div>
          )}
        </div>

        {/* ─ Right: History tabs ─ */}
        <div className="rounded-xl bg-white dark:bg-slate-800 shadow-sm dark:shadow-slate-900/50 lg:col-span-2">
          {/* Tabs */}
          <div className="border-b border-slate-200 dark:border-slate-700">
            <nav className="flex">
              {(
                [
                  { key: "visits", label: `Lịch sử ghé (${visits.length})` },
                  { key: "orders", label: `Đơn hàng (${orders.length})` },
                ] as { key: TabKey; label: string }[]
              ).map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`px-5 py-3 text-sm font-medium border-b-2 transition ${
                    activeTab === tab.key
                      ? "border-blue-600 text-blue-600"
                      : "border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          <div className="p-5">
            {/* Visit history */}
            {activeTab === "visits" && (
              <>
                {visits.length === 0 ? (
                  <p className="py-10 text-center text-sm text-slate-400 dark:text-slate-500">
                    Chưa có lịch sử ghé nào
                  </p>
                ) : (
                  <div className="space-y-3">
                    {visits.map((v) => (
                      <div
                        key={v.id}
                        className="flex items-start justify-between rounded-lg border border-slate-100 dark:border-slate-700 p-3 hover:bg-slate-50 dark:hover:bg-slate-700/40"
                      >
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/30">
                            <svg
                              className="h-4 w-4 text-blue-600 dark:text-blue-400"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                              strokeWidth={2}
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                              />
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                              />
                            </svg>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                              {formatDateTime(v.entry_time)}
                            </p>
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                              Ra:{" "}
                              {v.exit_time
                                ? formatDateTime(v.exit_time)
                                : "Chưa ghi nhận"}
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                            {formatDuration(v.duration_seconds)}
                          </p>
                          <p className="text-xs text-slate-400 dark:text-slate-500">
                            thời gian ở
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            {/* Order history */}
            {activeTab === "orders" && (
              <>
                {orders.length === 0 ? (
                  <p className="py-10 text-center text-sm text-slate-400 dark:text-slate-500">
                    Chưa có đơn hàng nào
                  </p>
                ) : (
                  <div className="space-y-3">
                    {orders.map((o) => (
                      <div
                        key={o.id}
                        className="flex items-start justify-between rounded-lg border border-slate-100 dark:border-slate-700 p-3 hover:bg-slate-50 dark:hover:bg-slate-700/40"
                      >
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
                            <svg
                              className="h-4 w-4 text-green-600 dark:text-green-400"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                              strokeWidth={2}
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"
                              />
                            </svg>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                              {o.order_code}
                            </p>
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                              {formatDateTime(o.order_time)}
                            </p>
                            {o.item_summary && (
                              <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
                                {o.item_summary}
                              </p>
                            )}
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-semibold text-green-700 dark:text-green-400">
                            {formatCurrency(o.total_amount)}
                          </p>
                          <p className="text-xs text-slate-400 dark:text-slate-500">
                            {o.payment_method
                              ? (paymentLabel[o.payment_method] ??
                                o.payment_method)
                              : "—"}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* ── Modals ── */}
      <CustomerEditModal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        customer={customer}
        onSubmit={handleUpdate}
      />

      <CustomerDeleteModal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        customer={customer}
        onConfirm={handleDelete}
        loading={deleteLoading}
      />

      {/* ── Toast ── */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-xl px-4 py-3 shadow-lg ${
            toast.type === "success"
              ? "bg-green-600 text-white"
              : "bg-red-600 text-white"
          }`}
          role="alert"
        >
          <span className="text-sm font-medium">{toast.msg}</span>
        </div>
      )}
    </div>
  );
}

// ─── Helper component ─────────────────────────────────────────────────────────
function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="shrink-0 text-xs text-slate-500 dark:text-slate-400">
        {label}
      </dt>
      <dd className="text-right text-sm text-slate-800 dark:text-slate-200">
        {value}
      </dd>
    </div>
  );
}
