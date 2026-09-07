from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import date
from urllib.parse import quote
from app.database.session import get_db
from app.core.dependencies import RequirePermission, get_current_user
from app.services.report_service import get_report_data
from app.services.excel_service import generate_excel_report
from app.services.pdf_service import generate_pdf_report

router = APIRouter(prefix="/api/reports", tags=["Reports"])

@router.get("/export/excel")
def export_excel(
    start_date: date = Query(..., description="YYYY-MM-DD"),
    end_date: date = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user = Depends(RequirePermission("report.view"))
):
    # validate roles here nếu cần
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Ngày bắt đầu không hợp lệ.")

    report_data = get_report_data(db, start_date, end_date)
    file_stream = generate_excel_report(report_data)
    
    filename = f"store_report_{start_date}_{end_date}.xlsx"
    
    return StreamingResponse(
        file_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{quote(filename)}"}
    )

@router.get("/export/pdf")
def export_pdf(
    start_date: date = Query(..., description="YYYY-MM-DD"),
    end_date: date = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user = Depends(RequirePermission("report.view"))
):
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Ngày bắt đầu không hợp lệ.")

    report_data = get_report_data(db, start_date, end_date)
    file_stream = generate_pdf_report(report_data)
    
    filename = f"store_report_{start_date}_{end_date}.pdf"
    
    return StreamingResponse(
        file_stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{quote(filename)}"}
    )