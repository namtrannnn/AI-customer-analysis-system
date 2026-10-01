"""
PDF Report Service — Tạo báo cáo PDF chuyên nghiệp, đẳng cấp Executive Dashboard
Layout: Cover Banner (với Title & Date range sắc nét) → KPI Cards Grid (2x3) → Charts → Data Tables → Footers (Trang X / Y)
"""
import io
import os
from datetime import datetime
from typing import List
from fastapi import HTTPException

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, Image, HRFlowable, KeepTogether,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.schemas.report_schema import ReportDataDTO, ReportType
from app.services.chart_service import (
    make_visitor_trend_chart,
    make_visitor_pie_chart,
    make_revenue_bar_chart,
    make_segment_pie_chart,
    make_zone_bar_chart,
    make_duration_histogram,
)

# ─── Color Palette ────────────────────────────────────────────────────────────
C_NAVY       = colors.HexColor("#0f172a")   # Slate 900
C_HEADER_BG  = colors.HexColor("#1e293b")   # Slate 800
C_PRIMARY    = colors.HexColor("#2563eb")   # Blue 600
C_PRIMARY_LT = colors.HexColor("#eff6ff")   # Blue 50
C_ACCENT     = colors.HexColor("#0284c7")   # Sky 600
C_SUCCESS    = colors.HexColor("#059669")   # Emerald 600
C_WARNING    = colors.HexColor("#d97706")   # Amber 600
C_DANGER     = colors.HexColor("#e11d48")   # Rose 600
C_PURPLE     = colors.HexColor("#7c3aed")   # Violet 600
C_TEAL       = colors.HexColor("#0d9488")   # Teal 600
C_BG_LIGHT   = colors.HexColor("#f8fafc")   # Slate 50
C_TEXT       = colors.HexColor("#0f172a")   # Slate 900
C_TEXT_MUTED = colors.HexColor("#64748b")   # Slate 500
C_BORDER     = colors.HexColor("#e2e8f0")   # Slate 200
C_ROW_ALT    = colors.HexColor("#f8fafc")   # Slate 50
C_WHITE      = colors.white

HEADER_COLORS = {
    ReportType.summary:  colors.HexColor("#0f172a"),
    ReportType.activity: colors.HexColor("#064e3b"),
    ReportType.customer: colors.HexColor("#3b0764"),
    ReportType.revenue:  colors.HexColor("#451a03"),
    ReportType.segment:  colors.HexColor("#431407"),
    ReportType.zone:     colors.HexColor("#042f2e"),
    ReportType.duration: colors.HexColor("#1e1b4b"),
}

REPORT_TITLES = {
    ReportType.summary:  "BÁO CÁO TỔNG HỢP HỆ THỐNG",
    ReportType.activity: "BÁO CÁO HOẠT ĐỘNG KHÁCH HÀNG",
    ReportType.customer: "BÁO CÁO DANH SÁCH KHÁCH HÀNG",
    ReportType.revenue:  "BÁO CÁO DOANH THU & ĐƠN HÀNG",
    ReportType.segment:  "BÁO CÁO PHÂN NHÓM KHÁCH HÀNG AI",
    ReportType.zone:     "BÁO CÁO VÙNG THEO DÕI",
    ReportType.duration: "BÁO CÁO THỜI GIAN LƯU TRÚ",
}

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm
CONTENT_W = PAGE_W - 2 * MARGIN


# ─── Font Loader ──────────────────────────────────────────────────────────────
def _load_font() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    fonts_dir   = os.path.normpath(os.path.join(current_dir, "..", "utils", "fonts"))
    
    arial_p   = os.path.join(fonts_dir, "arial.ttf")
    arialbd_p = os.path.join(fonts_dir, "arialbd.ttf")
    times_p   = os.path.join(fonts_dir, "times.ttf")
    timesbd_p = os.path.join(fonts_dir, "timesbd.ttf")

    if os.path.exists(arial_p):
        font_name = "Arial"
        try:
            pdfmetrics.getFont("Arial")
        except Exception:
            pdfmetrics.registerFont(TTFont("Arial", arial_p))
        try:
            pdfmetrics.getFont("Arial-Bold")
        except Exception:
            if os.path.exists(arialbd_p):
                pdfmetrics.registerFont(TTFont("Arial-Bold", arialbd_p))
            else:
                pdfmetrics.registerFont(TTFont("Arial-Bold", arial_p))
        return font_name
    elif os.path.exists(times_p):
        font_name = "Times"
        try:
            pdfmetrics.getFont("Times")
        except Exception:
            pdfmetrics.registerFont(TTFont("Times", times_p))
        try:
            pdfmetrics.getFont("Times-Bold")
        except Exception:
            if os.path.exists(timesbd_p):
                pdfmetrics.registerFont(TTFont("Times-Bold", timesbd_p))
            else:
                pdfmetrics.registerFont(TTFont("Times-Bold", times_p))
        return font_name
    else:
        raise HTTPException(status_code=500, detail="Không tìm thấy font chữ Tiếng Việt thích hợp.")


# ─── Styles ───────────────────────────────────────────────────────────────────
def _styles(font: str):
    bold = font + "-Bold"
    return {
        "section":  ParagraphStyle("sec",      fontName=bold, fontSize=11,  textColor=C_NAVY, spaceBefore=10, spaceAfter=6, leading=14, keepWithNext=True),
        "body":     ParagraphStyle("body",     fontName=font, fontSize=8.5, textColor=C_TEXT, spaceAfter=2, leading=12),
        "muted":    ParagraphStyle("muted",    fontName=font, fontSize=8,   textColor=C_TEXT_MUTED),
        "kpi_lbl":  ParagraphStyle("kpil",     fontName=bold, fontSize=7.5, textColor=C_TEXT_MUTED, alignment=0, leading=9),
        "kpi_val":  ParagraphStyle("kpiv",     fontName=bold, fontSize=13,  textColor=C_NAVY, alignment=0, leading=16),
        "kpi_sub":  ParagraphStyle("kpis",     fontName=font, fontSize=7.5, textColor=C_TEXT_MUTED, alignment=0),
        "footer":   ParagraphStyle("footer",   fontName=font, fontSize=7.5, textColor=C_TEXT_MUTED, alignment=1),
        "tbl_hdr":  ParagraphStyle("tblhdr",   fontName=bold, fontSize=8.5, textColor=C_WHITE, alignment=1),
        "tbl_cell": ParagraphStyle("tblcell",  fontName=font, fontSize=8,   textColor=C_TEXT, leading=10),
        "tbl_cell_center": ParagraphStyle("tblcellc", fontName=font, fontSize=8, textColor=C_TEXT, alignment=1, leading=10),
        "tbl_cell_bold":   ParagraphStyle("tblcellb", fontName=bold, fontSize=8, textColor=C_NAVY, leading=10),
    }


# ─── Numbered Canvas (Two-pass page count for Trang X / Y) ───────────────────
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, report_type=ReportType.summary, font="Arial", generated_at="", start_date=None, end_date=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.report_type = report_type
        self.font = font
        self.generated_at = generated_at
        self.start_date = start_date
        self.end_date = end_date

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def _draw_page_decorations(self, page_count):
        self.saveState()
        page_num = self._pageNumber
        hdr_color = HEADER_COLORS.get(self.report_type, C_NAVY)
        bold_font = self.font + "-Bold"

        if page_num == 1:
            # Cover header banner (3.8 cm)
            self.setFillColor(hdr_color)
            self.rect(0, PAGE_H - 3.6*cm, PAGE_W, 3.6*cm, fill=1, stroke=0)
            
            # Accent bottom bar
            self.setFillColor(C_PRIMARY)
            self.rect(0, PAGE_H - 3.72*cm, PAGE_W, 0.12*cm, fill=1, stroke=0)

            # Top branding
            self.setFont(bold_font, 8.5)
            self.setFillColor(colors.HexColor("#38bdf8"))
            self.drawString(MARGIN, PAGE_H - 0.7*cm, "AI CUSTOMER ANALYSIS SYSTEM")

            self.setFont(self.font, 8)
            self.setFillColor(colors.HexColor("#cbd5e1"))
            self.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.7*cm, f"Xuất lúc: {self.generated_at}")

            # Main Report Title (Centered inside dark header)
            title_text = REPORT_TITLES.get(self.report_type, "BÁO CÁO TỔNG HỢP")
            self.setFont(bold_font, 16)
            self.setFillColor(C_WHITE)
            self.drawCentredString(PAGE_W / 2.0, PAGE_H - 1.8*cm, title_text)

            # Date Range Subtitle (Centered inside dark header)
            if self.start_date and self.end_date:
                date_str = f"Khoảng thời gian: {self.start_date.strftime('%d/%m/%Y')} — {self.end_date.strftime('%d/%m/%Y')}"
                self.setFont(self.font, 9.5)
                self.setFillColor(colors.HexColor("#93c5fd"))
                self.drawCentredString(PAGE_W / 2.0, PAGE_H - 2.7*cm, date_str)

        else:
            # Subsequent pages header
            self.setFillColor(hdr_color)
            self.rect(0, PAGE_H - 0.95*cm, PAGE_W, 0.95*cm, fill=1, stroke=0)
            self.setFillColor(C_PRIMARY)
            self.rect(0, PAGE_H - 1.02*cm, PAGE_W, 0.07*cm, fill=1, stroke=0)

            self.setFont(bold_font, 8.5)
            self.setFillColor(C_WHITE)
            self.drawString(MARGIN, PAGE_H - 0.65*cm, REPORT_TITLES.get(self.report_type, "BÁO CÁO"))

            self.setFont(self.font, 8)
            self.setFillColor(colors.HexColor("#94a3b8"))
            self.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.65*cm, f"Trang {page_num} / {page_count}")

        # Footer on all pages
        self.setFillColor(C_BG_LIGHT)
        self.rect(0, 0, PAGE_W, 1.0*cm, fill=1, stroke=0)
        self.setFillColor(C_BORDER)
        self.rect(0, 1.0*cm, PAGE_W, 0.04*cm, fill=1, stroke=0)

        self.setFont(self.font, 7.5)
        self.setFillColor(C_TEXT_MUTED)
        self.drawString(MARGIN, 0.4*cm, "AI Customer Analysis System  |  Tài liệu báo cáo nội bộ")
        self.drawRightString(PAGE_W - MARGIN, 0.4*cm, f"Trang {page_num} / {page_count}")

        self.restoreState()


# ─── KPI Cards Grid (2 rows x 3 columns) ──────────────────────────────────────
def _kpi_cards(s, font: str, S: dict) -> Table:
    avg_min = round(s.avg_duration_seconds / 60, 1) if s.avg_duration_seconds else 0.0
    
    # Smart revenue formatting
    if s.total_revenue >= 1_000_000:
        rev_str = f"{s.total_revenue / 1_000_000:,.1f} triệu VNĐ"
    else:
        rev_str = f"{s.total_revenue:,.0f} VNĐ"

    kpis = [
        ("TỔNG LƯỢT KHÁCH",   f"{s.total_visitors:,}",     "Lượt ghé tổng cộng", C_PRIMARY),
        ("KHÁCH HÀNG MỚI",    f"{s.new_visitors:,}",       f"{round(s.new_visitors/s.total_visitors*100, 1) if s.total_visitors else 0}% tổng khách", C_SUCCESS),
        ("KHÁCH QUAY LẠI",    f"{s.returning_visitors:,}", f"{round(s.returning_visitors/s.total_visitors*100, 1) if s.total_visitors else 0}% tổng khách", C_PURPLE),
        ("TB THỜI GIAN LƯU TRÚ", f"{avg_min} phút",       "Thời gian trung bình", C_TEAL),
        ("TỔNG SỐ ĐƠN HÀNG",  f"{s.total_orders:,}",       "Đơn hàng hoàn tất", C_WARNING),
        ("TỔNG DOANH THU",    rev_str,                    "Doanh thu tổng cộng", C_DANGER),
    ]

    card_tables = []
    card_w = (CONTENT_W - 10) / 3

    for title, val, sub, color in kpis:
        c_hex = color.hexval() if hasattr(color, 'hexval') else "#2563eb"
        
        val_p = Paragraph(f'<font color="{c_hex}"><b>{val}</b></font>', S["kpi_val"])
        lbl_p = Paragraph(title, S["kpi_lbl"])
        sub_p = Paragraph(sub, S["kpi_sub"])

        card = Table(
            [[lbl_p], [Spacer(1, 1*mm)], [val_p], [Spacer(1, 0.5*mm)], [sub_p]],
            colWidths=[card_w],
        )
        card.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), C_BG_LIGHT),
            ("BOX",           (0,0), (-1,-1), 0.6, C_BORDER),
            ("LINEBEFORE",    (0,0), (0,-1),  3.5, color),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ]))
        card_tables.append(card)

    row1 = card_tables[0:3]
    row2 = card_tables[3:6]

    grid = Table([row1, row2], colWidths=[card_w, card_w, card_w])
    grid.setStyle(TableStyle([
        ("LEFTPADDING",   (0,0), (-1,-1), 2),
        ("RIGHTPADDING",  (0,0), (-1,-1), 2),
        ("TOPPADDING",    (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    return grid


# ─── Section Header ───────────────────────────────────────────────────────────
def _section(title: str, S: dict) -> list:
    return [
        Spacer(1, 3*mm),
        Paragraph(f'<font color="#2563eb">■</font>  {title}', S["section"]),
        HRFlowable(width=CONTENT_W, thickness=0.6, color=C_BORDER, spaceBefore=1, spaceAfter=5),
    ]


# ─── Data Table Generator ─────────────────────────────────────────────────────
def _styled_table(rows: list, col_widths: list, hdr_color=None, has_total=False) -> Table:
    hdr_color = hdr_color or C_HEADER_BG
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    
    style_cmds = [
        ("FONTNAME",       (0,0), (-1,-1),  "Arial"),
        ("FONTSIZE",       (0,0), (-1,-1),  8),
        ("BACKGROUND",     (0,0), (-1,0),   hdr_color),
        ("TEXTCOLOR",      (0,0), (-1,0),   C_WHITE),
        ("ALIGN",          (0,0), (-1,0),   "CENTER"),
        ("VALIGN",         (0,0), (-1,-1),  "MIDDLE"),
        ("GRID",           (0,0), (-1,-1),  0.4, C_BORDER),
        ("ROWBACKGROUNDS", (0,1), (-1,-1 if not has_total else -2), [C_WHITE, C_ROW_ALT]),
        ("TOPPADDING",     (0,0), (-1,-1),  4.5),
        ("BOTTOMPADDING",  (0,0), (-1,-1),  4.5),
        ("LEFTPADDING",    (0,0), (-1,-1),  5),
        ("RIGHTPADDING",   (0,0), (-1,-1),  5),
    ]

    if has_total:
        style_cmds.extend([
            ("BACKGROUND",   (0,-1), (-1,-1), C_PRIMARY_LT),
            ("FONTNAME",     (0,-1), (-1,-1), "Arial-Bold"),
            ("TEXTCOLOR",    (0,-1), (-1,-1), C_NAVY),
            ("LINEABOVE",    (0,-1), (-1,-1), 1.2, C_PRIMARY),
        ])

    t.setStyle(TableStyle(style_cmds))
    return t


# ─── Chart Image Helper ───────────────────────────────────────────────────────
def _chart_img(png_bytes: bytes, width: float, height: float) -> Image | None:
    if not png_bytes:
        return None
    img = Image(io.BytesIO(png_bytes), width=width, height=height)
    img.hAlign = "CENTER"
    return img


# ─── Main Generator ───────────────────────────────────────────────────────────
def generate_pdf_report(data: ReportDataDTO) -> io.BytesIO:
    output  = io.BytesIO()
    font    = _load_font()
    S       = _styles(font)
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    hdr_color = HEADER_COLORS.get(data.report_type, C_NAVY)

    doc = SimpleDocTemplate(
        output, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=4.0*cm,   # space for cover header
        bottomMargin=1.4*cm,
        title=REPORT_TITLES.get(data.report_type, "Báo cáo"),
        author="AI Customer Analysis System",
    )

    elements = []

    # ── KPI Cards Grid ────────────────────────────────────────────────────────
    s = data.summary
    if data.daily_stats or data.report_type in (ReportType.summary, ReportType.activity, ReportType.revenue):
        elements += _section("Chỉ số hiệu suất chính (KPIs)", S)
        elements.append(_kpi_cards(s, font, S))
        elements.append(Spacer(1, 3*mm))

    # ── Charts: Activity / Summary ────────────────────────────────────────────
    if data.report_type in (ReportType.summary, ReportType.activity):
        pie_bytes  = make_visitor_pie_chart(data)
        line_bytes = make_visitor_trend_chart(data)
        if pie_bytes or line_bytes:
            chart_elems = _section("Phân tích lượt khách & Xu hướng", S)
            imgs = []
            if pie_bytes:
                imgs.append(_chart_img(pie_bytes, CONTENT_W * 0.44, CONTENT_W * 0.23))
            if line_bytes:
                imgs.append(_chart_img(line_bytes, CONTENT_W * 0.54, CONTENT_W * 0.23))
            if len(imgs) == 2:
                ct = Table([imgs], colWidths=[CONTENT_W * 0.45, CONTENT_W * 0.55])
                ct.setStyle(TableStyle([
                    ("ALIGN",        (0,0), (-1,-1), "CENTER"),
                    ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
                    ("LEFTPADDING",  (0,0), (-1,-1), 0),
                    ("RIGHTPADDING", (0,0), (-1,-1), 0),
                ]))
                chart_elems.append(ct)
            elif imgs:
                chart_elems.append(imgs[0])
            elements.append(KeepTogether(chart_elems))
            elements.append(Spacer(1, 3*mm))

    # ── Charts: Revenue ───────────────────────────────────────────────────────
    if data.report_type in (ReportType.summary, ReportType.revenue):
        rev_bytes = make_revenue_bar_chart(data)
        if rev_bytes:
            rev_elems = _section("Biểu đồ doanh thu theo ngày", S)
            img = _chart_img(rev_bytes, CONTENT_W, CONTENT_W * 0.35)
            if img:
                rev_elems.append(img)
            elements.append(KeepTogether(rev_elems))
            elements.append(Spacer(1, 3*mm))

    # ── Charts: Segment ───────────────────────────────────────────────────────
    if data.report_type in (ReportType.summary, ReportType.segment) and data.segments:
        seg_bytes = make_segment_pie_chart(data)
        if seg_bytes:
            seg_elems = _section("Phân bố nhóm khách hàng AI", S)
            img = _chart_img(seg_bytes, CONTENT_W * 0.75, CONTENT_W * 0.34)
            if img:
                seg_elems.append(img)
            elements.append(KeepTogether(seg_elems))
            elements.append(Spacer(1, 3*mm))

    # ── Charts: Zone ─────────────────────────────────────────────────────────
    if data.report_type in (ReportType.summary, ReportType.zone) and data.zones:
        zone_bytes = make_zone_bar_chart(data)
        if zone_bytes:
            zone_elems = _section("Lượt ghé theo vùng theo dõi", S)
            img = _chart_img(zone_bytes, CONTENT_W, CONTENT_W * 0.34)
            if img:
                zone_elems.append(img)
            elements.append(KeepTogether(zone_elems))
            elements.append(Spacer(1, 3*mm))

    # ── Charts: Duration ─────────────────────────────────────────────────────
    if data.report_type in (ReportType.summary, ReportType.duration) and data.duration_buckets:
        dur_bytes = make_duration_histogram(data)
        if dur_bytes:
            dur_elems = _section("Phân phối thời gian lưu trú", S)
            img = _chart_img(dur_bytes, CONTENT_W * 0.75, CONTENT_W * 0.34)
            if img:
                dur_elems.append(img)
            elements.append(KeepTogether(dur_elems))
            elements.append(Spacer(1, 3*mm))

    # ── Table: Daily stats ────────────────────────────────────────────────────
    if data.daily_stats and data.report_type in (
        ReportType.summary, ReportType.activity, ReportType.revenue
    ):
        tbl_elems = _section("Chi tiết thống kê hoạt động theo ngày", S)
        hdrs = [
            Paragraph("Ngày", S["tbl_hdr"]),
            Paragraph("Tổng khách", S["tbl_hdr"]),
            Paragraph("Mới", S["tbl_hdr"]),
            Paragraph("Quay lại", S["tbl_hdr"]),
            Paragraph("TB lưu trú", S["tbl_hdr"]),
            Paragraph("Đơn hàng", S["tbl_hdr"]),
            Paragraph("Doanh thu (VNĐ)", S["tbl_hdr"]),
        ]
        
        rows = [hdrs]
        tot_vis = sum(r.total_visitors for r in data.daily_stats)
        tot_new = sum(r.new_visitors for r in data.daily_stats)
        tot_ret = sum(r.returning_visitors for r in data.daily_stats)
        avg_dur = round(sum(r.avg_duration_seconds for r in data.daily_stats) / len(data.daily_stats) / 60, 1) if data.daily_stats else 0
        tot_ord = sum(r.total_orders for r in data.daily_stats)
        tot_rev = sum(r.total_revenue for r in data.daily_stats)

        for r in data.daily_stats:
            rows.append([
                Paragraph(r.statistic_date.strftime("%d/%m/%Y"), S["tbl_cell_center"]),
                Paragraph(f"{r.total_visitors:,}", S["tbl_cell_center"]),
                Paragraph(f"{r.new_visitors:,}", S["tbl_cell_center"]),
                Paragraph(f"{r.returning_visitors:,}", S["tbl_cell_center"]),
                Paragraph(f"{round(r.avg_duration_seconds / 60, 1)} ph", S["tbl_cell_center"]),
                Paragraph(f"{r.total_orders:,}", S["tbl_cell_center"]),
                Paragraph(f"{r.total_revenue:,.0f} đ", S["tbl_cell_center"]),
            ])

        # Summary Row
        rows.append([
            Paragraph("TỔNG CỘNG", S["tbl_cell_bold"]),
            Paragraph(f"{tot_vis:,}", S["tbl_cell_bold"]),
            Paragraph(f"{tot_new:,}", S["tbl_cell_bold"]),
            Paragraph(f"{tot_ret:,}", S["tbl_cell_bold"]),
            Paragraph(f"{avg_dur} ph (TB)", S["tbl_cell_bold"]),
            Paragraph(f"{tot_ord:,}", S["tbl_cell_bold"]),
            Paragraph(f"{tot_rev:,.0f} đ", S["tbl_cell_bold"]),
        ])

        cw = [68, 62, 48, 56, 60, 56, 110]
        tbl_elems.append(_styled_table(rows, cw, hdr_color, has_total=True))
        elements.append(KeepTogether(tbl_elems))
        elements.append(Spacer(1, 3*mm))

    # ── Table: Customers ──────────────────────────────────────────────────────
    if data.customers and data.report_type in (ReportType.summary, ReportType.customer):
        tbl_elems = _section("Danh sách khách hàng tiêu biểu", S)
        hdrs = [
            Paragraph("Mã khách", S["tbl_hdr"]),
            Paragraph("Loại", S["tbl_hdr"]),
            Paragraph("Tên khách hàng", S["tbl_hdr"]),
            Paragraph("Lượt ghé", S["tbl_hdr"]),
            Paragraph("TB lưu trú", S["tbl_hdr"]),
            Paragraph("Chi tiêu (VNĐ)", S["tbl_hdr"]),
            Paragraph("Nhóm AI", S["tbl_hdr"]),
        ]
        rows = [hdrs]
        for c in data.customers:
            rows.append([
                Paragraph(c.anonymous_code, S["tbl_cell_center"]),
                Paragraph("Nhận diện" if c.person_type == "identified" else "Ẩn danh", S["tbl_cell_center"]),
                Paragraph(c.customer_name or "—", S["tbl_cell"]),
                Paragraph(f"{c.total_visits:,}", S["tbl_cell_center"]),
                Paragraph(f"{round(c.avg_duration_seconds / 60, 1)} ph", S["tbl_cell_center"]),
                Paragraph(f"{c.total_spent:,.0f} đ", S["tbl_cell_center"]),
                Paragraph((c.segment_name or "—")[:22], S["tbl_cell"]),
            ])
        cw = [68, 55, 85, 45, 58, 85, 64]
        tbl_elems.append(_styled_table(rows, cw, HEADER_COLORS[ReportType.customer]))
        elements.append(KeepTogether(tbl_elems))
        elements.append(Spacer(1, 3*mm))

    # ── Table: Segments ───────────────────────────────────────────────────────
    if data.segments and data.report_type in (ReportType.summary, ReportType.segment):
        tbl_elems = _section("Bảng chi tiết phân nhóm khách hàng AI", S)
        hdrs = [
            Paragraph("Tên nhóm AI", S["tbl_hdr"]),
            Paragraph("Số thành viên", S["tbl_hdr"]),
            Paragraph("TB lượt ghé", S["tbl_hdr"]),
            Paragraph("TB lưu trú", S["tbl_hdr"]),
            Paragraph("TB chi tiêu (VNĐ)", S["tbl_hdr"]),
        ]
        rows = [hdrs]
        for seg in data.segments:
            rows.append([
                Paragraph(seg.segment_name[:38], S["tbl_cell_bold"]),
                Paragraph(f"{seg.member_count:,}", S["tbl_cell_center"]),
                Paragraph(f"{seg.avg_visits:.1f}", S["tbl_cell_center"]),
                Paragraph(f"{round(seg.avg_duration_seconds / 60, 1)} ph", S["tbl_cell_center"]),
                Paragraph(f"{seg.avg_spent:,.0f} đ", S["tbl_cell_center"]),
            ])
        cw = [160, 70, 70, 75, 85]
        tbl_elems.append(_styled_table(rows, cw, HEADER_COLORS[ReportType.segment]))
        elements.append(KeepTogether(tbl_elems))
        elements.append(Spacer(1, 3*mm))

    # ── Table: Zones ──────────────────────────────────────────────────────────
    if data.zones and data.report_type in (ReportType.summary, ReportType.zone):
        tbl_elems = _section("Bảng chi tiết các vùng theo dõi", S)
        hdrs = [
            Paragraph("Tên vùng", S["tbl_hdr"]),
            Paragraph("Loại vùng", S["tbl_hdr"]),
            Paragraph("Tổng lượt ghé", S["tbl_hdr"]),
            Paragraph("TB lưu trú", S["tbl_hdr"]),
            Paragraph("Khung giờ đông nhất", S["tbl_hdr"]),
        ]
        rows = [hdrs]
        for z in data.zones:
            rows.append([
                Paragraph(z.zone_name, S["tbl_cell_bold"]),
                Paragraph(z.zone_type, S["tbl_cell_center"]),
                Paragraph(f"{z.total_visits:,}", S["tbl_cell_center"]),
                Paragraph(f"{round(z.avg_duration_seconds / 60, 1)} ph", S["tbl_cell_center"]),
                Paragraph(z.peak_hour or "—", S["tbl_cell_center"]),
            ])
        cw = [130, 70, 70, 75, 115]
        tbl_elems.append(_styled_table(rows, cw, HEADER_COLORS[ReportType.zone]))
        elements.append(KeepTogether(tbl_elems))
        elements.append(Spacer(1, 3*mm))

    # ── Table: Duration buckets ───────────────────────────────────────────────
    if data.duration_buckets and data.report_type in (ReportType.summary, ReportType.duration):
        tbl_elems = _section("Bảng phân phối thời gian lưu trú", S)
        hdrs = [
            Paragraph("Khoảng thời gian", S["tbl_hdr"]),
            Paragraph("Số lượt ghé", S["tbl_hdr"]),
            Paragraph("Tỷ lệ phân bố (%)", S["tbl_hdr"]),
        ]
        rows = [hdrs]
        for b in data.duration_buckets:
            rows.append([
                Paragraph(b.label, S["tbl_cell_bold"]),
                Paragraph(f"{b.count:,}", S["tbl_cell_center"]),
                Paragraph(f"{b.pct}%", S["tbl_cell_center"]),
            ])
        cw = [180, 140, 140]
        tbl_elems.append(_styled_table(rows, cw, HEADER_COLORS[ReportType.duration]))
        elements.append(KeepTogether(tbl_elems))

    # ── Build Document with NumberedCanvas ─────────────────────────────────────
    def canvas_factory(*args, **kwargs):
        return NumberedCanvas(
            *args,
            report_type=data.report_type,
            font=font,
            generated_at=now_str,
            start_date=data.start_date,
            end_date=data.end_date,
            **kwargs
        )

    doc.build(elements, canvasmaker=canvas_factory)
    output.seek(0)
    return output
