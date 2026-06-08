import DashboardLayout from "@/components/layout/DashboardLayout";

export default function DashboardPage() {
  return (
    <DashboardLayout>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Tổng quan</h1>
        <p className="mt-1 text-sm text-slate-500">
          Theo dõi tổng quan hệ thống khách hàng và lượt ghé cửa hàng.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded-xl bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Tổng khách hàng</p>
          <h2 className="mt-2 text-2xl font-bold text-slate-900">120</h2>
        </div>

        <div className="rounded-xl bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Khách mới</p>
          <h2 className="mt-2 text-2xl font-bold text-slate-900">35</h2>
        </div>

        <div className="rounded-xl bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Khách quay lại</p>
          <h2 className="mt-2 text-2xl font-bold text-slate-900">85</h2>
        </div>

        <div className="rounded-xl bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Tổng đơn hàng</p>
          <h2 className="mt-2 text-2xl font-bold text-slate-900">58</h2>
        </div>
      </div>
    </DashboardLayout>
  );
}
