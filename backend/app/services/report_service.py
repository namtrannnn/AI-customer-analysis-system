from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from fastapi import HTTPException

from app.models.daily_statistic import DailyStatistic
from app.models.person_profile import PersonProfile
from app.models.visit_sessions import VisitSession
from app.models.customer_segment_member import CustomerSegmentMember
from app.models.customer_segment import CustomerSegment
from app.models.customer_identity import CustomerIdentity
from app.models.customer import Customer
from app.models.order import Order
from app.models.zone_visit import ZoneVisit
from app.models.store_zone import StoreZone
from app.schemas.report_schema import (
    ReportDataDTO, ReportSummary, DailyReportData,
    CustomerReportData, ReportType,
    SegmentReportData, ZoneReportData, DurationBucketData,
)


def _get_daily_stats(db: Session, start_date: date, end_date: date) -> list[DailyReportData]:
    """Lấy thống kê theo ngày từ daily_statistics."""
    stats = db.query(DailyStatistic).filter(
        DailyStatistic.statistic_date >= start_date,
        DailyStatistic.statistic_date <= end_date,
    ).order_by(DailyStatistic.statistic_date.asc()).all()

    return [
        DailyReportData(
            statistic_date=s.statistic_date,
            total_visitors=s.total_visitors,
            new_visitors=s.new_visitors,
            returning_visitors=s.returning_visitors,
            avg_duration_seconds=s.avg_duration_seconds or 0,
            total_orders=s.total_orders or 0,
            total_revenue=float(s.total_revenue or 0),
        )
        for s in stats
    ]


def _build_summary(daily_list: list[DailyReportData]) -> ReportSummary:
    """Tính tổng hợp từ danh sách daily stats."""
    if not daily_list:
        return ReportSummary()

    summary = ReportSummary()
    total_duration = 0

    for d in daily_list:
        summary.total_visitors   += d.total_visitors
        summary.new_visitors     += d.new_visitors
        summary.returning_visitors += d.returning_visitors
        summary.total_orders     += d.total_orders
        summary.total_revenue    += d.total_revenue
        total_duration           += d.avg_duration_seconds

    summary.avg_duration_seconds = int(total_duration / len(daily_list))
    return summary


def _get_customers(db: Session, start_date: date, end_date: date) -> list[CustomerReportData]:
    """Lấy danh sách person profiles có visit trong khoảng ngày."""
    # Subquery: avg duration mỗi profile trong kỳ
    duration_sq = (
        db.query(
            VisitSession.person_profile_id,
            func.avg(VisitSession.duration_seconds).label("avg_dur"),
            func.count(VisitSession.id).label("visit_count"),
        )
        .filter(
            VisitSession.entry_time >= start_date,
            VisitSession.entry_time <= end_date,
        )
        .group_by(VisitSession.person_profile_id)
        .subquery()
    )

    # Subquery: total spent mỗi profile trong kỳ
    spent_sq = (
        db.query(
            Order.person_profile_id,
            func.sum(Order.total_amount).label("total_spent"),
        )
        .filter(
            Order.created_at >= start_date,
            Order.created_at <= end_date,
        )
        .group_by(Order.person_profile_id)
        .subquery()
    )

    rows = (
        db.query(
            PersonProfile,
            duration_sq.c.avg_dur,
            duration_sq.c.visit_count,
            spent_sq.c.total_spent,
            Customer.full_name,
            CustomerSegment.segment_name,
        )
        .join(duration_sq, duration_sq.c.person_profile_id == PersonProfile.id)
        .outerjoin(spent_sq, spent_sq.c.person_profile_id == PersonProfile.id)
        .outerjoin(CustomerIdentity, CustomerIdentity.person_profile_id == PersonProfile.id)
        .outerjoin(Customer, Customer.id == CustomerIdentity.customer_id)
        .outerjoin(CustomerSegmentMember, CustomerSegmentMember.person_profile_id == PersonProfile.id)
        .outerjoin(CustomerSegment, CustomerSegment.id == CustomerSegmentMember.segment_id)
        .order_by(duration_sq.c.visit_count.desc())
        .all()
    )

    return [
        CustomerReportData(
            anonymous_code=p.anonymous_code,
            person_type=p.person_type,
            customer_name=full_name,
            total_visits=int(visit_count or 0),
            avg_duration_seconds=int(avg_dur or 0),
            total_spent=float(total_spent or 0),
            segment_name=segment_name,
        )
        for p, avg_dur, visit_count, total_spent, full_name, segment_name in rows
    ]


def _get_segments(db: Session) -> list[SegmentReportData]:
    """Lấy thống kê phân nhóm AI từ customer_segments."""
    segments = db.query(CustomerSegment).all()
    result = []
    for seg in segments:
        rule = seg.rule_definition or {}
        stats = rule.get("statistics") or {}
        result.append(SegmentReportData(
            segment_name=seg.segment_name,
            member_count=int(stats.get("member_count") or 0),
            avg_visits=float(stats.get("avg_visits") or 0),
            avg_duration_seconds=int(float(stats.get("avg_duration") or 0)),
            avg_spent=float(stats.get("avg_spent") or 0),
        ))
    return [s for s in result if s.member_count > 0]


def _get_zones(db: Session, start_date: date, end_date: date) -> list[ZoneReportData]:
    """Lấy thống kê lượt ghé và thời gian theo từng zone."""
    from sqlalchemy import extract
    zones = db.query(StoreZone).all()
    result = []
    for zone in zones:
        visits = db.query(ZoneVisit).filter(
            ZoneVisit.zone_id == zone.id,
            ZoneVisit.enter_time >= start_date,
            ZoneVisit.enter_time <= end_date,
        ).all()
        if not visits:
            continue
        total_visits = len(visits)
        avg_dur = int(
            sum(v.duration_seconds or 0 for v in visits) / total_visits
        ) if total_visits else 0
        # Tìm giờ đông nhất
        hour_counts: dict[int, int] = {}
        for v in visits:
            h = v.enter_time.hour
            hour_counts[h] = hour_counts.get(h, 0) + 1
        peak_h = max(hour_counts, key=lambda h: hour_counts[h]) if hour_counts else None
        peak_str = f"{peak_h:02d}:00 - {peak_h:02d}:59" if peak_h is not None else None
        result.append(ZoneReportData(
            zone_name=zone.zone_name,
            zone_type=zone.zone_type,
            color=zone.color,
            total_visits=total_visits,
            avg_duration_seconds=avg_dur,
            peak_hour=peak_str,
        ))
    return sorted(result, key=lambda z: z.total_visits, reverse=True)


def _get_duration_buckets(db: Session, start_date: date, end_date: date) -> list[DurationBucketData]:
    """Phân phối thời gian lưu trú vào các bucket."""
    sessions = db.query(VisitSession).filter(
        VisitSession.entry_time >= start_date,
        VisitSession.entry_time <= end_date,
        VisitSession.duration_seconds.isnot(None),
        VisitSession.duration_seconds > 0,
    ).all()

    if not sessions:
        return []

    buckets = [
        ("< 5 phút",      0,    300),
        ("5 - 15 phút",   300,  900),
        ("15 - 30 phút",  900,  1800),
        ("30 - 60 phút",  1800, 3600),
        ("> 60 phút",     3600, 999999),
    ]
    total = len(sessions)
    result = []
    for label, lo, hi in buckets:
        count = sum(1 for s in sessions if lo <= (s.duration_seconds or 0) < hi)
        result.append(DurationBucketData(
            label=label,
            count=count,
            pct=round(count / total * 100, 1) if total else 0,
        ))
    return result


def get_report_data(
    db: Session,
    start_date: date,
    end_date: date,
    report_type: ReportType = ReportType.summary,
) -> ReportDataDTO:
    daily_list:       list[DailyReportData]    = []
    customers:        list[CustomerReportData] = []
    segments:         list[SegmentReportData]  = []
    zones:            list[ZoneReportData]     = []
    duration_buckets: list[DurationBucketData] = []

    if report_type in (ReportType.summary, ReportType.activity, ReportType.revenue):
        daily_list = _get_daily_stats(db, start_date, end_date)

    if report_type in (ReportType.summary, ReportType.customer):
        customers = _get_customers(db, start_date, end_date)

    if report_type in (ReportType.summary, ReportType.segment):
        segments = _get_segments(db)

    if report_type in (ReportType.summary, ReportType.zone):
        zones = _get_zones(db, start_date, end_date)

    if report_type in (ReportType.summary, ReportType.duration):
        duration_buckets = _get_duration_buckets(db, start_date, end_date)

    # Validate — ít nhất phải có 1 trong các list
    has_data = any([daily_list, customers, segments, zones, duration_buckets])
    if not has_data:
        raise HTTPException(
            status_code=404,
            detail="Không có dữ liệu trong khoảng thời gian đã chọn. Vui lòng chọn khoảng ngày khác hoặc đồng bộ dữ liệu trước.",
        )

    summary = _build_summary(daily_list)

    return ReportDataDTO(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        summary=summary,
        daily_stats=daily_list,
        customers=customers,
        segments=segments,
        zones=zones,
        duration_buckets=duration_buckets,
    )
