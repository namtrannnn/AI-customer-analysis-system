"""
Excel Report Service — Xuất báo cáo Excel chuyên nghiệp, chuẩn Executive Dashboard
Hỗ trợ đầy đủ 7 loại báo cáo: Summary, Activity, Customer, Revenue, Segment, Zone, Duration
Bao gồm: Formatting số/tiền tệ, Bảng dữ liệu xen kẽ màu, Dòng TỔNG CỘNG dùng Công thức Excel, Tự động chỉnh độ rộng cột
"""
import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from app.schemas.report_schema import ReportDataDTO, ReportType

# ─── Color Palette & Fills ───────────────────────────────────────────────────
FILL_BANNER   = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")  # Slate 800
FILL_SUBTITLE = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")  # Slate 100
FILL_HEADER   = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")  # Slate 900
FILL_HEADER_ALT = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")# Blue 600
FILL_ALT_ROW  = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")  # Slate 50
FILL_TOTAL    = PatternFill(start_color="EFF6FF", end_color="EFF6FF", fill_type="solid")  # Blue 50
FILL_KPI_HDR  = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")  # Slate 200
FILL_KPI_VAL  = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")  # Slate 50

# ─── Fonts ───────────────────────────────────────────────────────────────────
FONT_BANNER   = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
FONT_SUBTITLE = Font(name="Calibri", size=9.5, italic=True, color="475569")
FONT_SECTION  = Font(name="Calibri", size=11, bold=True, color="0F172A")
FONT_HEADER   = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
FONT_CELL     = Font(name="Calibri", size=9.5, color="0F172A")
FONT_CELL_BOLD= Font(name="Calibri", size=9.5, bold=True, color="0F172A")
FONT_TOTAL    = Font(name="Calibri", size=10, bold=True, color="1E3A8A")
FONT_KPI_LBL  = Font(name="Calibri", size=8.5, bold=True, color="475569")
FONT_KPI_VAL  = Font(name="Calibri", size=12, bold=True, color="0F172A")

# ─── Borders ──────────────────────────────────────────────────────────────────
THIN_SIDE    = Side(style="thin", color="CBD5E1")
THIN_BORDER  = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)

TOTAL_BORDER = Border(
    top=Side(style="thin", color="2563EB"),
    bottom=Side(style="double", color="1E293B"),
    left=THIN_SIDE,
    right=THIN_SIDE,
)

KPI_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)

# ─── Alignments ───────────────────────────────────────────────────────────────
ALIGN_LEFT   = Alignment(horizontal="left", vertical="center")
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_RIGHT  = Alignment(horizontal="right", vertical="center")

REPORT_TITLE = {
    ReportType.summary:  "BÁO CÁO TỔNG HỢP HỆ THỐNG AI",
    ReportType.activity: "BÁO CÁO HOẠT ĐỘNG KHÁCH HÀNG",
    ReportType.customer: "BÁO CÁO DANH SÁCH KHÁCH HÀNG",
    ReportType.revenue:  "BÁO CÁO DOANH THU & ĐƠN HÀNG",
    ReportType.segment:  "BÁO CÁO PHÂN NHÓM KHÁCH HÀNG AI",
    ReportType.zone:     "BÁO CÁO VÙNG THEO DÕI",
    ReportType.duration: "BÁO CÁO THỜI GIAN LƯU TRÚ",
}


# ─── Auto Column Widths & Gridlines ───────────────────────────────────────────
def _auto_fit_columns(ws, max_col: int):
    ws.views.sheetView[0].showGridLines = True
    for col_idx in range(1, max_col + 1):
        col_letter = get_column_letter(col_idx)
        max_len = 0
        for row_idx in range(1, ws.max_row + 1):
            cell_val = ws.cell(row=row_idx, column=col_idx).value
            if cell_val is not None and not str(cell_val).startswith("="):
                # Skip row 1 & 2 merged banners for length calculation
                if row_idx in (1, 2):
                    continue
                val_str = str(cell_val)
                if len(val_str) > max_len:
                    max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 5, 13)


# ─── Header Banner ────────────────────────────────────────────────────────────
def _write_header_banner(ws, data: ReportDataDTO, max_col: int = 7):
    title = REPORT_TITLE.get(data.report_type, "BÁO CÁO HỆ THỐNG AI")
    max_col_letter = get_column_letter(max_col)

    # Row 1: Title
    ws.merge_cells(f"A1:{max_col_letter}1")
    cell1 = ws["A1"]
    cell1.value = title
    cell1.font = FONT_BANNER
    cell1.fill = FILL_BANNER
    cell1.alignment = ALIGN_CENTER
    ws.row_dimensions[1].height = 32

    # Row 2: Subtitle
    ws.merge_cells(f"A2:{max_col_letter}2")
    cell2 = ws["A2"]
    cell2.value = f"Khoảng thời gian: {data.start_date.strftime('%d/%m/%Y')} — {data.end_date.strftime('%d/%m/%Y')}   |   AI Customer Analysis System"
    cell2.font = FONT_SUBTITLE
    cell2.fill = FILL_SUBTITLE
    cell2.alignment = ALIGN_CENTER
    ws.row_dimensions[2].height = 20
    ws.row_dimensions[3].height = 10


# ─── KPI Cards Grid (2 rows x 3 columns) ──────────────────────────────────────
def _write_kpi_cards_block(ws, summary, start_row: int = 4) -> int:
    s = summary
    avg_min = round(s.avg_duration_seconds / 60, 1) if s.avg_duration_seconds else 0.0

    kpis = [
        ("TỔNG LƯỢT KHÁCH",    s.total_visitors,          "#,##0"),
        ("KHÁCH HÀNG MỚI",     s.new_visitors,            "#,##0"),
        ("KHÁCH QUAY LẠI",     s.returning_visitors,       "#,##0"),
        ("TB THỜI GIAN LƯU TRÚ", f"{avg_min} phút",       None),
        ("TỔNG SỐ ĐƠN HÀNG",   s.total_orders,            "#,##0"),
        ("TỔNG DOANH THU",     s.total_revenue,           '#,##0 "VNĐ"'),
    ]

    # Row 1 of KPIs (rows start_row to start_row+1)
    # Row 2 of KPIs (rows start_row+3 to start_row+4)
    ws.cell(row=start_row, column=1, value="CHỈ SỐ HIỆU SUẤT CHÍNH (KPIs)").font = FONT_SECTION
    r = start_row + 1

    for idx, (label, val, num_fmt) in enumerate(kpis):
        grid_row = r if idx < 3 else r + 3
        col = (idx % 3) * 2 + 1  # Cols 1-2, 3-4, 5-6

        # Label cell
        ws.merge_cells(start_row=grid_row, start_column=col, end_row=grid_row, end_column=col+1)
        c_lbl = ws.cell(row=grid_row, column=col, value=label)
        c_lbl.font = FONT_KPI_LBL
        c_lbl.fill = FILL_KPI_HDR
        c_lbl.alignment = ALIGN_CENTER

        # Value cell
        val_row = grid_row + 1
        ws.merge_cells(start_row=val_row, start_column=col, end_row=val_row, end_column=col+1)
        c_val = ws.cell(row=val_row, column=col, value=val)
        c_val.font = FONT_KPI_VAL
        c_val.fill = FILL_KPI_VAL
        c_val.alignment = ALIGN_CENTER
        if num_fmt and isinstance(val, (int, float)):
            c_val.number_format = num_fmt

        # Borders around merged cells
        for row_i in range(grid_row, grid_row + 2):
            for col_j in range(col, col + 2):
                ws.cell(row=row_i, column=col_j).border = KPI_BORDER

    ws.row_dimensions[r].height = 18
    ws.row_dimensions[r+1].height = 24
    ws.row_dimensions[r+3].height = 18
    ws.row_dimensions[r+4].height = 24
    ws.row_dimensions[r+5].height = 12

    return r + 6


# ─── Table 1: Daily Stats Table ───────────────────────────────────────────────
def _write_daily_table(ws, daily_stats: list, start_row: int) -> int:
    headers = ["Ngày", "Tổng khách", "Khách mới", "Quay lại", "TB lưu trú (phút)", "Đơn hàng", "Doanh thu (VNĐ)"]
    
    ws.cell(row=start_row, column=1, value="CHI TIẾT THỐNG KÊ THEO NGÀY").font = FONT_SECTION
    r = start_row + 1

    # Header Row
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=r, column=col_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_CENTER
        cell.border = THIN_BORDER
    ws.row_dimensions[r].height = 26

    first_data_row = r + 1
    for i, d in enumerate(daily_stats, first_data_row):
        fill = FILL_ALT_ROW if i % 2 == 0 else PatternFill(fill_type=None)
        
        c1 = ws.cell(row=i, column=1, value=d.statistic_date.strftime("%d/%m/%Y"))
        c1.alignment = ALIGN_CENTER
        
        c2 = ws.cell(row=i, column=2, value=d.total_visitors)
        c2.number_format = "#,##0"
        c2.alignment = ALIGN_RIGHT

        c3 = ws.cell(row=i, column=3, value=d.new_visitors)
        c3.number_format = "#,##0"
        c3.alignment = ALIGN_RIGHT

        c4 = ws.cell(row=i, column=4, value=d.returning_visitors)
        c4.number_format = "#,##0"
        c4.alignment = ALIGN_RIGHT

        c5 = ws.cell(row=i, column=5, value=round(d.avg_duration_seconds / 60, 1))
        c5.number_format = '0.0 "ph"'
        c5.alignment = ALIGN_RIGHT

        c6 = ws.cell(row=i, column=6, value=d.total_orders)
        c6.number_format = "#,##0"
        c6.alignment = ALIGN_RIGHT

        c7 = ws.cell(row=i, column=7, value=float(d.total_revenue))
        c7.number_format = '#,##0 "VNĐ"'
        c7.alignment = ALIGN_RIGHT

        for col_idx in range(1, 8):
            cell = ws.cell(row=i, column=col_idx)
            cell.font = FONT_CELL
            cell.border = THIN_BORDER
            if fill.fill_type:
                cell.fill = fill
        ws.row_dimensions[i].height = 20

    last_data_row = first_data_row + len(daily_stats) - 1

    # Total Row with Formulas
    tot_row = last_data_row + 1
    t1 = ws.cell(row=tot_row, column=1, value="TỔNG CỘNG")
    t1.alignment = ALIGN_LEFT

    t2 = ws.cell(row=tot_row, column=2, value=f"=SUM(B{first_data_row}:B{last_data_row})")
    t2.number_format = "#,##0"
    t2.alignment = ALIGN_RIGHT

    t3 = ws.cell(row=tot_row, column=3, value=f"=SUM(C{first_data_row}:C{last_data_row})")
    t3.number_format = "#,##0"
    t3.alignment = ALIGN_RIGHT

    t4 = ws.cell(row=tot_row, column=4, value=f"=SUM(D{first_data_row}:D{last_data_row})")
    t4.number_format = "#,##0"
    t4.alignment = ALIGN_RIGHT

    t5 = ws.cell(row=tot_row, column=5, value=f"=AVERAGE(E{first_data_row}:E{last_data_row})")
    t5.number_format = '0.0 "ph"'
    t5.alignment = ALIGN_RIGHT

    t6 = ws.cell(row=tot_row, column=6, value=f"=SUM(F{first_data_row}:F{last_data_row})")
    t6.number_format = "#,##0"
    t6.alignment = ALIGN_RIGHT

    t7 = ws.cell(row=tot_row, column=7, value=f"=SUM(G{first_data_row}:G{last_data_row})")
    t7.number_format = '#,##0 "VNĐ"'
    t7.alignment = ALIGN_RIGHT

    for col_idx in range(1, 8):
        cell = ws.cell(row=tot_row, column=col_idx)
        cell.font = FONT_TOTAL
        cell.fill = FILL_TOTAL
        cell.border = TOTAL_BORDER
    ws.row_dimensions[tot_row].height = 24

    return tot_row + 2


# ─── Table 2: Customer List Table ─────────────────────────────────────────────
def _write_customer_table(ws, customers: list, start_row: int) -> int:
    headers = ["Mã khách", "Loại", "Tên khách hàng", "Lượt ghé", "TB lưu trú (phút)", "Chi tiêu (VNĐ)", "Nhóm AI"]

    ws.cell(row=start_row, column=1, value="DANH SÁCH KHÁCH HÀNG").font = FONT_SECTION
    r = start_row + 1

    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=r, column=col_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER_ALT
        cell.alignment = ALIGN_CENTER
        cell.border = THIN_BORDER
    ws.row_dimensions[r].height = 26

    first_data_row = r + 1
    for i, c in enumerate(customers, first_data_row):
        fill = FILL_ALT_ROW if i % 2 == 0 else PatternFill(fill_type=None)

        c1 = ws.cell(row=i, column=1, value=c.anonymous_code)
        c1.alignment = ALIGN_CENTER

        c2 = ws.cell(row=i, column=2, value="Nhận diện" if c.person_type == "identified" else "Ẩn danh")
        c2.alignment = ALIGN_CENTER

        c3 = ws.cell(row=i, column=3, value=c.customer_name or "—")
        c3.alignment = ALIGN_LEFT

        c4 = ws.cell(row=i, column=4, value=c.total_visits)
        c4.number_format = "#,##0"
        c4.alignment = ALIGN_RIGHT

        c5 = ws.cell(row=i, column=5, value=round(c.avg_duration_seconds / 60, 1))
        c5.number_format = '0.0 "ph"'
        c5.alignment = ALIGN_RIGHT

        c6 = ws.cell(row=i, column=6, value=float(c.total_spent))
        c6.number_format = '#,##0 "VNĐ"'
        c6.alignment = ALIGN_RIGHT

        c7 = ws.cell(row=i, column=7, value=c.segment_name or "—")
        c7.alignment = ALIGN_LEFT

        for col_idx in range(1, 8):
            cell = ws.cell(row=i, column=col_idx)
            cell.font = FONT_CELL
            cell.border = THIN_BORDER
            if fill.fill_type:
                cell.fill = fill
        ws.row_dimensions[i].height = 20

    last_data_row = first_data_row + len(customers) - 1

    # Total Row
    tot_row = last_data_row + 1
    ws.cell(row=tot_row, column=1, value="TỔNG CỘNG").alignment = ALIGN_LEFT
    ws.cell(row=tot_row, column=3, value=f"{len(customers)} khách hàng").alignment = ALIGN_LEFT

    t4 = ws.cell(row=tot_row, column=4, value=f"=SUM(D{first_data_row}:D{last_data_row})")
    t4.number_format = "#,##0"
    t4.alignment = ALIGN_RIGHT

    t5 = ws.cell(row=tot_row, column=5, value=f"=AVERAGE(E{first_data_row}:E{last_data_row})")
    t5.number_format = '0.0 "ph"'
    t5.alignment = ALIGN_RIGHT

    t6 = ws.cell(row=tot_row, column=6, value=f"=SUM(F{first_data_row}:F{last_data_row})")
    t6.number_format = '#,##0 "VNĐ"'
    t6.alignment = ALIGN_RIGHT

    for col_idx in range(1, 8):
        cell = ws.cell(row=tot_row, column=col_idx)
        cell.font = FONT_TOTAL
        cell.fill = FILL_TOTAL
        cell.border = TOTAL_BORDER
    ws.row_dimensions[tot_row].height = 24

    return tot_row + 2


# ─── Table 3: Segment Table ───────────────────────────────────────────────────
def _write_segment_table(ws, segments: list, start_row: int) -> int:
    headers = ["Tên nhóm AI", "Số thành viên", "TB lượt ghé", "TB lưu trú (phút)", "TB chi tiêu (VNĐ)"]

    ws.cell(row=start_row, column=1, value="PHÂN NHÓM KHÁCH HÀNG AI").font = FONT_SECTION
    r = start_row + 1

    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=r, column=col_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_CENTER
        cell.border = THIN_BORDER
    ws.row_dimensions[r].height = 26

    first_data_row = r + 1
    for i, seg in enumerate(segments, first_data_row):
        fill = FILL_ALT_ROW if i % 2 == 0 else PatternFill(fill_type=None)

        c1 = ws.cell(row=i, column=1, value=seg.segment_name)
        c1.alignment = ALIGN_LEFT
        c1.font = FONT_CELL_BOLD

        c2 = ws.cell(row=i, column=2, value=seg.member_count)
        c2.number_format = "#,##0"
        c2.alignment = ALIGN_RIGHT

        c3 = ws.cell(row=i, column=3, value=round(seg.avg_visits, 1))
        c3.number_format = "0.0"
        c3.alignment = ALIGN_RIGHT

        c4 = ws.cell(row=i, column=4, value=round(seg.avg_duration_seconds / 60, 1))
        c4.number_format = '0.0 "ph"'
        c4.alignment = ALIGN_RIGHT

        c5 = ws.cell(row=i, column=5, value=float(seg.avg_spent))
        c5.number_format = '#,##0 "VNĐ"'
        c5.alignment = ALIGN_RIGHT

        for col_idx in range(1, 6):
            cell = ws.cell(row=i, column=col_idx)
            cell.border = THIN_BORDER
            if col_idx != 1:
                cell.font = FONT_CELL
            if fill.fill_type:
                cell.fill = fill
        ws.row_dimensions[i].height = 20

    last_data_row = first_data_row + len(segments) - 1

    # Total Row
    tot_row = last_data_row + 1
    ws.cell(row=tot_row, column=1, value="TỔNG CỘNG").alignment = ALIGN_LEFT
    t2 = ws.cell(row=tot_row, column=2, value=f"=SUM(B{first_data_row}:B{last_data_row})")
    t2.number_format = "#,##0"
    t2.alignment = ALIGN_RIGHT

    t3 = ws.cell(row=tot_row, column=3, value=f"=AVERAGE(C{first_data_row}:C{last_data_row})")
    t3.number_format = "0.0"
    t3.alignment = ALIGN_RIGHT

    t4 = ws.cell(row=tot_row, column=4, value=f"=AVERAGE(D{first_data_row}:D{last_data_row})")
    t4.number_format = '0.0 "ph"'
    t4.alignment = ALIGN_RIGHT

    t5 = ws.cell(row=tot_row, column=5, value=f"=AVERAGE(E{first_data_row}:E{last_data_row})")
    t5.number_format = '#,##0 "VNĐ"'
    t5.alignment = ALIGN_RIGHT

    for col_idx in range(1, 6):
        cell = ws.cell(row=tot_row, column=col_idx)
        cell.font = FONT_TOTAL
        cell.fill = FILL_TOTAL
        cell.border = TOTAL_BORDER
    ws.row_dimensions[tot_row].height = 24

    return tot_row + 2


# ─── Table 4: Zone Table ──────────────────────────────────────────────────────
def _write_zone_table(ws, zones: list, start_row: int) -> int:
    headers = ["Tên vùng theo dõi", "Loại vùng", "Tổng lượt ghé", "TB lưu trú (phút)", "Khung giờ đông nhất"]

    ws.cell(row=start_row, column=1, value="CHI TIẾT VÙNG THEO DÕI").font = FONT_SECTION
    r = start_row + 1

    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=r, column=col_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_CENTER
        cell.border = THIN_BORDER
    ws.row_dimensions[r].height = 26

    first_data_row = r + 1
    for i, z in enumerate(zones, first_data_row):
        fill = FILL_ALT_ROW if i % 2 == 0 else PatternFill(fill_type=None)

        c1 = ws.cell(row=i, column=1, value=z.zone_name)
        c1.alignment = ALIGN_LEFT
        c1.font = FONT_CELL_BOLD

        c2 = ws.cell(row=i, column=2, value=z.zone_type)
        c2.alignment = ALIGN_CENTER

        c3 = ws.cell(row=i, column=3, value=z.total_visits)
        c3.number_format = "#,##0"
        c3.alignment = ALIGN_RIGHT

        c4 = ws.cell(row=i, column=4, value=round(z.avg_duration_seconds / 60, 1))
        c4.number_format = '0.0 "ph"'
        c4.alignment = ALIGN_RIGHT

        c5 = ws.cell(row=i, column=5, value=z.peak_hour or "—")
        c5.alignment = ALIGN_CENTER

        for col_idx in range(1, 6):
            cell = ws.cell(row=i, column=col_idx)
            cell.border = THIN_BORDER
            if col_idx != 1:
                cell.font = FONT_CELL
            if fill.fill_type:
                cell.fill = fill
        ws.row_dimensions[i].height = 20

    last_data_row = first_data_row + len(zones) - 1

    # Total Row
    tot_row = last_data_row + 1
    ws.cell(row=tot_row, column=1, value="TỔNG CỘNG").alignment = ALIGN_LEFT
    t3 = ws.cell(row=tot_row, column=3, value=f"=SUM(C{first_data_row}:C{last_data_row})")
    t3.number_format = "#,##0"
    t3.alignment = ALIGN_RIGHT

    t4 = ws.cell(row=tot_row, column=4, value=f"=AVERAGE(D{first_data_row}:D{last_data_row})")
    t4.number_format = '0.0 "ph"'
    t4.alignment = ALIGN_RIGHT

    for col_idx in range(1, 6):
        cell = ws.cell(row=tot_row, column=col_idx)
        cell.font = FONT_TOTAL
        cell.fill = FILL_TOTAL
        cell.border = TOTAL_BORDER
    ws.row_dimensions[tot_row].height = 24

    return tot_row + 2


# ─── Table 5: Duration Buckets Table ─────────────────────────────────────────
def _write_duration_table(ws, buckets: list, start_row: int) -> int:
    headers = ["Khoảng thời gian lưu trú", "Số lượt ghé", "Tỷ lệ phân bố (%)"]

    ws.cell(row=start_row, column=1, value="PHÂN PHỐI THỜI GIAN LƯU TRÚ").font = FONT_SECTION
    r = start_row + 1

    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=r, column=col_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_CENTER
        cell.border = THIN_BORDER
    ws.row_dimensions[r].height = 26

    first_data_row = r + 1
    for i, b in enumerate(buckets, first_data_row):
        fill = FILL_ALT_ROW if i % 2 == 0 else PatternFill(fill_type=None)

        c1 = ws.cell(row=i, column=1, value=b.label)
        c1.alignment = ALIGN_LEFT
        c1.font = FONT_CELL_BOLD

        c2 = ws.cell(row=i, column=2, value=b.count)
        c2.number_format = "#,##0"
        c2.alignment = ALIGN_RIGHT

        c3 = ws.cell(row=i, column=3, value=float(b.pct / 100.0))
        c3.number_format = "0.0%"
        c3.alignment = ALIGN_RIGHT

        for col_idx in range(1, 4):
            cell = ws.cell(row=i, column=col_idx)
            cell.border = THIN_BORDER
            if col_idx != 1:
                cell.font = FONT_CELL
            if fill.fill_type:
                cell.fill = fill
        ws.row_dimensions[i].height = 20

    last_data_row = first_data_row + len(buckets) - 1

    # Total Row
    tot_row = last_data_row + 1
    ws.cell(row=tot_row, column=1, value="TỔNG CỘNG").alignment = ALIGN_LEFT

    t2 = ws.cell(row=tot_row, column=2, value=f"=SUM(B{first_data_row}:B{last_data_row})")
    t2.number_format = "#,##0"
    t2.alignment = ALIGN_RIGHT

    t3 = ws.cell(row=tot_row, column=3, value=f"=SUM(C{first_data_row}:C{last_data_row})")
    t3.number_format = "0.0%"
    t3.alignment = ALIGN_RIGHT

    for col_idx in range(1, 4):
        cell = ws.cell(row=tot_row, column=col_idx)
        cell.font = FONT_TOTAL
        cell.fill = FILL_TOTAL
        cell.border = TOTAL_BORDER
    ws.row_dimensions[tot_row].height = 24

    return tot_row + 2


# ─── Main Generator ───────────────────────────────────────────────────────────
def generate_excel_report(data: ReportDataDTO) -> io.BytesIO:
    wb = Workbook()
    
    # ── 1. Summary Report (Multi-sheet) ───────────────────────────────────────
    if data.report_type == ReportType.summary:
        ws = wb.active
        ws.title = "Tổng Quan & Thống Kê"
        _write_header_banner(ws, data, max_col=7)
        next_row = _write_kpi_cards_block(ws, data.summary, start_row=4)
        if data.daily_stats:
            _write_daily_table(ws, data.daily_stats, start_row=next_row)
        _auto_fit_columns(ws, max_col=7)

        if data.customers:
            ws2 = wb.create_sheet("Danh Sách Khách Hàng")
            _write_header_banner(ws2, data, max_col=7)
            _write_customer_table(ws2, data.customers, start_row=4)
            _auto_fit_columns(ws2, max_col=7)

        if data.segments or data.zones:
            ws3 = wb.create_sheet("Nhóm AI & Vùng")
            _write_header_banner(ws3, data, max_col=5)
            r3 = 4
            if data.segments:
                r3 = _write_segment_table(ws3, data.segments, start_row=r3)
            if data.zones:
                _write_zone_table(ws3, data.zones, start_row=r3)
            _auto_fit_columns(ws3, max_col=5)

        if data.duration_buckets:
            ws4 = wb.create_sheet("Thời Gian Lưu Trú")
            _write_header_banner(ws4, data, max_col=3)
            _write_duration_table(ws4, data.duration_buckets, start_row=4)
            _auto_fit_columns(ws4, max_col=3)

    # ── 2. Activity Report ────────────────────────────────────────────────────
    elif data.report_type == ReportType.activity:
        ws = wb.active
        ws.title = "Hoạt Động Khách Hàng"
        _write_header_banner(ws, data, max_col=7)
        next_row = _write_kpi_cards_block(ws, data.summary, start_row=4)
        if data.daily_stats:
            _write_daily_table(ws, data.daily_stats, start_row=next_row)
        _auto_fit_columns(ws, max_col=7)

    # ── 3. Customer Report ────────────────────────────────────────────────────
    elif data.report_type == ReportType.customer:
        ws = wb.active
        ws.title = "Danh Sách Khách Hàng"
        _write_header_banner(ws, data, max_col=7)
        next_row = _write_kpi_cards_block(ws, data.summary, start_row=4)
        if data.customers:
            _write_customer_table(ws, data.customers, start_row=next_row)
        _auto_fit_columns(ws, max_col=7)

    # ── 4. Revenue Report ─────────────────────────────────────────────────────
    elif data.report_type == ReportType.revenue:
        ws = wb.active
        ws.title = "Doanh Thu & Đơn Hàng"
        _write_header_banner(ws, data, max_col=7)
        next_row = _write_kpi_cards_block(ws, data.summary, start_row=4)
        if data.daily_stats:
            _write_daily_table(ws, data.daily_stats, start_row=next_row)
        _auto_fit_columns(ws, max_col=7)

    # ── 5. Segment Report ─────────────────────────────────────────────────────
    elif data.report_type == ReportType.segment:
        ws = wb.active
        ws.title = "Phân Nhóm AI"
        _write_header_banner(ws, data, max_col=5)
        next_row = _write_kpi_cards_block(ws, data.summary, start_row=4)
        if data.segments:
            _write_segment_table(ws, data.segments, start_row=next_row)
        _auto_fit_columns(ws, max_col=5)

    # ── 6. Zone Report ────────────────────────────────────────────────────────
    elif data.report_type == ReportType.zone:
        ws = wb.active
        ws.title = "Vùng Theo Dõi"
        _write_header_banner(ws, data, max_col=5)
        next_row = _write_kpi_cards_block(ws, data.summary, start_row=4)
        if data.zones:
            _write_zone_table(ws, data.zones, start_row=next_row)
        _auto_fit_columns(ws, max_col=5)

    # ── 7. Duration Report ────────────────────────────────────────────────────
    elif data.report_type == ReportType.duration:
        ws = wb.active
        ws.title = "Thời Gian Lưu Trú"
        _write_header_banner(ws, data, max_col=3)
        next_row = _write_kpi_cards_block(ws, data.summary, start_row=4)
        if data.duration_buckets:
            _write_duration_table(ws, data.duration_buckets, start_row=next_row)
        _auto_fit_columns(ws, max_col=3)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
