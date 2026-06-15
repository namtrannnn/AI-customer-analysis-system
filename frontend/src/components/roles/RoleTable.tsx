"use client";

import { useRouter } from "next/navigation";
import type { Role } from "@/types/role.type";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { Eye, Pencil, ShieldCheck, Trash2, Users } from "lucide-react";

interface RoleTableProps {
  roles: Role[];
  canEdit?: boolean;
  canDelete?: boolean;
  onEdit: (role: Role) => void;
  onDelete: (role: Role) => void;
}

export default function RoleTable({
  roles,
  canEdit = false,
  canDelete = false,
  onEdit,
  onDelete,
}: RoleTableProps) {
  const router = useRouter();

  if (roles.length === 0) {
    return (
      <div className="py-12">
        <EmptyState
          title="Không tìm thấy nhóm quyền"
          description="Thử thay đổi từ khóa tìm kiếm hoặc thêm nhóm quyền mới."
        />
      </div>
    );
  }

  return (
    <div className="overflow-x-auto bg-white dark:bg-slate-900">
      <table className="w-full min-w-[920px] text-sm">
        <thead className="bg-slate-50 dark:bg-slate-950/50">
          <tr className="text-left text-[11px] font-black uppercase tracking-wide text-slate-500 dark:text-slate-400">
            <th className="px-4 py-3">Nhóm quyền</th>
            <th className="px-4 py-3">Mã vai trò</th>
            <th className="px-4 py-3">Mô tả</th>
            <th className="px-4 py-3 text-center">Quyền</th>
            <th className="px-4 py-3 text-center">Người dùng</th>
            <th className="px-4 py-3 text-right">Thao tác</th>
          </tr>
        </thead>

        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {roles.map((role) => {
            const permissionCount = role.permissions?.length ?? 0;
            const userCount = role.users?.length ?? 0;

            return (
              <tr
                key={role.id}
                onClick={() => router.push(`/roles/${role.id}`)}
                className="group cursor-pointer bg-white transition-colors hover:bg-blue-50/40 dark:bg-slate-900 dark:hover:bg-slate-800/60"
              >
                <td className="px-4 py-3.5">
                  <div className="min-w-0">
                    <p className="line-clamp-1 font-bold text-slate-900 transition group-hover:text-blue-600 dark:text-white dark:group-hover:text-blue-300">
                      {role.role_name}
                    </p>

                    {role.permissions && role.permissions.length > 0 ? (
                      <p className="mt-0.5 max-w-[300px] truncate text-xs font-medium text-slate-400 dark:text-slate-500">
                        {role.permissions
                          .slice(0, 3)
                          .map((permission) => permission.permission_name)
                          .join(", ")}
                        {role.permissions.length > 3
                          ? ` +${role.permissions.length - 3} quyền`
                          : ""}
                      </p>
                    ) : (
                      <p className="mt-0.5 text-xs font-medium text-slate-400 dark:text-slate-500">
                        Chưa gán quyền
                      </p>
                    )}
                  </div>
                </td>

                <td className="px-4 py-3.5">
                  <code className="rounded-lg bg-slate-100 px-2 py-1 text-xs font-bold text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                    {role.role_code}
                  </code>
                </td>

                <td className="max-w-[260px] truncate px-4 py-3.5 text-slate-500 dark:text-slate-400">
                  {role.description || "—"}
                </td>

                <td className="px-4 py-3.5 text-center">
                  <span className="inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-full bg-violet-50 px-2.5 py-1 text-xs font-bold text-violet-700 ring-1 ring-violet-100 dark:bg-violet-500/10 dark:text-violet-300 dark:ring-violet-500/20">
                    <ShieldCheck className="h-3.5 w-3.5" />
                    {permissionCount}
                  </span>
                </td>

                <td className="px-4 py-3.5 text-center">
                  <span className="inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-full bg-blue-50 px-2.5 py-1 text-xs font-bold text-blue-700 ring-1 ring-blue-100 dark:bg-blue-500/10 dark:text-blue-300 dark:ring-blue-500/20">
                    <Users className="h-3.5 w-3.5" />
                    {userCount}
                  </span>
                </td>

                <td
                  className="px-4 py-3.5 text-right"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="invisible flex items-center justify-end gap-1 opacity-0 pointer-events-none transition-all duration-150 group-hover:visible group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:visible group-focus-within:pointer-events-auto group-focus-within:opacity-100">
                    <Button
                      variant="ghost"
                      size="sm"
                      title="Xem chi tiết"
                      onClick={() => router.push(`/roles/${role.id}`)}
                    >
                      <Eye className="h-4 w-4" />
                    </Button>

                    {canEdit && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onEdit(role)}
                        title="Chỉnh sửa"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                    )}

                    {canDelete && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10 dark:hover:text-red-300"
                        onClick={() => onDelete(role)}
                        title={
                          userCount > 0
                            ? "Nhóm quyền đang có người dùng, BE có thể không cho xóa"
                            : "Xóa"
                        }
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
