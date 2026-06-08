import DashboardLayout from "@/components/layout/DashboardLayout";

export default function CustomersPage() {
  return (
    <DashboardLayout>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Quản lý khách hàng
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Danh sách khách hàng, khách ẩn danh và lịch sử xuất hiện.
          </p>
        </div>

        <button className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700">
          Thêm khách hàng
        </button>
      </div>

      <div className="rounded-xl bg-white p-6 shadow-sm">
        <p className="text-slate-500">
          Bảng khách hàng sẽ làm ở bước tiếp theo.
        </p>
      </div>
    </DashboardLayout>
  );
}
