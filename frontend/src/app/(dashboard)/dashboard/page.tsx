// ─── Stat card ────────────────────────────────────────────────────────────────
function StatCard({
  label,
  value,
  sub,
  trend,
  icon,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  trend?: { value: string; up: boolean };
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div
      className="group relative overflow-hidden rounded-2xl p-5 transition-all hover:shadow-md"
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {/* Background decoration */}
      <div
        className={`absolute -right-4 -top-4 h-20 w-20 rounded-full opacity-10 ${color}`}
      />

      <div className="relative flex items-start justify-between">
        <div>
          <p
            className="text-xs font-medium"
            style={{ color: "var(--text-muted)" }}
          >
            {label}
          </p>
          <p
            className="mt-2 text-2xl font-bold tracking-tight"
            style={{ color: "var(--text-primary)" }}
          >
            {value}
          </p>
          {sub && (
            <p
              className="mt-0.5 text-xs"
              style={{ color: "var(--text-muted)" }}
            >
              {sub}
            </p>
          )}
          {trend && (
            <div
              className={`mt-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${trend.up ? "bg-green-50 text-green-600 dark:bg-green-900/30 dark:text-green-400" : "bg-red-50 text-red-500 dark:bg-red-900/20 dark:text-red-400"}`}
            >
              <svg
                className={`h-3 w-3 ${trend.up ? "" : "rotate-180"}`}
                viewBox="0 0 12 12"
                fill="currentColor"
              >
                <path d="M6 2l4 6H2l4-6z" />
              </svg>
              {trend.value}
            </div>
          )}
        </div>
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-xl ${color} shadow-sm`}
        >
          {icon}
        </div>
      </div>
    </div>
  );
}

// ─── Recent activity item ─────────────────────────────────────────────────────
function ActivityItem({
  color,
  title,
  sub,
  time,
}: {
  color: string;
  title: string;
  sub: string;
  time: string;
}) {
  return (
    <div className="flex items-start gap-3 py-3">
      <div className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${color}`} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">
          {title}
        </p>
        <p className="text-xs text-slate-400 dark:text-slate-500">{sub}</p>
      </div>
      <span className="shrink-0 text-xs text-slate-400 dark:text-slate-500">
        {time}
      </span>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <div>
      {/* ── Page title ── */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
          Tổng quan
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Theo dõi hoạt động hệ thống và chỉ số khách hàng hôm nay.
        </p>
      </div>

      {/* ── Stat cards ── */}
      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Tổng khách hàng"
          value="120"
          sub="Đã định danh"
          trend={{ value: "+8% tháng này", up: true }}
          color="bg-blue-500"
          icon={
            <svg
              className="h-5 w-5 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          }
        />
        <StatCard
          label="Khách mới hôm nay"
          value="35"
          sub="Lượt ghé đầu tiên"
          trend={{ value: "+12% vs hôm qua", up: true }}
          color="bg-emerald-500"
          icon={
            <svg
              className="h-5 w-5 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"
              />
            </svg>
          }
        />
        <StatCard
          label="Khách quay lại"
          value="85"
          sub="Tỷ lệ giữ chân 70.8%"
          trend={{ value: "+3% tuần này", up: true }}
          color="bg-violet-500"
          icon={
            <svg
              className="h-5 w-5 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          }
        />
        <StatCard
          label="Tổng doanh thu"
          value="58.2M"
          sub="Tháng 6/2024"
          trend={{ value: "-2% vs tháng trước", up: false }}
          color="bg-amber-500"
          icon={
            <svg
              className="h-5 w-5 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          }
        />
      </div>

      {/* ── Content grid ── */}
      <div className="grid gap-5 lg:grid-cols-3">
        {/* ─ Recent visits (2/3) ─ */}
        <div
          className="rounded-2xl p-6 lg:col-span-2"
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <div className="mb-4 flex items-center justify-between">
            <h2
              className="text-sm font-semibold"
              style={{ color: "var(--text-primary)" }}
            >
              Lượt ghé gần đây
            </h2>
            <a
              href="/customers"
              className="text-xs font-medium text-blue-600 hover:underline"
            >
              Xem tất cả →
            </a>
          </div>

          <div className="divide-y divide-slate-100 dark:divide-slate-700">
            {[
              {
                name: "Nguyễn Văn An",
                code: "KH-000001",
                time: "14:20",
                duration: "45 phút",
                status: "VIP",
              },
              {
                name: "Võ Minh Đức",
                code: "KH-000005",
                time: "09:30",
                duration: "90 phút",
                status: "VIP",
              },
              {
                name: "Lý Thị Ích",
                code: "KH-000010",
                time: "15:00",
                duration: "60 phút",
                status: "VIP",
              },
              {
                name: "Bùi Văn Hùng",
                code: "KH-000009",
                time: "09:00",
                duration: "35 phút",
                status: "active",
              },
              {
                name: "Trần Thị Bình",
                code: "KH-000002",
                time: "11:00",
                duration: "40 phút",
                status: "active",
              },
            ].map((item) => (
              <div
                key={item.code}
                className="flex items-center justify-between py-3"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-700 dark:to-slate-600 text-xs font-bold text-slate-600 dark:text-slate-300">
                    {item.name.charAt(0)}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                      {item.name}
                    </p>
                    <p className="text-xs text-slate-400 dark:text-slate-500">
                      {item.code}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${
                      item.status === "VIP"
                        ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                        : "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                    }`}
                  >
                    {item.status === "VIP" ? "VIP" : "Hoạt động"}
                  </span>
                  <div className="text-right">
                    <p className="text-xs font-medium text-slate-700 dark:text-slate-300">
                      {item.time}
                    </p>
                    <p className="text-[11px] text-slate-400 dark:text-slate-500">
                      {item.duration}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ─ Activity feed (1/3) ─ */}
        <div
          className="rounded-2xl p-6"
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <div className="mb-4 flex items-center justify-between">
            <h2
              className="text-sm font-semibold"
              style={{ color: "var(--text-primary)" }}
            >
              Hoạt động
            </h2>
            <span className="rounded-full bg-blue-50 dark:bg-blue-900/30 px-2 py-0.5 text-[11px] font-medium text-blue-600 dark:text-blue-400">
              Hôm nay
            </span>
          </div>

          <div className="divide-y divide-slate-100 dark:divide-slate-700">
            <ActivityItem
              color="bg-green-500"
              title="Thêm khách hàng mới"
              sub="KH-000012 · Lê Văn C"
              time="14:32"
            />
            <ActivityItem
              color="bg-blue-500"
              title="Cập nhật thông tin"
              sub="KH-000005 · Võ Minh Đức"
              time="12:15"
            />
            <ActivityItem
              color="bg-amber-500"
              title="Khách VIP ghé cửa hàng"
              sub="KH-000010 · Lý Thị Ích"
              time="11:40"
            />
            <ActivityItem
              color="bg-violet-500"
              title="Thêm người dùng mới"
              sub="staff02 · Nhân viên"
              time="09:18"
            />
            <ActivityItem
              color="bg-red-500"
              title="Xóa khách hàng"
              sub="KH-000008 · Đỗ Thị Giang"
              time="08:55"
            />
          </div>
        </div>
      </div>

      {/* ── Bottom cards ── */}
      <div className="mt-5 grid gap-5 sm:grid-cols-3">
        <div className="rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-700 p-5 text-white shadow-lg shadow-blue-500/20">
          <p className="text-xs font-medium text-blue-200">
            Camera đang hoạt động
          </p>
          <p className="mt-2 text-3xl font-bold">4</p>
          <p className="mt-1 text-xs text-blue-300">/ 6 camera tổng</p>
          <div className="mt-4 flex gap-1">
            {[1, 1, 1, 1, 0, 0].map((on, i) => (
              <div
                key={i}
                className={`h-1.5 w-1.5 rounded-full ${on ? "bg-white" : "bg-blue-400/40"}`}
              />
            ))}
          </div>
        </div>

        <div
          className="rounded-2xl p-5"
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <p
            className="text-xs font-medium"
            style={{ color: "var(--text-muted)" }}
          >
            Thời gian ở lại TB
          </p>
          <p
            className="mt-2 text-3xl font-bold"
            style={{ color: "var(--text-primary)" }}
          >
            42 phút
          </p>
          <div className="mt-1 inline-flex items-center gap-1 rounded-full bg-green-50 dark:bg-green-900/30 px-2 py-0.5 text-xs font-medium text-green-600 dark:text-green-400">
            <svg className="h-3 w-3" viewBox="0 0 12 12" fill="currentColor">
              <path d="M6 2l4 6H2l4-6z" />
            </svg>
            +5 phút vs tuần trước
          </div>
        </div>

        <div
          className="rounded-2xl p-5"
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <p
            className="text-xs font-medium"
            style={{ color: "var(--text-muted)" }}
          >
            Tỷ lệ chuyển đổi
          </p>
          <p
            className="mt-2 text-3xl font-bold"
            style={{ color: "var(--text-primary)" }}
          >
            48.3%
          </p>
          <div
            className="mt-2 h-2 w-full overflow-hidden rounded-full"
            style={{ background: "var(--bg-surface-3)" }}
          >
            <div
              className="h-2 rounded-full bg-gradient-to-r from-blue-500 to-indigo-500"
              style={{ width: "48.3%" }}
            />
          </div>
          <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
            58 / 120 khách mua hàng
          </p>
        </div>
      </div>
    </div>
  );
}
