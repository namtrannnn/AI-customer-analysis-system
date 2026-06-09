"use client";

import { useState, useEffect, useCallback } from "react";
import RoleTable from "@/components/roles/RoleTable";
import {
  RoleAddModal,
  RoleEditModal,
  RoleDeleteModal,
} from "@/components/roles/RoleModal";
import Loading from "@/components/ui/Loading";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import {
  getRoles,
  createRole,
  updateRole,
  deleteRole,
  getRolePermissions,
} from "@/services/role.service";
import type {
  Role,
  RoleCreatePayload,
  RoleFilterParams,
} from "@/types/role.type";
import type { PaginatedResponse } from "@/types/customer.type";
import { useDebounce } from "@/hooks/useDebounce";

export default function RolesPage() {
  const [result, setResult] = useState<PaginatedResponse<Role> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<RoleFilterParams>({
    search: "",
    page: 1,
    limit: 10,
  });

  const [addOpen, setAddOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Role | null>(null);
  const [editPermIds, setEditPermIds] = useState<number[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<Role | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [toast, setToast] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);

  const debouncedSearch = useDebounce(filter.search, 400);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getRoles({ ...filter, search: debouncedSearch });
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

  async function handleCreate(payload: RoleCreatePayload) {
    await createRole(payload);
    showToast("success", "Thêm nhóm quyền thành công");
    fetchData();
  }

  async function handleUpdate(payload: RoleCreatePayload) {
    if (!editTarget) return;
    await updateRole(editTarget.id, payload);
    showToast("success", "Cập nhật nhóm quyền thành công");
    fetchData();
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleteLoading(true);
    try {
      await deleteRole(deleteTarget.id);
      showToast("success", `Đã xóa "${deleteTarget.role_name}"`);
      setDeleteTarget(null);
      fetchData();
    } catch (e: unknown) {
      showToast("error", e instanceof Error ? e.message : "Xóa thất bại");
    } finally {
      setDeleteLoading(false);
    }
  }

  async function openEdit(role: Role) {
    const permIds = await getRolePermissions(role.id);
    setEditPermIds(permIds);
    setEditTarget(role);
  }

  const page = filter.page ?? 1;
  const totalPages = result?.total_pages ?? 1;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
            Nhóm quyền
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Quản lý các nhóm quyền và phân công quyền hạn cho từng nhóm.
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
          Thêm nhóm quyền
        </Button>
      </div>

      <div className="rounded-xl bg-white dark:bg-slate-800 shadow-sm dark:shadow-slate-900/50">
        <div className="border-b border-slate-100 dark:border-slate-700 p-4">
          <Input
            placeholder="Tìm theo tên, mã nhóm quyền..."
            value={filter.search ?? ""}
            onChange={(e) =>
              setFilter((p) => ({ ...p, search: e.target.value, page: 1 }))
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

        {result && (
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-700 px-4 py-2">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Tổng{" "}
              <span className="font-semibold text-slate-700 dark:text-slate-300">
                {result.total}
              </span>{" "}
              nhóm quyền
            </p>
          </div>
        )}

        <div className="p-4">
          {loading ? (
            <Loading text="Đang tải danh sách nhóm quyền..." />
          ) : error ? (
            <div className="flex flex-col items-center gap-3 py-12 text-center">
              <p className="text-sm text-red-500">{error}</p>
              <Button variant="secondary" onClick={fetchData} size="sm">
                Thử lại
              </Button>
            </div>
          ) : (
            <RoleTable
              roles={result?.data ?? []}
              onEdit={openEdit}
              onDelete={setDeleteTarget}
            />
          )}
        </div>
      </div>

      <RoleAddModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onSubmit={handleCreate}
      />
      <RoleEditModal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        role={editTarget}
        currentPermissionIds={editPermIds}
        onSubmit={handleUpdate}
      />
      <RoleDeleteModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        role={deleteTarget}
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
