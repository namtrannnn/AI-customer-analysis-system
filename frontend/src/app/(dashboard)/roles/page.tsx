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
} from "@/services/role.service";
import type {
  Role,
  RoleCreatePayload,
  RoleUpdatePayload,
  RoleFilterParams,
} from "@/types/role.type";
import type { PaginatedResponse } from "@/types/customer.type";
import { useDebounce } from "@/hooks/useDebounce";
import { usePermission } from "@/hooks/usePermission";
import ForbiddenPage from "@/components/ui/ForbiddenPage";
import Pagination from "@/components/ui/Pagination";
import { AlertTriangle, Plus, Search, X } from "lucide-react";
import { useToast } from "@/components/ui/ToastProvider";

const DEFAULT_FILTER: RoleFilterParams = {
  search: "",
  page: 1,
  limit: 10,
};

export default function RolesPage() {
  const { hasPermission } = usePermission();
  const toast = useToast();
  const canViewRole = hasPermission("role.view");
  const canCreateRole = hasPermission("role.create");
  const canUpdateRole = hasPermission("role.update");
  const canDeleteRole = hasPermission("role.delete");

  const [result, setResult] = useState<PaginatedResponse<Role> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filter, setFilter] = useState<RoleFilterParams>(DEFAULT_FILTER);

  const [addOpen, setAddOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Role | null>(null);
  const [editPermIds, setEditPermIds] = useState<number[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<Role | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const debouncedSearch = useDebounce(filter.search ?? "", 400);

  const page = filter.page ?? 1;
  const limit = filter.limit ?? 10;
  const totalPages = result?.total_pages ?? 1;
  const hasFilter = Boolean(filter.search);

  const fetchData = useCallback(async () => {
    if (!canViewRole) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await getRoles({
        page: filter.page,
        limit: filter.limit,
        search: debouncedSearch,
      });

      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Có lỗi xảy ra");
    } finally {
      setLoading(false);
    }
  }, [canViewRole, filter.page, filter.limit, debouncedSearch]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  function updateFilter(partial: Partial<RoleFilterParams>) {
    setFilter((prev) => ({
      ...prev,
      ...partial,
    }));
  }

  function resetFilter() {
    setFilter(DEFAULT_FILTER);
  }

  function normalizeCreatePayload(
    payload: RoleCreatePayload,
  ): RoleCreatePayload {
    return {
      role_code: payload.role_code.trim().toLowerCase(),
      role_name: payload.role_name.trim(),
      description: payload.description?.trim() || null,
      permission_ids: payload.permission_ids ?? [],
    };
  }

  function normalizeUpdatePayload(
    payload: RoleUpdatePayload,
  ): RoleUpdatePayload {
    return {
      ...payload,
      role_code: payload.role_code?.trim().toLowerCase(),
      role_name: payload.role_name?.trim(),
      description: payload.description?.trim() || null,
      permission_ids: payload.permission_ids ?? [],
    };
  }

  async function handleCreate(payload: RoleCreatePayload) {
    if (!canCreateRole) {
      toast.error("Bạn không có quyền thêm nhóm quyền.");
      return;
    }

    try {
      await createRole(normalizeCreatePayload(payload));
      toast.success("Thêm nhóm quyền thành công");
      setAddOpen(false);

      if ((filter.page ?? 1) !== 1) {
        updateFilter({ page: 1 });
      } else {
        await fetchData();
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Thêm nhóm quyền thất bại");
      throw e;
    }
  }

  async function handleUpdate(payload: RoleUpdatePayload) {
    if (!editTarget) return;

    if (!canUpdateRole) {
      toast.error("Bạn không có quyền cập nhật nhóm quyền.");
      return;
    }

    try {
      await updateRole(editTarget.id, normalizeUpdatePayload(payload));
      toast.success("Cập nhật nhóm quyền thành công");
      setEditTarget(null);
      setEditPermIds([]);
      await fetchData();
    } catch (e: unknown) {
      toast.error(
        e instanceof Error ? e.message : "Cập nhật nhóm quyền thất bại",
      );
      throw e;
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;

    if (!canDeleteRole) {
      toast.error("Bạn không có quyền xóa nhóm quyền.");
      return;
    }

    setDeleteLoading(true);

    try {
      await deleteRole(deleteTarget.id);
      toast.success(`Đã xóa "${deleteTarget.role_name}"`);
      setDeleteTarget(null);
      await fetchData();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Xóa thất bại");
    } finally {
      setDeleteLoading(false);
    }
  }

  function openEdit(role: Role) {
    if (!canUpdateRole) {
      toast.error("Bạn không có quyền cập nhật nhóm quyền.");
      return;
    }

    const permIds =
      role.permission_ids ??
      role.permissions?.map((permission) => permission.id) ??
      [];

    setEditPermIds(permIds);
    setEditTarget(role);
  }

  if (!canViewRole) {
    return (
      <ForbiddenPage
        description="Bạn không có quyền xem danh sách nhóm quyền. Vui lòng liên hệ quản trị viên nếu cần được cấp quyền."
        backHref="/dashboard"
        backLabel="Về Dashboard"
        showHomeButton={false}
      />
    );
  }

  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="border-b border-slate-200 bg-slate-50 px-4 py-4 dark:border-slate-800 dark:bg-slate-950/40 sm:px-5">
          <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                  Nhóm quyền
                </h2>

                <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-bold text-blue-700 dark:bg-blue-500/10 dark:text-blue-300">
                  {result?.total ?? 0} nhóm quyền
                </span>

                {hasFilter && (
                  <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-bold text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
                    Đang lọc
                  </span>
                )}
              </div>

              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                Quản lý các nhóm quyền và phân công quyền hạn cho từng nhóm.
              </p>
            </div>

            {canCreateRole && (
              <div className="flex shrink-0 gap-2">
                <Button
                  size="base"
                  icon={<Plus className="h-4 w-4" />}
                  onClick={() => setAddOpen(true)}
                >
                  Thêm nhóm quyền
                </Button>
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[240px] flex-1">
              <Input
                placeholder="Tìm theo tên, mã nhóm quyền..."
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

            {hasFilter && (
              <Button
                type="button"
                variant="secondary"
                size="base"
                icon={<X className="h-4 w-4" />}
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
              nhóm quyền
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
            <Loading text="Đang tải danh sách nhóm quyền..." />
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
              <RoleTable
                roles={result?.data ?? []}
                canEdit={canUpdateRole}
                canDelete={canDeleteRole}
                onEdit={openEdit}
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
            label="nhóm quyền"
            onPageChange={(nextPage) =>
              updateFilter({
                page: nextPage,
              })
            }
          />
        )}
      </section>

      {canCreateRole && (
        <RoleAddModal
          open={addOpen}
          onClose={() => setAddOpen(false)}
          onSubmit={handleCreate}
        />
      )}

      {canUpdateRole && (
        <RoleEditModal
          open={!!editTarget}
          onClose={() => {
            setEditTarget(null);
            setEditPermIds([]);
          }}
          role={editTarget}
          currentPermissionIds={editPermIds}
          onSubmit={handleUpdate}
        />
      )}

      {canDeleteRole && (
        <RoleDeleteModal
          open={!!deleteTarget}
          onClose={() => setDeleteTarget(null)}
          role={deleteTarget}
          onConfirm={handleDelete}
          loading={deleteLoading}
        />
      )}
    </div>
  );
}
