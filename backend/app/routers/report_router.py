from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import date
from urllib.parse import quote

from app.database.session import get_db
from app.core.dependencies import RequirePermission
from app.schemas.report_schema import ReportType
from app.services.report_service import get_report_data
from app.services.excel_service import generate_excel_report
from app.services.pdf_service import generate_pdf_report

router = APIRouter(prefix="/api/reports", tags=["Reports"])


def _validate_dates(start_date: date, end_date: date) -> None:
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Ngày bắt đầu không được sau ngày kết thúc.")
    diff = (end_date - start_date).days
    if diff > 365:
        raise HTTPException(status_code=400, detail="Khoảng thời gian không được vượt quá 365 ngày.")


@router.get("/export/excel")
def export_excel(
    start_date: date = Query(..., description="YYYY-MM-DD"),
    end_date:   date = Query(..., description="YYYY-MM-DD"),
    report_type: ReportType = Query(default=ReportType.summary, description="Loại báo cáo"),
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("report.view")),
):
    """
    Xuất báo cáo Excel theo loại:
    - summary:  Tổng hợp (mặc định)
    - activity: Hoạt động khách hàng
    - customer: Danh sách khách hàng
    - revenue:  Doanh thu & đơn hàng
    """
    _validate_dates(start_date, end_date)
    report_data = get_report_data(db, start_date, end_date, report_type)
    file_stream = generate_excel_report(report_data)

    filename = f"store_report_{report_type.value}_{start_date}_{end_date}.xlsx"
    return StreamingResponse(
        file_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{quote(filename)}"},
    )


@router.get("/export/pdf")
def export_pdf(
    start_date: date = Query(..., description="YYYY-MM-DD"),
    end_date:   date = Query(..., description="YYYY-MM-DD"),
    report_type: ReportType = Query(default=ReportType.summary, description="Loại báo cáo"),
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("report.view")),
):
    """
    Xuất báo cáo PDF theo loại:
    - summary:  Tổng hợp (mặc định)
    - activity: Hoạt động khách hàng
    - customer: Danh sách khách hàng
    - revenue:  Doanh thu & đơn hàng
    """
    _validate_dates(start_date, end_date)
    report_data = get_report_data(db, start_date, end_date, report_type)
    file_stream = generate_pdf_report(report_data)

    filename = f"store_report_{report_type.value}_{start_date}_{end_date}.pdf"
    return StreamingResponse(
        file_stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{quote(filename)}"},
    )
