"use client";

import { useTheme } from "@/components/layout/ThemeProvider";

/**
 * Trả về true nếu đang ở dark mode.
 * Đọc từ ThemeContext — đồng bộ, không có delay.
 */
export function useIsDark(): boolean {
  const { theme } = useTheme();
  return theme === "dark";
}
