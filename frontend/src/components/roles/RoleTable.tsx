"use client";

import Link from "next/link";
import type { Role } from "@/types/role.type";
import { formatDate } from "@/utils/formatDate";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";

interface RoleTableProps {
  roles: Role[];
  onEdit: (role: Role) => void;
  onDelete: (role: Role) => void;
}

export default function RoleTable({ roles, onEdit, onDelete }: RoleTableProps) {
  if (roles.length === 0) {
    return (
      <EmptyState
        title="Không tìm thấy nhóm quyền"
        description="Thử thay đổi từ khóa tìm kiếm hoặc thêm nhóm quyền mới."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <th className="pb-3 pr-4">Nhóm quyền</th>
            <th className="pb-3 pr-4">Mã</th>
            <th className="pb-3 pr-4">Mô tả</th>
            <th className="pb-3 pr-4 text-center">Quyền</th>
            <th className="pb-3 pr-4 text-center">Người dùng</th>
            <th className="pb-3 pr-4">Ngày tạo</th>
            <th className="pb-3 text-right">Thao tác</th>
          </tr>
        </thead>

        <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
          {roles.map((role) => {
            const permissionCount = role.permissions?.length ?? 0;
            const userCount = role.users?.length ?? 0;

            return (
              <tr
                key={role.id}
                className="group transition-colors hover:bg-slate-50 dark:hover:bg-slate-700/40"
              >
                <td className="py-3 pr-4">
                  <div>
                    <Link
                      href={`/roles/${role.id}`}
                      className="font-medium text-slate-900 hover:text-blue-600 hover:underline dark:text-slate-100 dark:hover:text-blue-400"
                      title="Xem chi tiết nhóm quyền"
                    >
                      {role.role_name}
                    </Link>

                    {role.permissions && role.permissions.length > 0 && (
                      <p className="mt-0.5 max-w-[260px] truncate text-xs text-slate-400 dark:text-slate-500">
                        {role.permissions
                          .slice(0, 3)
                          .map((permission) => permission.permission_name)
                          .join(", ")}
                        {role.permissions.length > 3
                          ? ` +${role.permissions.length - 3} quyền`
                          : ""}
                      </p>
                    )}
                  </div>
                </td>

                <td className="py-3 pr-4">
                  <code className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700 dark:bg-slate-700 dark:text-slate-300">
                    {role.role_code}
                  </code>
                </td>

                <td className="max-w-[220px] truncate py-3 pr-4 text-slate-500 dark:text-slate-400">
                  {role.description || "—"}
                </td>

                <td className="py-3 pr-4 text-center">
                  <span className="inline-flex items-center justify-center rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                    {permissionCount}
                  </span>
                </td>

                <td className="py-3 pr-4 text-center">
                  <span className="inline-flex items-center justify-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                    {userCount}
                  </span>
                </td>

                <td className="py-3 pr-4 text-slate-500 dark:text-slate-400">
                  {formatDate(role.created_at)}
                </td>

                <td className="py-3 text-right">
                  <div className="flex items-center justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <Link href={`/roles/${role.id}`}>
                      <Button variant="ghost" size="sm" title="Xem chi tiết">
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
                            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                          />
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                          />
                        </svg>
                      </Button>
                    </Link>

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEdit(role)}
                      title="Chỉnh sửa"
                    >
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
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20"
                      onClick={() => onDelete(role)}
                      title={
                        userCount > 0
                          ? "Nhóm quyền đang có người dùng, BE có thể không cho xóa"
                          : "Xóa"
                      }
                    >
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
                    </Button>
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
