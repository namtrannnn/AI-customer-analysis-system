from datetime import datetime

import pandas as pd
from sklearn.cluster import KMeans
from sqlalchemy.orm import Session

from app.models.customer_identity import CustomerIdentity
from app.models.customer_segment import CustomerSegment
from app.models.customer_segment_member import CustomerSegmentMember
from app.services.cluster_analysis_service import ClusterAnalysisService


class AICustomerClusteringService:
    def __init__(self, db: Session, n_clusters: int = 5):
        self.db = db
        self.n_clusters = n_clusters

    def run_clustering(self, processed_df: pd.DataFrame, raw_df: pd.DataFrame):
        if processed_df.empty or raw_df.empty:
            return {"status": "error", "message": "Dữ liệu đầu vào rỗng"}

        # 1. Chạy K-Means
        feature_cols = [col for col in processed_df.columns if col != "person_profile_id"]
        X = processed_df[feature_cols]

        actual_clusters = min(self.n_clusters, len(processed_df))
        if actual_clusters < 2:
            return {
                "status": "warning",
                "message": "Cần ít nhất 2 khách hàng để chạy phân cụm.",
                "segments_created": 0,
                "total_customers_processed": len(processed_df),
                "features_used": feature_cols,
            }

        kmeans = KMeans(n_clusters=actual_clusters, random_state=42, n_init="auto")
        cluster_labels = kmeans.fit_predict(X)

        # 2. Phân tích Auto-Labeling (THUẬT TOÁN THÍCH ỨNG)
        raw_df["cluster_id"] = cluster_labels
        
        required_cols = ["total_spent", "total_orders", "avg_duration", "total_visits"]
        for col in required_cols:
            if col not in raw_df.columns:
                raw_df[col] = 0.0

        cluster_means = raw_df.groupby("cluster_id")[required_cols].mean()

        #  TÌM RA "ĐỈNH" CỦA DỮ LIỆU ĐỂ LÀM HỆ QUY CHIẾU
        max_spent = cluster_means["total_spent"].max()
        max_duration = cluster_means["avg_duration"].max()
        max_visits = cluster_means["total_visits"].max()

        dynamic_labels = {}

        for cluster_id, row in cluster_means.iterrows():
            avg_spent = row["total_spent"]
            avg_duration = row["avg_duration"]
            avg_visits = row["total_visits"]

            # Phân loại dựa trên tỷ lệ % so với cụm cao nhất
            if avg_spent > 0 and avg_spent >= (max_spent * 0.6):
                name = "VIP / Big Spender - Chi tiêu cực khủng"
            elif avg_spent > 0 and avg_spent >= (max_spent * 0.15):
                name = "Khách quen - Mua đều" if avg_visits >= (max_visits * 0.5) else "Mua nhanh rút gọn"
            else:
                if max_duration > 0 and avg_duration >= (max_duration * 0.6):
                    name = "Window Shopper - Ở rất lâu nhưng không mua"
                else:
                    name = "Vãng lai - Ghé cực nhanh rồi đi"

            dynamic_labels[int(cluster_id)] = name

        raw_df["segment_name"] = raw_df["cluster_id"].map(dynamic_labels)

        # 3. Lưu vào Database
        return self._save_clusters_to_db(raw_df, dynamic_labels, feature_cols)

    def _save_clusters_to_db(
        self,
        df: pd.DataFrame,
        dynamic_labels: dict[int, str],
        feature_cols: list[str],
    ):
        try:
            segment_mapping = {}

            # 1. Cập nhật hoặc tạo mới thông tin các Cụm (0, 1, 2...)
            for cluster_id, label_name in dynamic_labels.items():
                segment_name = f"Nhóm {cluster_id} ({label_name})"

                segment = self.db.query(CustomerSegment).filter(
                    CustomerSegment.rule_definition["cluster_index"].astext == str(cluster_id)
                ).first()

                if segment:
                    segment.segment_name = segment_name
                else:
                    segment = CustomerSegment(
                        segment_name=segment_name,
                        description="Nhóm được phân loại tự động bởi K-Means AI-08",
                        rule_definition={"algorithm": "K-Means", "cluster_index": cluster_id},
                    )
                    self.db.add(segment)

                self.db.flush()
                segment_mapping[cluster_id] = segment.id

            # 🚀 2. BỔ SUNG CHỐT CHẶN: XÓA CÁC CỤM "ZOMBIE" CỦA LẦN CHẠY TRƯỚC
            # Lấy danh sách các index đang được sử dụng trong lần chạy này (VD: ['0', '1', '2'])
            active_cluster_indexes = [str(k) for k in dynamic_labels.keys()]

            # Xóa thẳng tay các cụm do K-Means tạo ra nhưng không nằm trong danh sách active
            self.db.query(CustomerSegment).filter(
                CustomerSegment.rule_definition["algorithm"].astext == "K-Means",
                CustomerSegment.rule_definition["cluster_index"].astext.notin_(active_cluster_indexes)
            ).delete(synchronize_session=False)

            self.db.commit()

            # 3. Xóa mapping thành viên cũ (Clear old members)
            self.db.query(CustomerSegmentMember).delete()
            self.db.commit()

            # Lấy thông tin định danh
            identities = self.db.query(CustomerIdentity).all()
            identity_map = {
                identity.person_profile_id: identity.customer_id
                for identity in identities
            }

            # Bulk insert mapping mới
            members_to_insert = []
            for _, row in df.iterrows():
                profile_id = int(row["person_profile_id"])
                cluster_id = int(row["cluster_id"])

                members_to_insert.append(CustomerSegmentMember(
                    segment_id=segment_mapping[cluster_id],
                    person_profile_id=profile_id,
                    customer_id=identity_map.get(profile_id),
                    score=1.0,
                    assigned_at=datetime.utcnow(),
                ))

            if members_to_insert:
                self.db.bulk_save_objects(members_to_insert)
                self.db.commit()

            analysis_service = ClusterAnalysisService(self.db)
            # df chính là analysis_df chứa dữ liệu gốc đã được gắn cluster_id
            analysis_service.update_segment_statistics(df, segment_mapping)

            return {
                "status": "success",
                "message": (
                    f"Đã phân cụm thành công {len(members_to_insert)} khách hàng "
                    f"vào {len(dynamic_labels)} nhóm."
                ),
                "segments_created": len(dynamic_labels),
                "total_customers_processed": len(members_to_insert),
                "features_used": feature_cols,
            }

        except Exception as exc:
            self.db.rollback()
            return {"status": "error", "message": str(exc)}
