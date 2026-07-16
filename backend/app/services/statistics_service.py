from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from app.models.daily_statistic import DailyStatistic
from app.models.visit_sessions import VisitSession
from app.models.person_profile import PersonProfile
from app.models.order import Order

class DailyStatisticsService:
    def __init__(self, db: Session):
        self.db = db

    def aggregate_daily_stats(self, target_date: date = None):
        """
        BE-4: Tính toán và lưu trữ dữ liệu của một ngày cụ thể.
        Mặc định lấy ngày hôm qua nếu không truyền tham số.
        """
        if target_date is None:
            target_date = date.today() - timedelta(days=1)

        try:
            # 1. Thống kê lượt truy cập và thời gian trung bình từ visit_sessions
            session_stats = self.db.query(
                func.count(func.distinct(VisitSession.person_profile_id)).label("total_visitors"),
                func.avg(VisitSession.duration_seconds).label("avg_duration")
            ).filter(
                func.date(VisitSession.entry_time) == target_date
            ).first()

            total_visitors = session_stats.total_visitors or 0
            avg_duration = int(session_stats.avg_duration or 0)

            # 2. Khách mới (phát hiện lần đầu trong ngày)
            new_visitors = self.db.query(func.count(PersonProfile.id)).filter(
                func.date(PersonProfile.first_seen_at) == target_date
            ).scalar() or 0

            # 3. Khách quay lại (Khách cũ)
            returning_visitors = total_visitors - new_visitors
            if returning_visitors < 0: 
                returning_visitors = 0

            # 4. Khách đã định danh (Có liên kết với tài khoản customer)
            # Giả sử bảng VisitSession có liên kết hoặc join để check customer_id
            identified_visitors = self.db.query(
                func.count(func.distinct(VisitSession.person_profile_id))
            ).filter(
                func.date(VisitSession.entry_time) == target_date,
                VisitSession.customer_id.isnot(None) # Lọc những phiên đã định danh
            ).scalar() or 0

            # 5. Thống kê đơn hàng và doanh thu trong ngày từ bảng orders
            order_stats = self.db.query(
                func.count(Order.id).label("total_orders"),
                func.sum(Order.total_amount).label("total_revenue")
            ).filter(
                func.date(Order.created_at) == target_date
            ).first()

            total_orders = order_stats.total_orders or 0
            total_revenue = float(order_stats.total_revenue or 0.0)

            # 6. Tính tỷ lệ chuyển đổi (Conversion Rate)
            conversion_rate = 0.0
            if total_visitors > 0:
                conversion_rate = float(total_orders / total_visitors)

            # 7. Tiến hành lưu hoặc cập nhật (Upsert) vào bảng daily_statistics
            stat_record = self.db.query(DailyStatistic).filter(
                DailyStatistic.statistic_date == target_date
            ).first()

            if not stat_record:
                stat_record = DailyStatistic(statistic_date=target_date)
                self.db.add(stat_record)
            
            stat_record.total_visitors = total_visitors
            stat_record.new_visitors = new_visitors
            stat_record.returning_visitors = returning_visitors
            stat_record.identified_visitors = identified_visitors
            stat_record.avg_duration_seconds = avg_duration
            stat_record.total_orders = total_orders
            stat_record.total_revenue = total_revenue
            stat_record.conversion_rate = conversion_rate
            
            self.db.commit()
            return True
            
        except Exception as e:
            self.db.rollback()
            print(f"Lỗi Cronjob tổng hợp dữ liệu ngày {target_date}: {str(e)}")
            return False