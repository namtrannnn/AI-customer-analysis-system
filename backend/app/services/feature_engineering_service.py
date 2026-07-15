import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

class FeatureEngineeringService:
    
    @staticmethod
    def preprocess_features(raw_df: pd.DataFrame) -> pd.DataFrame:
        if raw_df.empty:
            return raw_df
            
        profile_ids = raw_df['person_profile_id'].copy()
        
        # Chỉ lấy các cột đặc trưng để huấn luyện
        feature_cols = [col for col in raw_df.columns if col != 'person_profile_id']
        features_df = raw_df[feature_cols].copy()

        # 1. Điền giá trị thiếu và Chuẩn hóa (StandardScaler)
        imputed_features = SimpleImputer(strategy='constant', fill_value=0).fit_transform(features_df)
        scaled_features = StandardScaler().fit_transform(imputed_features)
        
        processed_df = pd.DataFrame(scaled_features, columns=feature_cols)
        
        # 2. Áp dụng Đa Trọng số (Multi-Weighting)
        if 'total_spent' in processed_df.columns:
            processed_df['total_spent'] *= 3.0
        if 'total_orders' in processed_df.columns:
            processed_df['total_orders'] *= 2.0
        if 'avg_duration' in processed_df.columns:
            processed_df['avg_duration'] *= 1.5
            
        # Gắn lại ID
        processed_df.insert(0, 'person_profile_id', profile_ids)
        return processed_df