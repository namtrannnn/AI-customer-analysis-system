import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Nạp các biến môi trường từ file .env vào hệ thống
load_dotenv()

# Lấy chuỗi kết nối từ file .env
DATABASE_URL = os.environ["DATABASE_URL"]

# Khởi tạo Engine quản lý kết nối
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True # Tự động kiểm tra kết nối có bị rớt không trước khi truy vấn
)

# Khởi tạo cấu hình cho Session
# autocommit=False: Tắt tự động commit để ta tự kiểm soát transaction (rollback khi có lỗi)
# autoflush=False: Tắt tự động đẩy dữ liệu xuống DB trước khi query
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency cung cấp Database Session cho FastAPI
def get_db():
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()