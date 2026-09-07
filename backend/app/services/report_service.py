from sqlalchemy.orm import Session
from datetime import date
from fastapi import HTTPException
from app.models.daily_statistic import DailyStatistic
from app.schemas.report_schema import ReportDataDTO, ReportSummary, DailyReportData

def get_report_data(db: Session, start_date: date, end_date: date) -> ReportDataDTO:
    # Truy vấn bảng daily_statistics
    stats = db.query(DailyStatistic).filter(
        DailyStatistic.statistic_date >= start_date,
        DailyStatistic.statistic_date <= end_date
    ).order_by(DailyStatistic.statistic_date.asc()).all()

    if not stats:
        raise HTTPException(status_code=404, detail="Không có dữ liệu trong khoảng thời gian này.")

    summary = ReportSummary()
    daily_list = []
    total_duration = 0

    for stat in stats:
        daily_dto = DailyReportData(
            statistic_date=stat.statistic_date,
            total_visitors=stat.total_visitors,
            new_visitors=stat.new_visitors,
            returning_visitors=stat.returning_visitors,
            avg_duration_seconds=stat.avg_duration_seconds,
            total_orders=stat.total_orders,
            total_revenue=float(stat.total_revenue)
        )
        daily_list.append(daily_dto)

        # Cộng dồn chỉ số summary
        summary.total_visitors += stat.total_visitors
        summary.new_visitors += stat.new_visitors
        summary.returning_visitors += stat.returning_visitors
        summary.total_orders += stat.total_orders
        summary.total_revenue += float(stat.total_revenue)
        total_duration += stat.avg_duration_seconds

    # Tính trung bình thời gian lưu trú (giây) cho toàn kỳ
    if len(stats) > 0:
        summary.avg_duration_seconds = int(total_duration / len(stats))

    return ReportDataDTO(
        start_date=start_date,
        end_date=end_date,
        summary=summary,
        daily_stats=daily_list
    )