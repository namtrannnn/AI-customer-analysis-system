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
from app.schemas.report_schema import (
    ReportDataDTO, ReportSummary, DailyReportData,
    CustomerReportData, ReportType,
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


def get_report_data(
    db: Session,
    start_date: date,
    end_date: date,
    report_type: ReportType = ReportType.summary,
) -> ReportDataDTO:
    """
    Lấy dữ liệu báo cáo theo loại:
    - summary:  tất cả chỉ số + danh sách khách
    - activity: chỉ số lượt khách & thời gian
    - customer: danh sách khách hàng
    - revenue:  chỉ số đơn hàng & doanh thu
    """
    daily_list: list[DailyReportData] = []
    customers:  list[CustomerReportData] = []

    # ── Lấy daily stats (dùng cho summary, activity, revenue) ────────────────
    if report_type in (ReportType.summary, ReportType.activity, ReportType.revenue):
        daily_list = _get_daily_stats(db, start_date, end_date)

    # ── Lấy danh sách khách (dùng cho summary, customer) ─────────────────────
    if report_type in (ReportType.summary, ReportType.customer):
        customers = _get_customers(db, start_date, end_date)

    # ── Validate: không có data nào cả ───────────────────────────────────────
    if not daily_list and not customers:
        raise HTTPException(
            status_code=404,
            detail="Không có dữ liệu trong khoảng thời gian đã chọn. Vui lòng chọn khoảng ngày khác hoặc đồng bộ dữ liệu trước.",
        )

    summary = _build_summary(daily_list)

    # Với loại revenue: chỉ giữ lại chỉ số đơn hàng & doanh thu trong summary
    # (total_visitors vẫn hiển thị để tính tỷ lệ chuyển đổi)

    return ReportDataDTO(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        summary=summary,
        daily_stats=daily_list,
        customers=customers,
    )
