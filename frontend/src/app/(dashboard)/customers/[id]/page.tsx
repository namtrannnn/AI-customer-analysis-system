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
import { useToast } from "@/components/ui/ToastProvider";
import {
  getCustomerById,
  updateCustomer,
  deleteCustomer,
  getCustomerVisitHistory,
  getCustomerOrderHistory,
} from "@/services/customer.service";

import type {
  Customer,
  CustomerUpdatePayload,
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
import { usePermission } from "@/hooks/usePermission";
import {
  AlertTriangle,
  ArrowLeft,
  BadgeInfo,
  CalendarDays,
  CircleDollarSign,
  Clock3,
  CreditCard,
  Edit3,
  Mail,
  MapPin,
  Phone,
  ReceiptText,
  ShoppingBag,
  Trash2,
  UserRound,
  UsersRound,
} from "lucide-react";

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

import ForbiddenPage from "@/components/ui/ForbiddenPage";

export default function CustomerDetailPage() {
  const { hasPermission } = usePermission();

  const canViewCustomer = hasPermission("customer.view");
  const canUpdateCustomer = hasPermission("customer.update");
  const canDeleteCustomer = hasPermission("customer.delete");

  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const customerId = Number(id);
  const toast = useToast();

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [visits, setVisits] = useState<VisitSession[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("visits");

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  useEffect(() => {
    if (!canViewCustomer) {
      setLoading(false);
      return;
    }

    async function load() {
      if (Number.isNaN(customerId)) {
        setError("ID khách hàng không hợp lệ");
        setLoading(false);
        return;
      }

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

    load();
  }, [customerId, canViewCustomer]);

  function getApiErrorMessage(e: unknown) {
    const err = e as {
      response?: {
        data?: {
          detail?: string;
          message?: string;
        };
      };
      message?: string;
    };

    return (
      err.response?.data?.detail ||
      err.response?.data?.message ||
      err.message ||
      "Có lỗi xảy ra"
    );
  }

  async function handleUpdate(payload: CustomerUpdatePayload) {
    if (!customer) return;

    if (!canUpdateCustomer) {
      toast.error("Bạn không có quyền cập nhật khách hàng.");
      return;
    }

    try {
      const updated = await updateCustomer(customer.id, payload);

      setCustomer(updated);
      setEditOpen(false);

      toast.success(
        `Cập nhật thông tin "${
          payload.full_name ?? customer.full_name
        }" thành công`,
      );
    } catch (e: unknown) {
      toast.error(getApiErrorMessage(e));
      throw e;
    }
  }

  async function handleDelete() {
    if (!customer) return;

    if (!canDeleteCustomer) {
      toast.error("Bạn không có quyền xóa khách hàng.");
      return;
    }

    setDeleteLoading(true);

    try {
      await deleteCustomer(customer.id);

      toast.success(`Đã chuyển "${customer.full_name}" sang ngừng hoạt động`);

      setDeleteOpen(false);

      setTimeout(() => {
        router.push("/customers");
      }, 1000);
    } catch (e: unknown) {
      toast.error(getApiErrorMessage(e));
    } finally {
      setDeleteLoading(false);
    }
  }

  if (!canViewCustomer) {
    return (
      <ForbiddenPage
        description="Bạn không có quyền xem chi tiết khách hàng. Vui lòng liên hệ quản trị viên nếu cần được cấp quyền."
        backHref="/customers"
        backLabel="Quay lại danh sách"
      />
    );
  }

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
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-50 text-red-500 dark:bg-red-500/10">
            <AlertTriangle className="h-7 w-7" />
          </div>

          <p className="text-sm text-red-500">
            {error ?? "Không tìm thấy khách hàng"}
          </p>

          <Link href="/customers">
            <Button variant="secondary">
              <ArrowLeft className="mr-1 h-4 w-4" />
              Quay lại danh sách
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const status = statusConfig[customer.status] ?? statusConfig.inactive;

  return (
    <div>
      <nav className="mb-4 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
        <Link
          href="/customers"
          className="inline-flex items-center gap-1 hover:text-blue-600"
        >
          <ArrowLeft className="h-4 w-4" />
          Khách hàng
        </Link>

        <span>/</span>

        <span className="font-medium text-slate-900 dark:text-slate-100">
          {customer.full_name}
        </span>
      </nav>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-full bg-slate-200 shadow ring-2 ring-white dark:bg-slate-700 dark:ring-slate-800">
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

        {(canUpdateCustomer || canDeleteCustomer) && (
          <div className="flex gap-2">
            {canUpdateCustomer && (
              <Button
                variant="secondary"
                size="base"
                onClick={() => setEditOpen(true)}
                icon={<Edit3 className="h-4 w-4" />}
              >
                Chỉnh sửa
              </Button>
            )}

            {canDeleteCustomer && (
              <Button
                variant="danger"
                size="base"
                onClick={() => setDeleteOpen(true)}
                icon={<Trash2 className="h-4 w-4" />}
              >
                Xóa
              </Button>
            )}
          </div>
        )}
      </div>

      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          {
            label: "Lượt ghé",
            value: customer.total_visits.toString(),
            icon: <UsersRound className="h-5 w-5" />,
          },
          {
            label: "Đơn hàng",
            value: customer.total_orders.toString(),
            icon: <ShoppingBag className="h-5 w-5" />,
          },
          {
            label: "Tổng chi tiêu",
            value:
              customer.total_spent > 0
                ? formatCurrency(customer.total_spent)
                : "—",
            icon: <CircleDollarSign className="h-5 w-5" />,
          },
          {
            label: "Ghé gần nhất",
            value: timeAgo(customer.last_visited_at),
            icon: <Clock3 className="h-5 w-5" />,
          },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl bg-white p-4 shadow-sm dark:bg-slate-800 dark:shadow-slate-900/50"
          >
            <div className="mb-2 flex items-center justify-between gap-3">
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {stat.label}
              </p>

              <span className="text-slate-400 dark:text-slate-500">
                {stat.icon}
              </span>
            </div>

            <p className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">
              {stat.value}
            </p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="rounded-xl bg-white p-6 shadow-sm dark:bg-slate-800 dark:shadow-slate-900/50 lg:col-span-1">
          <h2 className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-300">
            Thông tin cá nhân
          </h2>

          <dl className="space-y-3">
            <InfoRow
              icon={<BadgeInfo className="h-4 w-4" />}
              label="Mã KH"
              value={customer.customer_code}
            />

            <InfoRow
              icon={<UserRound className="h-4 w-4" />}
              label="Họ tên"
              value={customer.full_name}
            />

            <InfoRow
              icon={<Phone className="h-4 w-4" />}
              label="Điện thoại"
              value={customer.phone ?? "—"}
            />

            <InfoRow
              icon={<Mail className="h-4 w-4" />}
              label="Email"
              value={customer.email ?? "—"}
            />

            <InfoRow
              icon={<UserRound className="h-4 w-4" />}
              label="Giới tính"
              value={customer.gender ? genderLabel[customer.gender] : "—"}
            />

            <InfoRow
              icon={<BadgeInfo className="h-4 w-4" />}
              label="Trạng thái"
              value={
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${status.className}`}
                >
                  {status.label}
                </span>
              }
            />

            <InfoRow
              icon={<CalendarDays className="h-4 w-4" />}
              label="Ngày tạo"
              value={formatDate(customer.created_at)}
            />

            <InfoRow
              icon={<Clock3 className="h-4 w-4" />}
              label="Cập nhật"
              value={
                customer.updated_at ? formatDateTime(customer.updated_at) : "—"
              }
            />
          </dl>

          {customer.note && (
            <div className="mt-4 rounded-lg bg-slate-50 p-3 dark:bg-slate-700/50">
              <p className="mb-1 text-xs font-medium text-slate-500 dark:text-slate-400">
                Ghi chú
              </p>

              <p className="text-sm text-slate-700 dark:text-slate-300">
                {customer.note}
              </p>
            </div>
          )}
        </div>

        <div className="rounded-xl bg-white shadow-sm dark:bg-slate-800 dark:shadow-slate-900/50 lg:col-span-2">
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
                  className={`border-b-2 px-5 py-3 text-sm font-medium transition ${
                    activeTab === tab.key
                      ? "border-blue-600 text-blue-600"
                      : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          <div className="p-5">
            {activeTab === "visits" && (
              <>
                {visits.length === 0 ? (
                  <p className="py-10 text-center text-sm text-slate-400 dark:text-slate-500">
                    Chưa có lịch sử ghé nào
                  </p>
                ) : (
                  <div className="space-y-3">
                    {visits.map((visit) => (
                      <div
                        key={visit.id}
                        className="flex items-start justify-between rounded-lg border border-slate-100 p-3 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700/40"
                      >
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/30">
                            <MapPin className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                          </div>

                          <div>
                            <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                              {formatDateTime(visit.entry_time)}
                            </p>

                            <p className="text-xs text-slate-500 dark:text-slate-400">
                              Ra:{" "}
                              {visit.exit_time
                                ? formatDateTime(visit.exit_time)
                                : "Chưa ghi nhận"}
                            </p>
                          </div>
                        </div>

                        <div className="text-right">
                          <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                            {formatDuration(visit.duration_seconds)}
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

            {activeTab === "orders" && (
              <>
                {orders.length === 0 ? (
                  <p className="py-10 text-center text-sm text-slate-400 dark:text-slate-500">
                    Chưa có đơn hàng nào
                  </p>
                ) : (
                  <div className="space-y-3">
                    {orders.map((order) => (
                      <div
                        key={order.id}
                        className="flex items-start justify-between rounded-lg border border-slate-100 p-3 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700/40"
                      >
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
                            <ShoppingBag className="h-4 w-4 text-green-600 dark:text-green-400" />
                          </div>

                          <div>
                            <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                              {order.order_code}
                            </p>

                            <p className="text-xs text-slate-500 dark:text-slate-400">
                              {formatDateTime(order.order_time)}
                            </p>

                            {order.item_summary && (
                              <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
                                {order.item_summary}
                              </p>
                            )}
                          </div>
                        </div>

                        <div className="text-right">
                          <p className="text-sm font-semibold text-green-700 dark:text-green-400">
                            {formatCurrency(order.total_amount)}
                          </p>

                          <p className="inline-flex items-center justify-end gap-1 text-xs text-slate-400 dark:text-slate-500">
                            <CreditCard className="h-3.5 w-3.5" />
                            {order.payment_method
                              ? (paymentLabel[order.payment_method] ??
                                order.payment_method)
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

      {canUpdateCustomer && (
        <CustomerEditModal
          open={editOpen}
          onClose={() => setEditOpen(false)}
          customer={customer}
          onSubmit={handleUpdate}
        />
      )}

      {canDeleteCustomer && (
        <CustomerDeleteModal
          open={deleteOpen}
          onClose={() => setDeleteOpen(false)}
          customer={customer}
          onConfirm={handleDelete}
          loading={deleteLoading}
        />
      )}
    </div>
  );
}

function InfoRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="flex shrink-0 items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
        <span className="text-slate-400 dark:text-slate-500">{icon}</span>
        {label}
      </dt>

      <dd className="text-right text-sm text-slate-800 dark:text-slate-200">
        {value}
      </dd>
    </div>
  );
}
