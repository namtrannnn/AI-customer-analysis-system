import pandas as pd
from sqlalchemy.orm import Session
from app.models.customer_segment import CustomerSegment

class ClusterAnalysisService:
    def __init__(self, db: Session):
        self.db = db

    def update_segment_statistics(self, analysis_df: pd.DataFrame, segment_mapping: dict):
        """
        BE-5: Tổng hợp thống kê của từng cụm và lưu vào cột rule_definition.
        - analysis_df: DataFrame chứa dữ liệu gốc đã được gắn nhãn 'cluster_id'
        - segment_mapping: Dictionary map giữa cluster_id và segment_id trong DB
        """
        try:
            # 1. Gom nhóm tính toán bằng Pandas
            stats_df = analysis_df.groupby('cluster_id').agg(
                member_count=('person_profile_id', 'count'),
                avg_spent=('total_spent', 'mean'),
                avg_duration=('avg_duration', 'mean'),
                avg_orders=('total_orders', 'mean'),
                avg_visits=('total_visits', 'mean')
            ).reset_index()
            stats_df = stats_df.fillna(0)

            # 2. Cập nhật vào Database
            for _, row in stats_df.iterrows():
                cluster_id = int(row['cluster_id'])
                segment_id = segment_mapping.get(cluster_id)
                
                if not segment_id:
                    continue

                segment = self.db.query(CustomerSegment).filter(CustomerSegment.id == segment_id).first()
                if segment:
                    # Tạo cục JSON thống kê
                    stats_json = {
                        "algorithm": "K-Means",
                        "cluster_index": cluster_id,
                        "statistics": {
                            "member_count": int(row['member_count']),
                            "avg_spent": round(float(row['avg_spent']), 2),
                            "avg_duration": round(float(row['avg_duration']), 2),
                            "avg_orders": round(float(row['avg_orders']), 2),
                            "avg_visits": round(float(row['avg_visits']), 2)
                        }
                    }
                    # Ghi đè vào cột JSONB của PostgreSQL
                    segment.rule_definition = stats_json
            
            self.db.commit()
            return True
            
        except Exception as e:
            self.db.rollback()
            print(f"Lỗi khi thống kê cụm: {e}")
            return False
