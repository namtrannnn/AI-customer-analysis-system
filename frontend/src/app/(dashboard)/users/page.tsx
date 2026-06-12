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

const DEFAULT_FILTER: UserFilterParams = {
  search: "",
  status: "",
  page: 1,
  limit: 10,
};

export default function UsersPage() {
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

  const [toast, setToast] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);

  const debouncedSearch = useDebounce(filter.search, 400);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await getUsers({
        ...filter,
        search: debouncedSearch,
      });

      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Có lỗi xảy ra");
    } finally {
      setLoading(false);
    }
  }, [filter, debouncedSearch]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  function showToast(type: "success" | "error", msg: string) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  }

  async function handleCreate(payload: UserCreatePayload, roleIds: number[]) {
    try {
      const created = await createUser({
        ...payload,
        role_ids: roleIds,
      });

      setCreatedAccount({
        username: created.username,
        temporary_password: created.temporary_password,
      });

      showToast("success", "Thêm người dùng thành công");
      setAddOpen(false);
      fetchData();
    } catch (e: unknown) {
      showToast(
        "error",
        e instanceof Error ? e.message : "Thêm người dùng thất bại",
      );
      throw e;
    }
  }

  async function handleUpdate(payload: UserUpdatePayload, roleIds: number[]) {
    if (!editTarget) return;

    const finalPayload = {
      ...payload,
      role_ids: roleIds,
    };

    console.log("UPDATE ID:", editTarget.id);
    console.log("UPDATE PAYLOAD:", finalPayload);

    try {
      await updateUser(editTarget.id, finalPayload);

      showToast("success", "Cập nhật thành công");
      setEditTarget(null);
      fetchData();
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "Cập nhật thất bại");
      throw e;
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;

    setDeleteLoading(true);

    try {
      await deleteUser(deleteTarget.id);

      showToast("success", `Đã xóa "${deleteTarget.full_name}"`);
      setDeleteTarget(null);
      fetchData();
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "Xóa thất bại");
    } finally {
      setDeleteLoading(false);
    }
  }

  const page = filter.page ?? 1;
  const totalPages = result?.total_pages ?? 1;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
            Quản lý người dùng
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Quản lý tài khoản, vai trò và quyền truy cập của nhân viên.
          </p>
        </div>

        <Button
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
                d="M12 4v16m8-8H4"
              />
            </svg>
          }
          onClick={() => setAddOpen(true)}
        >
          Thêm người dùng
        </Button>
      </div>

      {createdAccount && (
        <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200">
          <div className="mb-2 flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold">Tài khoản vừa tạo</p>
              <p className="mt-1 text-xs opacity-80">
                Vui lòng lưu lại mật khẩu tạm thời. Sau khi đóng thông báo này,
                bạn sẽ không xem lại được mật khẩu.
              </p>
            </div>

            <button
              type="button"
              onClick={() => setCreatedAccount(null)}
              className="rounded-lg px-2 py-1 text-xs font-medium hover:bg-emerald-100 dark:hover:bg-emerald-500/20"
            >
              Đóng
            </button>
          </div>

          <div className="grid gap-2 rounded-lg bg-white/70 p-3 dark:bg-slate-900/40">
            <div>
              <span className="text-xs opacity-70">Tên đăng nhập:</span>{" "}
              <span className="font-mono font-semibold">
                {createdAccount.username}
              </span>
            </div>

            <div>
              <span className="text-xs opacity-70">Mật khẩu tạm thời:</span>{" "}
              <span className="font-mono font-semibold">
                {createdAccount.temporary_password}
              </span>
            </div>
          </div>
        </div>
      )}

      <div className="rounded-xl bg-white shadow-sm dark:bg-slate-800 dark:shadow-slate-900/50">
        {/* Filter */}
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 p-4 dark:border-slate-700">
          <div className="min-w-[220px] flex-1">
            <Input
              placeholder="Tìm theo tên, username, email..."
              value={filter.search ?? ""}
              onChange={(e) =>
                setFilter((p) => ({
                  ...p,
                  search: e.target.value,
                  page: 1,
                }))
              }
              leftIcon={
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
                    d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"
                  />
                </svg>
              }
            />
          </div>

          <select
            value={filter.status ?? ""}
            onChange={(e) =>
              setFilter((p) => ({
                ...p,
                status: e.target.value as UserFilterStatus,
                page: 1,
              }))
            }
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
          >
            <option value="">Tất cả trạng thái</option>
            <option value="active">Hoạt động</option>
            <option value="inactive">Ngừng HĐ</option>
          </select>
        </div>

        {/* Stats */}
        {result && (
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2 dark:border-slate-700">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Tổng{" "}
              <span className="font-semibold text-slate-700 dark:text-slate-300">
                {result.total}
              </span>{" "}
              người dùng
            </p>

            <p className="text-xs text-slate-400 dark:text-slate-500">
              Trang {page}/{totalPages}
            </p>
          </div>
        )}

        {/* Table */}
        <div className="p-4">
          {loading ? (
            <Loading text="Đang tải danh sách người dùng..." />
          ) : error ? (
            <div className="flex flex-col items-center gap-3 py-12 text-center">
              <p className="text-sm text-red-500">{error}</p>
              <Button variant="secondary" onClick={fetchData} size="sm">
                Thử lại
              </Button>
            </div>
          ) : (
            <UserTable
              users={result?.data ?? []}
              onEdit={setEditTarget}
              onDelete={setDeleteTarget}
            />
          )}
        </div>

        {/* Pagination */}
        {!loading && !error && totalPages > 1 && (
          <div className="flex items-center justify-center gap-1 border-t border-slate-100 px-4 py-3 dark:border-slate-700">
            <button
              onClick={() =>
                setFilter((p) => ({
                  ...p,
                  page: Math.max(1, (p.page ?? 1) - 1),
                }))
              }
              disabled={page <= 1}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-40 dark:border-slate-600 dark:text-slate-400 dark:hover:bg-slate-700"
            >
              ← Trước
            </button>

            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
              <button
                key={p}
                onClick={() =>
                  setFilter((prev) => ({
                    ...prev,
                    page: p,
                  }))
                }
                className={`min-w-[36px] rounded-lg border px-3 py-1.5 text-sm transition ${
                  page === p
                    ? "border-blue-600 bg-blue-600 font-semibold text-white"
                    : "border-slate-300 text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-400 dark:hover:bg-slate-700"
                }`}
              >
                {p}
              </button>
            ))}

            <button
              onClick={() =>
                setFilter((p) => ({
                  ...p,
                  page: Math.min(totalPages, (p.page ?? 1) + 1),
                }))
              }
              disabled={page >= totalPages}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-40 dark:border-slate-600 dark:text-slate-400 dark:hover:bg-slate-700"
            >
              Sau →
            </button>
          </div>
        )}
      </div>

      <UserAddModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onSubmit={handleCreate}
      />

      <UserEditModal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        user={editTarget}
        onSubmit={handleUpdate}
      />

      <UserDeleteModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        user={deleteTarget}
        onConfirm={handleDelete}
        loading={deleteLoading}
      />

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
