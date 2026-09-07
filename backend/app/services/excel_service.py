import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
from app.schemas.report_schema import ReportDataDTO

def generate_excel_report(data: ReportDataDTO) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "Báo Cáo Tổng Hợp"

    title_font = Font(size=16, bold=True)
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")

    # 1. Header
    ws.merge_cells('A1:G1')
    ws['A1'] = "BÁO CÁO HOẠT ĐỘNG TỔNG HỢP"
    ws['A1'].font = title_font
    ws['A1'].alignment = center_align

    ws.merge_cells('A2:G2')
    ws['A2'] = f"Từ ngày: {data.start_date.strftime('%d/%m/%Y')} - Đến ngày: {data.end_date.strftime('%d/%m/%Y')}"
    ws['A2'].alignment = center_align

    # 2. Summary
    ws['A4'] = "Tổng lượt khách"
    ws['B4'] = data.summary.total_visitors
    ws['A5'] = "Khách mới"
    ws['B5'] = data.summary.new_visitors
    ws['A6'] = "Khách quay lại"
    ws['B6'] = data.summary.returning_visitors
    
    ws['D4'] = "Tổng đơn hàng"
    ws['E4'] = data.summary.total_orders
    ws['D5'] = "Tổng doanh thu"
    ws['E5'] = float(data.summary.total_revenue) # Đảm bảo là float
    ws['E5'].number_format = '#,##0 "VND"'
    ws['D6'] = "TG lưu trú TB (phút)"
    ws['E6'] = round(data.summary.avg_duration_seconds / 60, 2)

    # 3. Table Header
    headers = ["Ngày", "Tổng lượt khách", "Khách mới", "Khách quay lại", "TG lưu trú (phút)", "Số đơn", "Doanh thu"]
    start_row = 8
    
    for col, h in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # 4. Table Data
    for i, row_data in enumerate(data.daily_stats, start=start_row + 1):
        ws.cell(row=i, column=1, value=row_data.statistic_date.strftime('%d/%m/%Y'))
        ws.cell(row=i, column=2, value=row_data.total_visitors)
        ws.cell(row=i, column=3, value=row_data.new_visitors)
        ws.cell(row=i, column=4, value=row_data.returning_visitors)
        ws.cell(row=i, column=5, value=round(row_data.avg_duration_seconds / 60, 2))
        ws.cell(row=i, column=6, value=row_data.total_orders)
        
        revenue_cell = ws.cell(row=i, column=7, value=float(row_data.total_revenue))
        revenue_cell.number_format = '#,##0 "VND"'

    # SỬA LỖI Ở ĐÂY: Dùng get_column_letter thay vì gọi thuộc tính của cell (vì bị lỗi MergedCell)
    for col_idx in range(1, len(headers) + 1):
        col_letter = get_column_letter(col_idx)
        max_length = 0
        for row_idx in range(1, ws.max_row + 1):
            cell_value = ws.cell(row=row_idx, column=col_idx).value
            if cell_value is not None:
                max_length = max(max_length, len(str(cell_value)))
        ws.column_dimensions[col_letter].width = max_length + 2

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output