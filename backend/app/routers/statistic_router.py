from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, extract
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date, timedelta

from app.database.session import get_db
from app.models.daily_statistic import DailyStatistic
from app.schemas.daily_statistic import OverviewStatsResponse, TrendChartResponse, ChartDataPoint
from app.core.dependencies import get_admin_user

router = APIRouter(prefix="/api/statistics", tags=["Dashboard Statistics"])

# BE-2: API Thống kê tổng quan (Cards)
@router.get("/overview", response_model=OverviewStatsResponse)
def get_overview_statistics(
    start_date: Optional[date] = Query(None, description="Mặc định lấy 30 ngày qua"),
    end_date: Optional[date] = Query(None, description="Mặc định là hôm nay"),
    db: Session = Depends(get_db),
    admin_user = Depends(get_admin_user)
):
    if not end_date: end_date = date.today()
    if not start_date: start_date = end_date - timedelta(days=30)

    result = db.query(
        func.sum(DailyStatistic.total_visitors).label("sum_visitors"),
        func.sum(DailyStatistic.new_visitors).label("sum_new"),
        func.sum(DailyStatistic.returning_visitors).label("sum_returning"),
        func.avg(DailyStatistic.avg_duration_seconds).label("overall_avg_duration")
    ).filter(
        DailyStatistic.statistic_date >= start_date,
        DailyStatistic.statistic_date <= end_date
    ).first()

    return OverviewStatsResponse(
        total_visits=result.sum_visitors or 0, # Sẽ map với schema total_visits
        new_visitors=result.sum_new or 0,
        returning_visitors=result.sum_returning or 0,
        avg_duration_seconds=float(result.overall_avg_duration or 0.0)
    )

# BE-3: API Biểu đồ xu hướng (Trend Chart)
@router.get("/trend", response_model=TrendChartResponse)
def get_trend_chart(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    group_by: str = Query("day", description="Nhóm theo: day, month"),
    db: Session = Depends(get_db),
    admin_user = Depends(get_admin_user)
):
    if not end_date: end_date = date.today()
    if not start_date: start_date = end_date - timedelta(days=30)

    query = db.query(DailyStatistic).filter(
        DailyStatistic.statistic_date >= start_date,
        DailyStatistic.statistic_date <= end_date
    )

    data_points = []
    
    if group_by == "day":
        records = query.order_by(DailyStatistic.statistic_date.asc()).all()
        for r in records:
            data_points.append(ChartDataPoint(
                label=r.statistic_date.strftime("%Y-%m-%d"),
                total_visits=r.total_visitors,
                new_visitors=r.new_visitors,
                returning_visitors=r.returning_visitors
            ))
            
    elif group_by == "month":
        grouped_records = db.query(
            extract('year', DailyStatistic.statistic_date).label('year'),
            extract('month', DailyStatistic.statistic_date).label('month'),
            func.sum(DailyStatistic.total_visitors).label("visits"),
            func.sum(DailyStatistic.new_visitors).label("new_v"),
            func.sum(DailyStatistic.returning_visitors).label("ret_v")
        ).filter(
            DailyStatistic.statistic_date >= start_date,
            DailyStatistic.statistic_date <= end_date
        ).group_by('year', 'month').order_by('year', 'month').all()

        for r in grouped_records:
            data_points.append(ChartDataPoint(
                label=f"{int(r.month):02d}/{int(r.year)}",
                total_visits=r.visits or 0,
                new_visitors=r.new_v or 0,
                returning_visitors=r.ret_v or 0
            ))

    return TrendChartResponse(group_by=group_by, data=data_points)