"use client";

import { useState, useEffect, useCallback } from "react";
import CustomerTable from "@/components/customers/CustomerTable";
import CustomerFilter from "@/components/customers/CustomerFilter";
import {
  CustomerAddModal,
  CustomerEditModal,
  CustomerDeleteModal,
} from "@/components/customers/CustomerModal";
import Loading from "@/components/ui/Loading";
import Button from "@/components/ui/Button";
import {
  getCustomers,
  createCustomer,
  updateCustomer,
  deleteCustomer,
} from "@/services/customer.service";
import type {
  Customer,
  CustomerCreatePayload,
  CustomerUpdatePayload,
  CustomerFilterParams,
  PaginatedResponse,
} from "@/types/customer.type";
import { useDebounce } from "@/hooks/useDebounce";
import { useToast } from "@/components/ui/ToastProvider";
import { usePermission } from "@/hooks/usePermission";
import {
  Users,
  UserCheck,
  UserRound,
  Plus,
  AlertTriangle,
  AlertCircle,
  LockKeyhole,
} from "lucide-react";

const DEFAULT_FILTER: CustomerFilterParams = {
  search: "",
  status: "",
  gender: "",
  page: 1,
  limit: 10,
};

function MiniStat({
  label,
  value,
  icon,
  accent,
  description,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  accent: "blue" | "green" | "amber" | "violet";
  description?: string;
}) {
  const styles = {
    blue: {
      box: "bg-blue-50 text-blue-600 ring-blue-100 dark:bg-blue-500/10 dark:text-blue-300 dark:ring-blue-500/20",
    },
    green: {
      box: "bg-emerald-50 text-emerald-600 ring-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/20",
    },
    amber: {
      box: "bg-amber-50 text-amber-600 ring-amber-100 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/20",
    },
    violet: {
      box: "bg-violet-50 text-violet-600 ring-violet-100 dark:bg-violet-500/10 dark:text-violet-300 dark:ring-violet-500/20",
    },
  }[accent];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-3.5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xl font-black leading-none tracking-tight text-slate-900 dark:text-white">
            {value}
          </p>

          <p className="mt-1 text-[11px] font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {label}
          </p>

          {description && (
            <p className="mt-1 truncate text-xs text-slate-400 dark:text-slate-500">
              {description}
            </p>
          )}
        </div>

        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ring-1 ${styles.box}`}
        >
          {icon}
        </div>
      </div>
    </div>
  );
}

function ForbiddenCustomersPage() {
  return (
    <div className="flex min-h-[calc(100vh-140px)] items-center justify-center px-4">
      <div className="max-w-md rounded-3xl border border-red-100 bg-white p-8 text-center shadow-sm dark:border-red-500/20 dark:bg-slate-900">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-300">
          <LockKeyhole className="h-7 w-7" />
        </div>

        <h2 className="mt-4 text-lg font-bold text-slate-900 dark:text-white">
          Không có quyền truy cập
        </h2>

        <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
          Bạn không có quyền xem danh sách khách hàng. Vui lòng liên hệ quản trị
          viên nếu cần được cấp quyền.
        </p>
      </div>
    </div>
  );
}

export default function CustomersPage() {
  const { hasPermission } = usePermission();

  const canViewCustomer = hasPermission("customer.view");
  const canCreateCustomer = hasPermission("customer.create");
  const canUpdateCustomer = hasPermission("customer.update");
  const canDeleteCustomer = hasPermission("customer.delete");

  const [result, setResult] = useState<PaginatedResponse<Customer> | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<CustomerFilterParams>(DEFAULT_FILTER);
  const toast = useToast();
  const [addOpen, setAddOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Customer | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Customer | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const debouncedSearch = useDebounce(filter.search, 500);

  const fetchData = useCallback(async () => {
    if (!canViewCustomer) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await getCustomers({
        page: filter.page,
        limit: filter.limit,
        status: filter.status,
        gender: filter.gender,
        search: debouncedSearch,
      });

      setResult(data);
    } catch (e: unknown) {
      console.error("CUSTOMER API ERROR:", e);
      setError(e instanceof Error ? e.message : "Có lỗi xảy ra");
    } finally {
      setLoading(false);
    }
  }, [
    canViewCustomer,
    filter.page,
    filter.limit,
    filter.status,
    filter.gender,
    debouncedSearch,
  ]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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

  async function handleCreate(payload: CustomerCreatePayload) {
    if (!canCreateCustomer) {
      toast.error("Bạn không có quyền thêm khách hàng.");
      return;
    }

    try {
      const cleanPayload: CustomerCreatePayload = {
        full_name: payload.full_name.trim(),
        gender: payload.gender ?? "male",
      };

      if (payload.phone?.trim()) {
        cleanPayload.phone = payload.phone.trim();
      }

      if (payload.email?.trim()) {
        cleanPayload.email = payload.email.trim();
      }

      if (payload.note?.trim()) {
        cleanPayload.note = payload.note.trim();
      }

      await createCustomer(cleanPayload);

      toast.success(`Đã thêm khách hàng "${payload.full_name}"`);

      setAddOpen(false);

      if ((filter.page ?? 1) !== 1) {
        setFilter((prev) => ({
          ...prev,
          page: 1,
        }));
      } else {
        await fetchData();
      }
    } catch (e: unknown) {
      toast.error(getApiErrorMessage(e));
    }
  }

  async function handleUpdate(payload: CustomerUpdatePayload) {
    if (!editTarget) return;

    if (!canUpdateCustomer) {
      toast.error("Bạn không có quyền cập nhật khách hàng.");
      return;
    }

    try {
      await updateCustomer(editTarget.id, payload);
      toast.success(`Cập nhật thông tin "${payload.full_name}" thành công`);
      await fetchData();
    } catch (e: unknown) {
      toast.error(getApiErrorMessage(e));
      throw e;
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;

    if (!canDeleteCustomer) {
      toast.error("Bạn không có quyền xóa khách hàng.");
      return;
    }

    setDeleteLoading(true);

    try {
      await deleteCustomer(deleteTarget.id);
      toast.success(
        `Đã chuyển "${deleteTarget.full_name}" sang ngừng hoạt động`,
      );

      setDeleteTarget(null);

      await fetchData();
    } catch (e: unknown) {
      toast.error(getApiErrorMessage(e));
    } finally {
      setDeleteLoading(false);
    }
  }

  function updateFilter(partial: Partial<CustomerFilterParams>) {
    setFilter((prev) => ({ ...prev, ...partial }));
  }

  function resetFilter() {
    setFilter(DEFAULT_FILTER);
  }

  const page = filter.page ?? 1;
  const limit = filter.limit ?? 10;
  const totalPages = result?.total_pages ?? 1;

  const allCustomers = result?.data ?? [];
  const activeCount = allCustomers.filter((c) => c.status === "active").length;
  const inactiveCount = allCustomers.filter(
    (c) => c.status === "inactive",
  ).length;
  const anonymousCount = allCustomers.filter(
    (c) => !c.full_name || c.full_name.trim() === "",
  ).length;

  const hasFilter = Boolean(filter.search || filter.status || filter.gender);

  if (!canViewCustomer) {
    return <ForbiddenCustomersPage />;
  }

  return (
    <div className="space-y-5">
      {result && (
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          <MiniStat
            label="Tổng khách"
            value={result.total}
            description="Toàn bộ dữ liệu"
            accent="blue"
            icon={<Users className="h-5 w-5" />}
          />

          <MiniStat
            label="Hoạt động"
            value={activeCount}
            description="Đang active"
            accent="green"
            icon={<UserCheck className="h-5 w-5" />}
          />

          <MiniStat
            label="Ngừng HĐ"
            value={inactiveCount}
            description="Đã ngừng hoạt động"
            accent="amber"
            icon={<AlertCircle className="h-5 w-5" />}
          />

          <MiniStat
            label="Ẩn danh"
            value={anonymousCount}
            description={`Trang ${page}/${totalPages}`}
            accent="violet"
            icon={<UserRound className="h-5 w-5" />}
          />
        </div>
      )}

      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="border-b border-slate-200 bg-slate-50 px-4 py-4 dark:border-slate-800 dark:bg-slate-950/40 sm:px-5">
          <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                  Bộ lọc tìm kiếm
                </h2>

                <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-bold text-blue-700 dark:bg-blue-500/10 dark:text-blue-300">
                  {result?.total ?? 0} khách hàng
                </span>

                {hasFilter && (
                  <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-bold text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
                    Đang lọc
                  </span>
                )}
              </div>

              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                Tìm, lọc và quản lý khách hàng.
              </p>
            </div>

            {canCreateCustomer && (
              <div className="flex shrink-0 gap-2">
                <Button
                  size="base"
                  icon={<Plus className="h-4 w-4" />}
                  onClick={() => setAddOpen(true)}
                >
                  Thêm khách hàng
                </Button>
              </div>
            )}
          </div>

          <CustomerFilter
            params={filter}
            onChange={updateFilter}
            onReset={resetFilter}
          />
        </div>

        {result && (
          <div className="flex flex-col gap-2 border-b border-slate-200 px-4 py-3 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between sm:px-5">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Hiển thị{" "}
              <span className="font-bold text-slate-900 dark:text-white">
                {(page - 1) * limit + 1}–{Math.min(page * limit, result.total)}
              </span>{" "}
              trong tổng số{" "}
              <span className="font-bold text-slate-900 dark:text-white">
                {result.total}
              </span>{" "}
              khách hàng
            </p>

            <div className="flex items-center gap-2 text-xs font-semibold text-slate-400 dark:text-slate-500">
              <span>
                Trang {page}/{totalPages}
              </span>
              <span className="h-1 w-1 rounded-full bg-slate-300 dark:bg-slate-700" />
              <span>{limit} dòng/trang</span>
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex min-h-[360px] items-center justify-center">
            <Loading text="Đang tải danh sách khách hàng..." />
          </div>
        ) : error ? (
          <div className="flex min-h-[360px] flex-col items-center justify-center gap-4 px-6 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50 text-red-500 dark:bg-red-500/10">
              <AlertTriangle className="h-7 w-7" />
            </div>

            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                Không thể tải dữ liệu
              </h3>
              <p className="mt-1 text-sm text-red-500">{error}</p>
            </div>

            <Button variant="secondary" onClick={fetchData} size="sm">
              Thử lại
            </Button>
          </div>
        ) : (
          <div className="px-4 py-4 sm:px-5">
            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950/40">
              <CustomerTable
                customers={result?.data ?? []}
                canEdit={canUpdateCustomer}
                canDelete={canDeleteCustomer}
                onEdit={(c) => setEditTarget(c)}
                onDelete={(c) => setDeleteTarget(c)}
              />
            </div>
          </div>
        )}

        {!loading && !error && totalPages > 1 && (
          <div className="flex flex-col gap-3 border-t border-slate-200 bg-slate-50 px-4 py-4 dark:border-slate-800 dark:bg-slate-950/40 sm:flex-row sm:items-center sm:justify-between sm:px-5">
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
              {result?.total} bản ghi · {totalPages} trang
            </p>

            <div className="flex flex-wrap items-center gap-1.5">
              <button
                type="button"
                onClick={() => updateFilter({ page: page - 1 })}
                disabled={page <= 1}
                className="flex h-9 items-center rounded-xl border border-slate-200 bg-white px-3 text-xs font-bold text-slate-600 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                ← Trước
              </button>

              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .filter(
                  (p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1,
                )
                .reduce<(number | "...")[]>((acc, p, idx, arr) => {
                  if (
                    idx > 0 &&
                    typeof arr[idx - 1] === "number" &&
                    (p as number) - (arr[idx - 1] as number) > 1
                  ) {
                    acc.push("...");
                  }

                  acc.push(p);
                  return acc;
                }, [])
                .map((p, idx) =>
                  p === "..." ? (
                    <span
                      key={`e-${idx}`}
                      className="px-1.5 text-sm font-bold text-slate-400"
                    >
                      …
                    </span>
                  ) : (
                    <button
                      type="button"
                      key={p}
                      onClick={() => updateFilter({ page: p as number })}
                      className={`flex h-9 min-w-9 items-center justify-center rounded-xl border text-xs font-bold transition ${
                        page === p
                          ? "border-blue-600 bg-blue-600 text-white shadow-lg shadow-blue-600/25"
                          : "border-slate-200 bg-white text-slate-600 shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                      }`}
                    >
                      {p}
                    </button>
                  ),
                )}

              <button
                type="button"
                onClick={() => updateFilter({ page: page + 1 })}
                disabled={page >= totalPages}
                className="flex h-9 items-center rounded-xl border border-slate-200 bg-white px-3 text-xs font-bold text-slate-600 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                Sau →
              </button>
            </div>
          </div>
        )}
      </section>

      {canCreateCustomer && (
        <CustomerAddModal
          open={addOpen}
          onClose={() => setAddOpen(false)}
          onSubmit={handleCreate}
        />
      )}

      {canUpdateCustomer && (
        <CustomerEditModal
          open={!!editTarget}
          onClose={() => setEditTarget(null)}
          customer={editTarget}
          onSubmit={handleUpdate}
        />
      )}

      {canDeleteCustomer && (
        <CustomerDeleteModal
          open={!!deleteTarget}
          onClose={() => setDeleteTarget(null)}
          customer={deleteTarget}
          onConfirm={handleDelete}
          loading={deleteLoading}
        />
      )}
    </div>
  );
}
