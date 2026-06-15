"use client";

import { useState, useEffect, useCallback } from "react";
import UserTable from "@/components/users/UserTable";
import {
  UserAddModal,
  UserEditModal,
  UserDeleteModal,
} from "@/components/users/UserModal";
import Loading from "@/components/ui/Loading";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Select from "@/components/ui/Select";
import { useToast } from "@/components/ui/ToastProvider";
import {
  getUsers,
  createUser,
  updateUser,
  deleteUser,
} from "@/services/user.service";
import type {
  User,
  UserCreatePayload,
  UserUpdatePayload,
  UserFilterParams,
  UserFilterStatus,
} from "@/types/user.type";
import type { PaginatedResponse } from "@/types/customer.type";
import { useDebounce } from "@/hooks/useDebounce";
import { usePermission } from "@/hooks/usePermission";
import {
  AlertCircle,
  AlertTriangle,
  Copy,
  Plus,
  Search,
  Users,
} from "lucide-react";
import ForbiddenPage from "@/components/ui/ForbiddenPage";
import Pagination from "@/components/ui/Pagination";

const DEFAULT_FILTER: UserFilterParams = {
  search: "",
  status: "",
  page: 1,
  limit: 10,
};

const statusOptions: { value: UserFilterStatus | ""; label: string }[] = [
  { value: "", label: "Tất cả trạng thái" },
  { value: "active", label: "Hoạt động" },
  { value: "inactive", label: "Ngừng HĐ" },
];

export default function UsersPage() {
  const { hasPermission } = usePermission();
  const toast = useToast();

  const canViewUser = hasPermission("user.view");
  const canCreateUser = hasPermission("user.create");
  const canUpdateUser = hasPermission("user.update");
  const canDeleteUser = hasPermission("user.delete");

  const [result, setResult] = useState<PaginatedResponse<User> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<UserFilterParams>(DEFAULT_FILTER);

  const [addOpen, setAddOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<User | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const [createdAccount, setCreatedAccount] = useState<{
    username: string;
    temporary_password: string;
  } | null>(null);

  const debouncedSearch = useDebounce(filter.search, 500);

  const fetchData = useCallback(async () => {
    if (!canViewUser) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await getUsers({
        page: filter.page,
        limit: filter.limit,
        status: filter.status,
        search: debouncedSearch,
      });

      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Có lỗi xảy ra");
    } finally {
      setLoading(false);
    }
  }, [canViewUser, filter.page, filter.limit, filter.status, debouncedSearch]);

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

  function updateFilter(partial: Partial<UserFilterParams>) {
    setFilter((prev) => ({
      ...prev,
      ...partial,
    }));
  }

  function resetFilter() {
    setFilter(DEFAULT_FILTER);
  }

  async function handleCreate(payload: UserCreatePayload) {
    if (!canCreateUser) {
      toast.error("Bạn không có quyền thêm người dùng.");
      return;
    }

    try {
      const created = await createUser(payload);

      setCreatedAccount({
        username: created.username,
        temporary_password: created.temporary_password,
      });

      toast.success("Thêm người dùng thành công");
      setAddOpen(false);

      if ((filter.page ?? 1) !== 1) {
        updateFilter({ page: 1 });
      } else {
        await fetchData();
      }
    } catch (e: unknown) {
      toast.error(getApiErrorMessage(e) || "Thêm người dùng thất bại");
      throw e;
    }
  }

  async function handleUpdate(payload: UserUpdatePayload) {
    if (!editTarget) return;

    if (!canUpdateUser) {
      toast.error("Bạn không có quyền cập nhật người dùng.");
      return;
    }

    try {
      await updateUser(editTarget.id, payload);

      toast.success("Cập nhật người dùng thành công");
      setEditTarget(null);
      await fetchData();
    } catch (e: unknown) {
      toast.error(getApiErrorMessage(e) || "Cập nhật thất bại");
      throw e;
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;

    if (!canDeleteUser) {
      toast.error("Bạn không có quyền xóa người dùng.");
      return;
    }

    setDeleteLoading(true);

    try {
      await deleteUser(deleteTarget.id);

      toast.success(`Đã xóa "${deleteTarget.full_name}"`);
      setDeleteTarget(null);
      await fetchData();
    } catch (e: unknown) {
      toast.error(getApiErrorMessage(e) || "Xóa thất bại");
    } finally {
      setDeleteLoading(false);
    }
  }

  const page = filter.page ?? 1;
  const limit = filter.limit ?? 10;
  const totalPages = result?.total_pages ?? 1;
  const hasFilter = Boolean(filter.search || filter.status);

  if (!canViewUser) {
    return (
      <ForbiddenPage
        description="Bạn không có quyền xem danh sách người dùng. Vui lòng liên hệ quản trị viên nếu cần được cấp quyền."
        backHref="/dashboard"
        backLabel="Về Dashboard"
        showHomeButton={false}
      />
    );
  }

  return (
    <div className="space-y-5">
      {createdAccount && (
        <div className="overflow-hidden rounded-3xl border border-emerald-200 bg-emerald-50 shadow-sm dark:border-emerald-500/30 dark:bg-emerald-500/10">
          <div className="flex flex-col gap-3 p-4 text-sm text-emerald-800 dark:text-emerald-200 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="font-bold">Tài khoản vừa tạo</p>
              <p className="mt-1 text-xs opacity-80">
                Vui lòng lưu lại mật khẩu tạm thời. Sau khi đóng thông báo này,
                bạn sẽ không xem lại được mật khẩu.
              </p>

              <div className="mt-3 grid gap-2 rounded-2xl bg-white/70 p-3 dark:bg-slate-900/40">
                <div>
                  <span className="text-xs opacity-70">Tên đăng nhập:</span>{" "}
                  <span className="font-mono font-bold">
                    {createdAccount.username}
                  </span>
                </div>

                <div>
                  <span className="text-xs opacity-70">Mật khẩu tạm thời:</span>{" "}
                  <span className="font-mono font-bold">
                    {createdAccount.temporary_password}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex shrink-0 gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={<Copy className="h-4 w-4" />}
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(
                      `Username: ${createdAccount.username}\nPassword: ${createdAccount.temporary_password}`,
                    );
                    toast.success("Đã copy tài khoản");
                  } catch {
                    toast.error("Không copy được tài khoản");
                  }
                }}
              >
                Copy
              </Button>

              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setCreatedAccount(null)}
              >
                Đóng
              </Button>
            </div>
          </div>
        </div>
      )}

      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="border-b border-slate-200 bg-slate-50 px-4 py-4 dark:border-slate-800 dark:bg-slate-950/40 sm:px-5">
          <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                  Quản lý người dùng
                </h2>

                <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-bold text-blue-700 dark:bg-blue-500/10 dark:text-blue-300">
                  {result?.total ?? 0} người dùng
                </span>

                {hasFilter && (
                  <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-bold text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
                    Đang lọc
                  </span>
                )}
              </div>

              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                Quản lý tài khoản, vai trò và quyền truy cập của nhân viên.
              </p>
            </div>

            {canCreateUser && (
              <div className="flex shrink-0 gap-2">
                <Button
                  size="base"
                  icon={<Plus className="h-4 w-4" />}
                  onClick={() => setAddOpen(true)}
                >
                  Thêm người dùng
                </Button>
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[240px] flex-1">
              <Input
                placeholder="Tìm theo tên, username, email..."
                value={filter.search ?? ""}
                onChange={(e) =>
                  updateFilter({
                    search: e.target.value,
                    page: 1,
                  })
                }
                leftIcon={<Search className="h-4 w-4" />}
              />
            </div>

            <Select<UserFilterStatus | "">
              value={filter.status ?? ""}
              options={statusOptions}
              ariaLabel="Lọc trạng thái"
              onChange={(value) =>
                updateFilter({
                  status: value,
                  page: 1,
                })
              }
            />

            {hasFilter && (
              <Button
                type="button"
                variant="secondary"
                size="base"
                icon={<AlertCircle className="h-4 w-4" />}
                onClick={resetFilter}
                className="h-10 rounded-xl"
              >
                Xóa bộ lọc
              </Button>
            )}
          </div>
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
              người dùng
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
            <Loading text="Đang tải danh sách người dùng..." />
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
              <UserTable
                users={result?.data ?? []}
                canEdit={canUpdateUser}
                canDelete={canDeleteUser}
                onEdit={setEditTarget}
                onDelete={setDeleteTarget}
              />
            </div>
          </div>
        )}

        {!loading && !error && (
          <Pagination
            page={page}
            totalPages={totalPages}
            totalItems={result?.total ?? 0}
            label="người dùng"
            onPageChange={(nextPage) =>
              updateFilter({
                page: nextPage,
              })
            }
          />
        )}
      </section>

      {canCreateUser && (
        <UserAddModal
          open={addOpen}
          onClose={() => setAddOpen(false)}
          onSubmit={handleCreate}
        />
      )}

      {canUpdateUser && (
        <UserEditModal
          open={!!editTarget}
          onClose={() => setEditTarget(null)}
          user={editTarget}
          onSubmit={handleUpdate}
        />
      )}

      {canDeleteUser && (
        <UserDeleteModal
          open={!!deleteTarget}
          onClose={() => setDeleteTarget(null)}
          user={deleteTarget}
          onConfirm={handleDelete}
          loading={deleteLoading}
        />
      )}
    </div>
  );
}
