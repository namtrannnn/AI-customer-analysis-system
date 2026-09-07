import { http } from "@/lib/http";
import axios from "axios";

export type ReportType = "summary" | "activity" | "customer" | "revenue";

async function _downloadBlob(url: string, filename: string): Promise<void> {
  try {
    const res = await http.raw.get(url, { responseType: "blob" });

    // Kiểm tra nếu BE trả về JSON lỗi thay vì binary blob
    const contentType = String(res.headers["content-type"] ?? "");
    if (contentType.includes("application/json")) {
      // BE trả JSON error — đọc nội dung blob và throw
      const text = await (res.data as Blob).text();
      const json = JSON.parse(text);
      throw new Error(json?.detail || json?.message || "Không thể xuất báo cáo");
    }

    const blobUrl = URL.createObjectURL(new Blob([res.data]));
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(blobUrl);
  } catch (e) {
    if (axios.isAxiosError(e)) {
      // Đọc error response dạng blob
      if (e.response?.data instanceof Blob) {
        try {
          const text = await (e.response.data as Blob).text();
          const json = JSON.parse(text);
          const detail = json?.detail || json?.message;
          if (detail) throw new Error(detail);
        } catch (parseErr) {
          if (parseErr instanceof Error && parseErr.message !== "JSON parse error") {
            throw parseErr;
          }
        }
      }
      const status = e.response?.status;
      if (status === 404) throw new Error("Không có dữ liệu trong khoảng thời gian đã chọn.");
      if (status === 403) throw new Error("Bạn không có quyền xuất báo cáo.");
      if (status === 401) throw new Error("Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.");
    }
    throw e;
  }
}

export async function exportReportExcel(
  startDate: string,
  endDate: string,
  reportType: ReportType = "summary",
): Promise<void> {
  await _downloadBlob(
    `/reports/export/excel?start_date=${startDate}&end_date=${endDate}&report_type=${reportType}`,
    `store_report_${reportType}_${startDate}_${endDate}.xlsx`,
  );
}

export async function exportReportPdf(
  startDate: string,
  endDate: string,
  reportType: ReportType = "summary",
): Promise<void> {
  await _downloadBlob(
    `/reports/export/pdf?start_date=${startDate}&end_date=${endDate}&report_type=${reportType}`,
    `store_report_${reportType}_${startDate}_${endDate}.pdf`,
  );
}
