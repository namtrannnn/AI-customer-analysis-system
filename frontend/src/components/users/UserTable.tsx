"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import type { User, UserStatus } from "@/types/user.type";
import { timeAgo } from "@/utils/formatDate";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import {
  Eye,
  Edit3,
  Trash2,
  ShieldCheck,
  CheckCircle2,
  CircleOff,
} from "lucide-react";

interface UserTableProps {
  users: User[];
  canEdit?: boolean;
  canDelete?: boolean;
  onEdit: (user: User) => void;
  onDelete: (user: User) => void;
}

const ROLE_LABEL_MAP: Record<number, string> = {
  1: "Quản trị viên",
  2: "Quản lý",
  3: "Nhân viên",
};

const statusConfig: Record<
  UserStatus,
  {
    label: string;
    className: string;
    icon: React.ElementType;
  }
> = {
  active: {
    label: "Hoạt động",
    icon: CheckCircle2,
    className:
      "bg-emerald-50 text-emerald-700 ring-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/20",
  },
  inactive: {
    label: "Ngừng HĐ",
    icon: CircleOff,
    className:
      "bg-red-50 text-red-600 ring-red-100 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/20",
  },
  deleted: {
    label: "Đã xóa",
    icon: CircleOff,
    className:
      "bg-slate-100 text-slate-600 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700",
  },
};

function getUserName(user: User) {
  return user.full_name?.trim() || "Người dùng";
}

function getUserInitial(user: User) {
  const name = getUserName(user);
  return name.charAt(0).toUpperCase() || "U";
}

export default function UserTable({
  users,
  canEdit = false,
  canDelete = false,
  onEdit,
  onDelete,
}: UserTableProps) {
  const router = useRouter();

  if (users.length === 0) {
    return (
      <div className="py-12">
        <EmptyState
          title="Không tìm thấy người dùng"
          description="Thử thay đổi bộ lọc hoặc thêm người dùng mới."
        />
      </div>
    );
  }

  return (
    <div className="overflow-x-auto bg-white dark:bg-slate-900">
      <table className="w-full min-w-[980px] text-sm">
        <thead className="bg-slate-50 dark:bg-slate-950/50">
          <tr className="text-left text-[11px] font-black uppercase tracking-wide text-slate-500 dark:text-slate-400">
            <th className="px-4 py-3">Người dùng</th>
            <th className="px-4 py-3">Liên hệ</th>
            <th className="px-4 py-3">Nhóm quyền</th>
            <th className="px-4 py-3">Đăng nhập gần nhất</th>
            <th className="px-4 py-3">Trạng thái</th>
            <th className="px-4 py-3 text-right">Thao tác</th>
          </tr>
        </thead>

        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {users.map((user) => {
            const status = statusConfig[user.status] ?? statusConfig.inactive;
            const StatusIcon = status.icon;
            const roleId = user.role_id;
            const userName = getUserName(user);

            return (
              <tr
                key={user.id}
                onClick={() => router.push(`/users/${user.id}`)}
                className="group cursor-pointer bg-white transition-colors hover:bg-blue-50/40 dark:bg-slate-900 dark:hover:bg-slate-800/60"
              >
                <td className="px-4 py-3.5">
                  <div className="flex items-center gap-3">
                    <div className="relative h-10 w-10 shrink-0 overflow-hidden rounded-2xl bg-gradient-to-br from-slate-100 to-slate-200 ring-1 ring-slate-200 dark:from-slate-800 dark:to-slate-700 dark:ring-slate-700">
                      {user.avatar_url ? (
                        <Image
                          src={user.avatar_url}
                          alt={userName}
                          fill
                          className="object-cover"
                          sizes="40px"
                        />
                      ) : (
                        <span className="flex h-full w-full items-center justify-center text-sm font-black text-slate-500 dark:text-slate-300">
                          {getUserInitial(user)}
                        </span>
                      )}
                    </div>

                    <div className="min-w-0">
                      <p className="line-clamp-1 font-bold text-slate-900 transition group-hover:text-blue-600 dark:text-white dark:group-hover:text-blue-300">
                        {userName}
                      </p>

                      <p className="mt-0.5 line-clamp-1 text-xs font-medium text-slate-400 dark:text-slate-500">
                        @{user.username}
                      </p>
                    </div>
                  </div>
                </td>

                <td className="px-4 py-3.5">
                  <p className="font-medium text-slate-700 dark:text-slate-300">
                    {user.phone || "Chưa có SĐT"}
                  </p>

                  <p className="mt-0.5 line-clamp-1 text-xs text-slate-400 dark:text-slate-500">
                    {user.email || "Chưa có email"}
                  </p>
                </td>

                <td className="px-4 py-3.5">
                  {!roleId ? (
                    <span className="text-xs text-slate-400 dark:text-slate-500">
                      Chưa gán
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full bg-blue-50 px-2.5 py-1 text-xs font-bold text-blue-700 ring-1 ring-blue-100 dark:bg-blue-500/10 dark:text-blue-300 dark:ring-blue-500/20">
                      <ShieldCheck className="h-3.5 w-3.5" />
                      {ROLE_LABEL_MAP[roleId] ?? `Role #${roleId}`}
                    </span>
                  )}
                </td>

                <td className="px-4 py-3.5 text-slate-500 dark:text-slate-400">
                  {user.last_login_at
                    ? timeAgo(user.last_login_at)
                    : "Chưa đăng nhập"}
                </td>

                <td className="px-4 py-3.5">
                  <span
                    className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-bold ring-1 ${status.className}`}
                  >
                    <StatusIcon className="h-3.5 w-3.5" />
                    {status.label}
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
                      onClick={() => router.push(`/users/${user.id}`)}
                    >
                      <Eye className="h-4 w-4" />
                    </Button>

                    {canEdit && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onEdit(user)}
                        title="Chỉnh sửa"
                      >
                        <Edit3 className="h-4 w-4" />
                      </Button>
                    )}

                    {canDelete && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10 dark:hover:text-red-300"
                        onClick={() => onDelete(user)}
                        title="Xóa"
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
