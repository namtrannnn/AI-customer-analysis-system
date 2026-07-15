import pandas as pd
from sklearn.cluster import KMeans
from sqlalchemy.orm import Session
from datetime import datetime
from app.models.customer_segment import CustomerSegment
from app.models.customer_segment_member import CustomerSegmentMember
from app.models.customer_identity import CustomerIdentity
from app.services.cluster_analysis_service import ClusterAnalysisService

class AICustomerClusteringService:
    def __init__(self, db: Session, n_clusters: int = 5):
        self.db = db
        self.n_clusters = n_clusters

    def run_clustering(self, processed_df: pd.DataFrame, raw_df: pd.DataFrame):
        if processed_df.empty or raw_df.empty:
            return {"status": "error", "message": "Dữ liệu đầu vào rỗng"}

        # 1. Chạy K-Means
        feature_cols = [col for col in processed_df.columns if col != 'person_profile_id']
        X = processed_df[feature_cols]

        kmeans = KMeans(n_clusters=self.n_clusters, random_state=42, n_init="auto")
        cluster_labels = kmeans.fit_predict(X)
        
        # 2. Phân tích Auto-Labeling
        raw_df['cluster_id'] = cluster_labels
        cluster_means = raw_df.groupby('cluster_id')[['total_spent', 'total_orders', 'avg_duration', 'total_visits']].mean()
        
        dynamic_labels = {}
        SPENDING_THRESHOLD = 500000
        DURATION_THRESHOLD = 1500
        
        for cluster_id, row in cluster_means.iterrows():
            avg_spent = row['total_spent']
            avg_duration = row['avg_duration']
            avg_orders = row['total_orders']
            avg_visits = row['total_visits']
            
            if avg_spent >= 5000000:
                name = "VIP / Big Spender - Chi tiêu cực khủng"
            elif avg_spent >= SPENDING_THRESHOLD:
                name = "Khách quen - Mua lắt nhắt nhưng đều" if avg_visits >= 3 else "Mua nhanh rút gọn"
            else:
                name = "Window Shopper - Ở rất lâu nhưng không mua" if avg_duration >= DURATION_THRESHOLD else "Vãng lai - Ghé cực nhanh rồi đi"
            
            dynamic_labels[cluster_id] = name

        raw_df['segment_name'] = raw_df['cluster_id'].map(dynamic_labels)

        # 3. Lưu vào Database
        return self._save_clusters_to_db(raw_df, dynamic_labels)

    def _save_clusters_to_db(self, df: pd.DataFrame, dynamic_labels: dict):
        try:
            segment_mapping = {}
            
            # Cập nhật hoặc tạo mới thông tin các Cụm vào bảng customer_segments
            for cluster_id, label_name in dynamic_labels.items():
                segment_name = f"Nhóm {cluster_id} ({label_name})"
                
                segment = self.db.query(CustomerSegment).filter(
                    CustomerSegment.rule_definition['cluster_index'].astext == str(cluster_id)
                ).first()
                
                if segment:
                    segment.segment_name = segment_name
                else:
                    segment = CustomerSegment(
                        segment_name=segment_name,
                        description="Nhóm được phân loại tự động bởi K-Means",
                        rule_definition={"algorithm": "K-Means", "cluster_index": cluster_id}
                    )
                    self.db.add(segment)
                
                self.db.commit()
                self.db.refresh(segment)
                segment_mapping[cluster_id] = segment.id

            # Xóa mapping cũ và chuẩn bị insert mới
            self.db.query(CustomerSegmentMember).delete()
            self.db.commit()

            # Lấy thông tin định danh
            identities = self.db.query(CustomerIdentity).all()
            identity_map = {identity.person_profile_id: identity.customer_id for identity in identities}

            # Bulk insert mapping mới
            members_to_insert = []
            for _, row in df.iterrows():
                profile_id = int(row['person_profile_id'])
                cluster_id = int(row['cluster_id'])
                
                members_to_insert.append(CustomerSegmentMember(
                    segment_id=segment_mapping[cluster_id],
                    person_profile_id=profile_id,
                    customer_id=identity_map.get(profile_id),
                    score=1.0,
                    assigned_at=datetime.utcnow()
                ))

            if members_to_insert:
                self.db.bulk_save_objects(members_to_insert)
                self.db.commit()

            analysis_service = ClusterAnalysisService(self.db)
            # df chính là analysis_df chứa dữ liệu gốc đã được gắn cluster_id
            analysis_service.update_segment_statistics(df, segment_mapping)

            return {
                "status": "success", 
                "message": f"Đã phân cụm thành công {len(members_to_insert)} khách hàng vào {self.n_clusters} nhóm.",
            }

        except Exception as e:
            self.db.rollback()
            return {"status": "error", "message": str(e)}