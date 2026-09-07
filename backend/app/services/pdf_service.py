import io
import os
from fastapi import HTTPException
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.schemas.report_schema import ReportDataDTO, ReportType

REPORT_TITLE = {
    ReportType.summary:  "BÁO CÁO TỔNG HỢP",
    ReportType.activity: "BÁO CÁO HOẠT ĐỘNG KHÁCH HÀNG",
    ReportType.customer: "BÁO CÁO DANH SÁCH KHÁCH HÀNG",
    ReportType.revenue:  "BÁO CÁO DOANH THU & ĐƠN HÀNG",
}

HEADER_COLOR = {
    ReportType.summary:  colors.HexColor("#4F81BD"),
    ReportType.activity: colors.HexColor("#375623"),
    ReportType.customer: colors.HexColor("#7030A0"),
    ReportType.revenue:  colors.HexColor("#C65911"),
}


def _load_font() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.normpath(os.path.join(current_dir, "..", "utils", "fonts", "times.ttf"))
    if not os.path.exists(font_path):
        raise HTTPException(
            status_code=500,
            detail=f"Không tìm thấy font tiếng Việt tại: {font_path}",
        )
    # Chỉ đăng ký 1 lần
    try:
        pdfmetrics.getFont("TimesVI")
    except Exception:
        pdfmetrics.registerFont(TTFont("TimesVI", font_path))
    return "TimesVI"


def generate_pdf_report(data: ReportDataDTO) -> io.BytesIO:
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4,
                            leftMargin=40, rightMargin=40,
                            topMargin=40, bottomMargin=40)
    font_name = _load_font()
    hdr_color = HEADER_COLOR.get(data.report_type, colors.HexColor("#4F81BD"))

    title_style  = ParagraphStyle("T", fontName=font_name, fontSize=16, alignment=1, spaceAfter=6, leading=20)
    sub_style    = ParagraphStyle("S", fontName=font_name, fontSize=11, alignment=1, spaceAfter=16, textColor=colors.grey)
    section_style = ParagraphStyle("SEC", fontName=font_name, fontSize=13, spaceBefore=14, spaceAfter=6)

    elements = []
    title = REPORT_TITLE.get(data.report_type, "BÁO CÁO")
    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(
        f"Từ ngày: {data.start_date.strftime('%d/%m/%Y')}  —  Đến ngày: {data.end_date.strftime('%d/%m/%Y')}",
        sub_style,
    ))

    s = data.summary
    avg_min = round(s.avg_duration_seconds / 60, 1)

    # ── Summary block ─────────────────────────────────────────────────────────
    if data.report_type in (ReportType.summary, ReportType.activity):
        summary_rows = [
            ["Tổng lượt khách", str(s.total_visitors), "Khách mới", str(s.new_visitors)],
            ["Khách quay lại", str(s.returning_visitors), "TG lưu trú TB", f"{avg_min} phút"],
            ["Tổng đơn hàng", str(s.total_orders), "Tổng doanh thu", f"{s.total_revenue:,.0f} VND"],
        ]
    elif data.report_type == ReportType.revenue:
        cr = (s.total_orders / s.total_visitors * 100) if s.total_visitors else 0
        summary_rows = [
            ["Tổng lượt khách", str(s.total_visitors), "Tổng đơn hàng", str(s.total_orders)],
            ["Tổng doanh thu", f"{s.total_revenue:,.0f} VND", "Tỷ lệ chuyển đổi", f"{cr:.1f}%"],
        ]
    else:
        summary_rows = []

    if summary_rows:
        sum_table = Table(summary_rows, colWidths=[130, 100, 130, 130])
        sum_table.setStyle(TableStyle([
            ("FONTNAME",   (0,0), (-1,-1), font_name),
            ("FONTSIZE",   (0,0), (-1,-1), 11),
            ("GRID",       (0,0), (-1,-1), 0.5, colors.grey),
            ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#EBF3FF")),
            ("BACKGROUND", (2,0), (2,-1), colors.HexColor("#EBF3FF")),
            ("FONTNAME",   (0,0), (0,-1), font_name),
            ("FONTNAME",   (2,0), (2,-1), font_name),
            ("FONTWEIGHT", (0,0), (0,-1), "BOLD"),
            ("FONTWEIGHT", (2,0), (2,-1), "BOLD"),
        ]))
        elements.append(sum_table)
        elements.append(Spacer(1, 16))

    # ── Daily table ───────────────────────────────────────────────────────────
    if data.daily_stats and data.report_type in (ReportType.summary, ReportType.activity, ReportType.revenue):
        elements.append(Paragraph("Chi tiết theo ngày", section_style))
        daily_headers = ["Ngày", "Tổng khách", "Mới", "Quay lại", "TB (phút)", "Đơn", "Doanh thu (VND)"]
        daily_rows = [daily_headers] + [
            [
                r.statistic_date.strftime("%d/%m/%Y"),
                str(r.total_visitors),
                str(r.new_visitors),
                str(r.returning_visitors),
                str(round(r.avg_duration_seconds / 60, 1)),
                str(r.total_orders),
                f"{r.total_revenue:,.0f}",
            ]
            for r in data.daily_stats
        ]
        daily_table = Table(daily_rows, repeatRows=1,
                            colWidths=[65, 60, 45, 55, 60, 40, 85])
        daily_table.setStyle(TableStyle([
            ("FONTNAME",    (0,0), (-1,-1), font_name),
            ("FONTSIZE",    (0,0), (-1,-1), 10),
            ("BACKGROUND",  (0,0), (-1,0),  hdr_color),
            ("TEXTCOLOR",   (0,0), (-1,0),  colors.white),
            ("FONTWEIGHT",  (0,0), (-1,0),  "BOLD"),
            ("ALIGN",       (0,0), (-1,-1), "CENTER"),
            ("GRID",        (0,0), (-1,-1), 0.4, colors.black),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F5F5F5")]),
        ]))
        elements.append(daily_table)

    # ── Customer table ────────────────────────────────────────────────────────
    if data.customers and data.report_type in (ReportType.summary, ReportType.customer):
        elements.append(Spacer(1, 16))
        elements.append(Paragraph("Danh sách khách hàng", section_style))
        cust_headers = ["Mã khách", "Loại", "Tên KH", "Lượt ghé", "TB (phút)", "Chi tiêu (VND)", "Nhóm AI"]
        cust_rows = [cust_headers] + [
            [
                c.anonymous_code,
                "Nhận diện" if c.person_type == "identified" else "Ẩn danh",
                c.customer_name or "—",
                str(c.total_visits),
                str(round(c.avg_duration_seconds / 60, 1)),
                f"{c.total_spent:,.0f}",
                c.segment_name or "—",
            ]
            for c in data.customers
        ]
        cust_table = Table(cust_rows, repeatRows=1,
                           colWidths=[65, 55, 75, 45, 55, 75, 70])
        cust_table.setStyle(TableStyle([
            ("FONTNAME",    (0,0), (-1,-1), font_name),
            ("FONTSIZE",    (0,0), (-1,-1), 9),
            ("BACKGROUND",  (0,0), (-1,0),  HEADER_COLOR[ReportType.customer]),
            ("TEXTCOLOR",   (0,0), (-1,0),  colors.white),
            ("ALIGN",       (0,0), (-1,-1), "CENTER"),
            ("GRID",        (0,0), (-1,-1), 0.4, colors.black),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F5F5F5")]),
        ]))
        elements.append(cust_table)

    doc.build(elements)
    output.seek(0)
    return output
