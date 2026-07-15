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
        Trả về pandas DataFrame chứa các đặc trưng hành vi.
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
        orders_query = self.db.query(
            Order.person_profile_id,
            func.count(Order.id).label("total_orders"),
            func.sum(Order.total_amount).label("total_spent")
        ).group_by(Order.person_profile_id).subquery()

        # 4. Tổng hợp số khu vực đã ghé thăm từ zone_visits
        zones_query = self.db.query(
            ZoneVisit.person_profile_id,
            func.count(func.distinct(ZoneVisit.zone_id)).label("unique_zones_visited"),
            func.sum(ZoneVisit.duration_seconds).label("total_zone_duration")
        ).group_by(ZoneVisit.person_profile_id).subquery()

        # 5. Join tất cả các subquery lại với nhau
        final_query = self.db.query(
            profiles_query.c.person_profile_id,
            profiles_query.c.total_visits,
            sessions_query.c.total_duration,
            sessions_query.c.avg_duration,
            orders_query.c.total_orders,
            orders_query.c.total_spent,
            zones_query.c.unique_zones_visited,
            zones_query.c.total_zone_duration
        ).outerjoin(
            sessions_query, profiles_query.c.person_profile_id == sessions_query.c.person_profile_id
        ).outerjoin(
            orders_query, profiles_query.c.person_profile_id == orders_query.c.person_profile_id
        ).outerjoin(
            zones_query, profiles_query.c.person_profile_id == zones_query.c.person_profile_id
        )

        # Đọc trực tiếp kết quả truy vấn vào Pandas DataFrame
        df = pd.read_sql(final_query.statement, self.db.bind)
        
        return df