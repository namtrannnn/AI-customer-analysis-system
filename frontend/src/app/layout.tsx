import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/layout/ThemeProvider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AI Customer Analysis",
  description: "Hệ thống phân tích khách hàng bằng AI",
};

// Inline script — chạy trước khi React hydrate để tránh flash
// Default: light. User phải chủ động bấm toggle để đổi sang dark.
const themeScript = `
(function(){
  try {
    var k = 'ai-customer-theme';
    var stored = localStorage.getItem(k);
    var html = document.documentElement;
    // Chỉ dark nếu user đã chủ động chọn dark trước đó
    // Không tự động follow OS — default là light
    if (stored === 'dark') {
      html.classList.add('dark');
      html.style.colorScheme = 'dark';
    } else {
      html.classList.remove('dark');
      html.style.colorScheme = 'light';
      // Normalize: lưu lại "light" cho các giá trị cũ (null, "system", v.v.)
      if (stored !== 'light') localStorage.setItem(k, 'light');
    }
  } catch(e) {}
})();
`.trim();

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="vi"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        {/* Prevent FOUC — must run before page renders */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full theme-transition">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
