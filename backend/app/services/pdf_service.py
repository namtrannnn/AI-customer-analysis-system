import io
import os
from fastapi import HTTPException
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from app.schemas.report_schema import ReportDataDTO

def generate_pdf_report(data: ReportDataDTO) -> io.BytesIO:
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4)
    elements = []

    # 1. Xác định đường dẫn chính xác tới file font trong dự án
    current_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(current_dir, "..", "utils", "fonts", "times.ttf")

    # 2. Kiểm tra xem file font đã được copy vào chưa
    if not os.path.exists(font_path):
        raise HTTPException(
            status_code=500, 
            detail=f"Không tìm thấy file font tiếng Việt. Vui lòng copy file times.ttf vào thư mục: {os.path.abspath(font_path)}"
        )

    # 3. Đăng ký font
    pdfmetrics.registerFont(TTFont('Times New Roman', font_path))
    font_name = 'Times New Roman'

    # 4. Định dạng style sử dụng font Arial
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name='TitleStyle', fontName=font_name, fontSize=16, alignment=1, spaceAfter=10)
    normal_style = ParagraphStyle(name='NormalStyle', fontName=font_name, fontSize=12, alignment=1, spaceAfter=20)

    # Tiêu đề
    elements.append(Paragraph("BÁO CÁO HOẠT ĐỘNG TỔNG HỢP", title_style))
    elements.append(Paragraph(f"Từ ngày: {data.start_date.strftime('%d/%m/%Y')} - Đến ngày: {data.end_date.strftime('%d/%m/%Y')}", normal_style))
    elements.append(Spacer(1, 12))

    # Bảng Summary
    avg_stay_mins = round(data.summary.avg_duration_seconds / 60, 2)
    summary_data = [
        ['Tổng lượt khách', str(data.summary.total_visitors), 'Tổng đơn hàng', str(data.summary.total_orders)],
        ['Khách mới', str(data.summary.new_visitors), 'Tổng doanh thu', f"{data.summary.total_revenue:,.0f} VND"],
        ['Khách quay lại', str(data.summary.returning_visitors), 'TG lưu trú TB', f"{avg_stay_mins} phút"]
    ]
    
    summary_table = Table(summary_data, colWidths=[100, 100, 100, 150])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), font_name), # Ép dùng font tiếng Việt cho toàn bảng
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
        ('BACKGROUND', (2,0), (2,-1), colors.lightgrey),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # Bảng Chi tiết theo ngày
    daily_data = [["Ngày", "Lượt khách", "Khách mới", "Khách cũ", "TG lưu trú\n(phút)", "Số đơn", "Doanh thu (VND)"]]
    for row in data.daily_stats:
        daily_data.append([
            row.statistic_date.strftime('%d/%m/%Y'),
            str(row.total_visitors),
            str(row.new_visitors),
            str(row.returning_visitors),
            str(round(row.avg_duration_seconds / 60, 2)),
            str(row.total_orders),
            f"{row.total_revenue:,.0f}"
        ])

    daily_table = Table(daily_data, repeatRows=1)
    daily_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), font_name), # Ép dùng font tiếng Việt cho toàn bảng
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4F81BD')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
    ]))
    elements.append(daily_table)

    doc.build(elements)
    output.seek(0)
    return output