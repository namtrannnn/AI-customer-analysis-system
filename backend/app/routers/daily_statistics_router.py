# Router cho phần Thống kê khách theo ngày (PB06)
# Endpoints: Lấy danh sách, KPI tổng hợp, đồng bộ dữ liệu, export CSV

import csv
import io
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, cast, Date, case, distinct
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.daily_statistic import DailyStatistic
from app.models.visit_sessions import VisitSession
from app.models.person_profile import PersonProfile
from app.models.order import Order
from app.schemas.response_schema import StandardResponse
from app.schemas.daily_statistics_schema import (
    DailyStatisticResponse,
    DailyStatisticsSummary,
    DailyTrendItem,
    SyncStatsRequest,
)

router = APIRouter(prefix="/api/statistics", tags=["Daily Statistics"])


# ────────────────────────────────────────────────────────
# Hàm core: Tính toán số liệu của MỘT ngày cụ thể
# ────────────────────────────────────────────────────────
def _compute_stats_for_date(db: Session, target_date: date) -> dict:
    """
    Tính toán tất cả chỉ số thống kê cho một ngày cụ thể:
    - total_visitors: Số person_profile_id duy nhất (unique) có lượt ghé thăm trong ngày
    - new_visitors: Khách có lượt ghé thăm ĐẦU TIÊN từ trước đến nay nằm trong ngày này
    - returning_visitors: total_visitors - new_visitors
    - identified_visitors: Khách đã được định danh (is_identified = True)
    - avg_duration_seconds: Thời gian ở lại trung bình
    - total_orders / total_revenue: Tổng đơn hàng và doanh thu
    - conversion_rate: (Số khách có đơn hàng / Tổng khách) * 100
    """
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = datetime.combine(target_date, datetime.max.time())

    # === 1. Lấy tất cả visit_sessions trong ngày ===
    sessions = (
        db.query(VisitSession)
        .filter(VisitSession.entry_time >= day_start)
        .filter(VisitSession.entry_time <= day_end)
        .all()
    )

    # Danh sách person_profile_id duy nhất ghé thăm trong ngày
    visitor_ids = set(s.person_profile_id for s in sessions)
    total_visitors = len(visitor_ids)

    # === 2. Xác định khách mới (New) vs khách quay lại (Returning) ===
    new_count = 0
    identified_count = 0
    for pid in visitor_ids:
        # Kiểm tra xem person_profile này có lượt ghé thăm nào TRƯỚC ngày target_date không
        earlier_visit = (
            db.query(VisitSession.id)
            .filter(VisitSession.person_profile_id == pid)
            .filter(VisitSession.entry_time < day_start)
            .limit(1)
            .first()
        )
        if earlier_visit is None:
            new_count += 1

        # Kiểm tra đã định danh chưa (bất kỳ session nào trong ngày)
        identified_session = next(
            (s for s in sessions if s.person_profile_id == pid and s.is_identified),
            None,
        )
        if identified_session:
            identified_count += 1

    returning_count = total_visitors - new_count

    # === 3. Tính thời gian ở lại trung bình ===
    durations = [s.duration_seconds for s in sessions if s.duration_seconds is not None]
    avg_duration = int(sum(durations) / len(durations)) if durations else 0

    # === 4. Tính tổng đơn hàng và doanh thu ===
    orders = (
        db.query(Order)
        .filter(Order.order_time >= day_start)
        .filter(Order.order_time <= day_end)
        .all()
    )
    total_orders = len(orders)
    total_revenue = float(sum(o.total_amount for o in orders))

    # === 5. Tỷ lệ chuyển đổi ===
    conversion_rate = 0.0
    if total_visitors > 0:
        # Đếm số person_profile_id có đơn hàng trong ngày
        order_person_ids = set()
        for o in orders:
            if o.person_profile_id:
                order_person_ids.add(o.person_profile_id)
        buyers = len(order_person_ids & visitor_ids)
        conversion_rate = round((buyers / total_visitors) * 100, 2)

    return {
        "statistic_date": target_date,
        "total_visitors": total_visitors,
        "new_visitors": new_count,
        "returning_visitors": returning_count,
        "identified_visitors": identified_count,
        "avg_duration_seconds": avg_duration,
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "conversion_rate": conversion_rate,
    }


def _sync_date(db: Session, target_date: date) -> DailyStatistic:
    """
    Tính toán và ghi đè (upsert) số liệu của một ngày vào bảng daily_statistics.
    """
    stats = _compute_stats_for_date(db, target_date)

    # Tìm bản ghi hiện tại (nếu có) → cập nhật, nếu chưa có → tạo mới
    existing = db.query(DailyStatistic).filter(
        DailyStatistic.statistic_date == target_date
    ).first()

    if existing:
        for key, value in stats.items():
            if key != "statistic_date":
                setattr(existing, key, value)
        record = existing
    else:
        record = DailyStatistic(**stats)
        db.add(record)

    db.commit()
    db.refresh(record)
    return record


# ────────────────────────────────────────────────────────
# API Endpoints
# ────────────────────────────────────────────────────────

@router.get("/daily", response_model=StandardResponse[List[DailyStatisticResponse]])
def get_daily_statistics(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """
    Lấy danh sách thống kê chi tiết theo từng ngày, hỗ trợ phân trang và lọc khoảng ngày.
    """
    query = db.query(DailyStatistic)

    if start_date:
        try:
            query = query.filter(
                DailyStatistic.statistic_date >= datetime.strptime(start_date, "%Y-%m-%d").date()
            )
        except ValueError:
            pass

    if end_date:
        try:
            query = query.filter(
                DailyStatistic.statistic_date <= datetime.strptime(end_date, "%Y-%m-%d").date()
            )
        except ValueError:
            pass

    total = query.count()
    records = (
        query.order_by(DailyStatistic.statistic_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    data = [
        DailyStatisticResponse(
            id=r.id,
            statistic_date=r.statistic_date,
            total_visitors=r.total_visitors,
            new_visitors=r.new_visitors,
            returning_visitors=r.returning_visitors,
            identified_visitors=r.identified_visitors,
            avg_duration_seconds=r.avg_duration_seconds,
            total_orders=r.total_orders,
            total_revenue=float(r.total_revenue),
            conversion_rate=float(r.conversion_rate),
        )
        for r in records
    ]

    return StandardResponse(
        status="success",
        message="Lấy danh sách thống kê thành công",
        data=data,
        meta={"total": total, "skip": skip, "limit": limit},
    )


@router.get("/summary", response_model=StandardResponse[DailyStatisticsSummary])
def get_statistics_summary(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    group_by: str = Query("day", description="Nhóm dữ liệu: day | week | month"),
    db: Session = Depends(get_db),
):
    """
    Lấy tổng hợp KPIs + dữ liệu xu hướng cho biểu đồ.
    group_by: day = theo ngày, week = theo tuần, month = theo tháng
    """
    query = db.query(DailyStatistic)

    if start_date:
        try:
            query = query.filter(
                DailyStatistic.statistic_date >= datetime.strptime(start_date, "%Y-%m-%d").date()
            )
        except ValueError:
            pass

    if end_date:
        try:
            query = query.filter(
                DailyStatistic.statistic_date <= datetime.strptime(end_date, "%Y-%m-%d").date()
            )
        except ValueError:
            pass

    records = query.order_by(DailyStatistic.statistic_date.asc()).all()

    # Tính KPIs tổng hợp
    sum_visitors = sum(r.total_visitors for r in records)
    sum_new = sum(r.new_visitors for r in records)
    sum_returning = sum(r.returning_visitors for r in records)
    sum_orders = sum(r.total_orders for r in records)
    sum_revenue = sum(float(r.total_revenue) for r in records)

    durations = [r.avg_duration_seconds for r in records if r.avg_duration_seconds > 0]
    avg_dur = int(sum(durations) / len(durations)) if durations else 0

    conv_rates = [float(r.conversion_rate) for r in records if r.total_visitors > 0]
    avg_conv = round(sum(conv_rates) / len(conv_rates), 2) if conv_rates else 0.0

    # Nhóm dữ liệu xu hướng theo day / week / month
    trend_map: dict[str, dict] = {}
    for r in records:
        if group_by == "week":
            # Lấy tuần ISO: "2026-W28"
            iso = r.statistic_date.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
        elif group_by == "month":
            key = r.statistic_date.strftime("%Y-%m")
        else:
            key = r.statistic_date.strftime("%Y-%m-%d")

        if key not in trend_map:
            trend_map[key] = {
                "total_visitors": 0,
                "new_visitors": 0,
                "returning_visitors": 0,
                "duration_sum": 0,
                "duration_count": 0,
            }

        trend_map[key]["total_visitors"] += r.total_visitors
        trend_map[key]["new_visitors"] += r.new_visitors
        trend_map[key]["returning_visitors"] += r.returning_visitors
        if r.avg_duration_seconds > 0:
            trend_map[key]["duration_sum"] += r.avg_duration_seconds
            trend_map[key]["duration_count"] += 1

    trend = []
    for key in sorted(trend_map.keys()):
        t = trend_map[key]
        avg_d = int(t["duration_sum"] / t["duration_count"]) if t["duration_count"] > 0 else 0
        trend.append(
            DailyTrendItem(
                date=key,
                total_visitors=t["total_visitors"],
                new_visitors=t["new_visitors"],
                returning_visitors=t["returning_visitors"],
                avg_duration_seconds=avg_d,
            )
        )

    data = DailyStatisticsSummary(
        total_visitors=sum_visitors,
        new_visitors=sum_new,
        returning_visitors=sum_returning,
        avg_duration_seconds=avg_dur,
        total_orders=sum_orders,
        total_revenue=round(sum_revenue, 2),
        avg_conversion_rate=avg_conv,
        trend=trend,
    )

    return StandardResponse(
        status="success",
        message="Lấy tổng hợp thống kê thành công",
        data=data,
    )


@router.post("/sync", response_model=StandardResponse[dict])
def sync_statistics(
    body: SyncStatsRequest,
    db: Session = Depends(get_db),
):
    """
    Kích hoạt tính toán lại dữ liệu thống kê cho khoảng ngày chỉ định.
    Ghi đè (upsert) vào bảng daily_statistics.
    """
    if body.end_date < body.start_date:
        raise HTTPException(status_code=400, detail="end_date phải >= start_date")

    delta = (body.end_date - body.start_date).days
    if delta > 365:
        raise HTTPException(status_code=400, detail="Khoảng thời gian tối đa là 365 ngày")

    synced_dates = []
    current = body.start_date
    while current <= body.end_date:
        _sync_date(db, current)
        synced_dates.append(current.isoformat())
        current += timedelta(days=1)

    return StandardResponse(
        status="success",
        message=f"Đồng bộ thành công {len(synced_dates)} ngày",
        data={"synced_count": len(synced_dates), "dates": synced_dates},
    )


@router.get("/export")
def export_statistics_csv(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    Xuất dữ liệu thống kê ra file CSV để tải về.
    """
    query = db.query(DailyStatistic)

    if start_date:
        try:
            query = query.filter(
                DailyStatistic.statistic_date >= datetime.strptime(start_date, "%Y-%m-%d").date()
            )
        except ValueError:
            pass

    if end_date:
        try:
            query = query.filter(
                DailyStatistic.statistic_date <= datetime.strptime(end_date, "%Y-%m-%d").date()
            )
        except ValueError:
            pass

    records = query.order_by(DailyStatistic.statistic_date.asc()).all()

    # Tạo nội dung CSV trong bộ nhớ
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Ngày", "Tổng khách", "Khách mới", "Khách quay lại",
        "Đã định danh", "TB thời gian (giây)",
        "Đơn hàng", "Doanh thu", "Tỷ lệ chuyển đổi (%)"
    ])

    # Data rows
    for r in records:
        writer.writerow([
            r.statistic_date.isoformat(),
            r.total_visitors,
            r.new_visitors,
            r.returning_visitors,
            r.identified_visitors,
            r.avg_duration_seconds,
            r.total_orders,
            float(r.total_revenue),
            float(r.conversion_rate),
        ])

    output.seek(0)

    filename = f"thong_ke_khach_{start_date or 'all'}_{end_date or 'all'}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
