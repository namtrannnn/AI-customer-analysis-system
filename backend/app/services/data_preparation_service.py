import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.person_profile import PersonProfile
from app.models.visit_sessions import VisitSession
from app.models.order import Order
from app.models.zone_visit import ZoneVisit

class DataPreparationService:
    def __init__(self, db: Session):
        self.db = db

    def get_customer_feature_dataset(self) -> pd.DataFrame:
        """
        Truy vấn và tổng hợp dữ liệu khách hàng từ các bảng liên quan.
        Bảo vệ chặt chẽ chống lặp dữ liệu (Duplicate Keys) và NaN.
        """
        # 1. Truy vấn thông tin cơ bản từ person_profiles
        profiles_query = self.db.query(
            PersonProfile.id.label("person_profile_id"),
            PersonProfile.total_visits
        ).subquery()

        # 2. Tổng hợp thời gian ở lại từ visit_sessions
        sessions_query = self.db.query(
            VisitSession.person_profile_id,
            func.sum(VisitSession.duration_seconds).label("total_duration"),
            func.avg(VisitSession.duration_seconds).label("avg_duration")
        ).group_by(VisitSession.person_profile_id).subquery()

        # 3. Tổng hợp hành vi mua hàng từ orders
        # Lưu ý: Bảng orders lưu theo cả customer_id và person_profile_id
        orders_query = self.db.query(
            Order.person_profile_id,
            func.count(Order.id).label("total_orders"),
            func.sum(Order.total_amount).label("total_spent")
        ).filter(Order.person_profile_id.isnot(None)).group_by(Order.person_profile_id).subquery()

        # 4. Tổng hợp số khu vực đã ghé thăm từ zone_visits
        zones_query = self.db.query(
            ZoneVisit.person_profile_id,
            func.count(func.distinct(ZoneVisit.zone_id)).label("unique_zones_visited"),
            func.sum(ZoneVisit.duration_seconds).label("total_zone_duration")
        ).group_by(ZoneVisit.person_profile_id).subquery()

        # 5. CỐT LÕI CHỐNG NHÂN BẢN: Sử dụng select_from() làm mỏ neo chuẩn xác
        final_query = self.db.query(
            profiles_query.c.person_profile_id,
            profiles_query.c.total_visits,
            sessions_query.c.total_duration,
            sessions_query.c.avg_duration,
            orders_query.c.total_orders,
            orders_query.c.total_spent,
            zones_query.c.unique_zones_visited,
            zones_query.c.total_zone_duration
        ).select_from(
            profiles_query
        ).outerjoin(
            sessions_query, profiles_query.c.person_profile_id == sessions_query.c.person_profile_id
        ).outerjoin(
            orders_query, profiles_query.c.person_profile_id == orders_query.c.person_profile_id
        ).outerjoin(
            zones_query, profiles_query.c.person_profile_id == zones_query.c.person_profile_id
        )

        # 6. Đọc trực tiếp kết quả truy vấn vào Pandas DataFrame
        df = pd.read_sql(final_query.statement, self.db.bind)
        
        # BỘ KHIÊN KÉP BẢO VỆ PANDAS
        # 1. Ép buộc xóa mọi ID bị trùng (nếu có dị thường từ CSDL)
        df = df.drop_duplicates(subset=["person_profile_id"])
        
        # 2. Thay thế toàn bộ giá trị NaN (Khách không mua hàng / Không có lịch sử) thành số 0
        df = df.fillna(0)
        
        return df