import type { LucideIcon } from "lucide-react";
import { LogOut, UserRound } from "lucide-react";

export type UserMenuItemType = "link" | "logout";

export interface UserMenuItem {
  label: string;
  href?: string;
  type: UserMenuItemType;
  icon: LucideIcon;
}

export const userMenuItems: UserMenuItem[] = [
  {
    label: "Tài khoản của tôi",
    href: "/profile",
    type: "link",
    icon: UserRound,
  },
  {
    label: "Đăng xuất",
    type: "logout",
    icon: LogOut,
  },
];
