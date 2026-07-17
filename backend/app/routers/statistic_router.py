from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, extract
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date, timedelta

from app.database.session import get_db
from app.models.daily_statistic import DailyStatistic
from app.models.store_zone import StoreZone
from app.models.zone_visit import ZoneVisit
from app.schemas.daily_statistic import (
    OverviewStatsResponse,
    TrendChartResponse,
    ChartDataPoint,
    ZoneVisitStatResponse,
)
from app.schemas.response_schema import StandardResponse
from app.core.dependencies import get_admin_user
from app.utils.response import success_response

router = APIRouter(prefix="/api/statistics", tags=["Dashboard Statistics"])

# BE-2: API Thống kê tổng quan (Cards)
@router.get("/overview", response_model=StandardResponse[OverviewStatsResponse])
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

    overview = OverviewStatsResponse(
        total_visits=result.sum_visitors or 0, # Sẽ map với schema total_visits
        new_visitors=result.sum_new or 0,
        returning_visitors=result.sum_returning or 0,
        avg_duration_seconds=float(result.overall_avg_duration or 0.0)
    )
    return success_response(data=overview, message="Lay thong ke tong quan thanh cong")

# BE-3: API Biểu đồ xu hướng (Trend Chart)
@router.get("/trend", response_model=StandardResponse[TrendChartResponse])
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

    trend = TrendChartResponse(group_by=group_by, data=data_points)
    return success_response(data=trend, message="Lay du lieu xu huong thanh cong")


@router.get("/zone-visits", response_model=StandardResponse[List[ZoneVisitStatResponse]])
def get_zone_visit_statistics(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    admin_user=Depends(get_admin_user),
):
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    rows = (
        db.query(
            StoreZone.zone_name.label("zone"),
            StoreZone.color.label("color"),
            func.count(ZoneVisit.id).label("visits"),
        )
        .join(ZoneVisit, ZoneVisit.zone_id == StoreZone.id)
        .filter(func.date(ZoneVisit.enter_time) >= start_date)
        .filter(func.date(ZoneVisit.enter_time) <= end_date)
        .group_by(StoreZone.id, StoreZone.zone_name, StoreZone.color)
        .order_by(func.count(ZoneVisit.id).desc())
        .all()
    )

    data = [
        ZoneVisitStatResponse(
            zone=row.zone,
            visits=int(row.visits or 0),
            color=row.color or "#6366f1",
        )
        for row in rows
    ]
    return success_response(data=data, message="Lay thong ke luot tham theo vung thanh cong")
