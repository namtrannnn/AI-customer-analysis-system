from datetime import datetime, timedelta, timezone
import os

from dotenv import load_dotenv
import jwt
from passlib.context import CryptContext

# Cấu hình CryptContext để băm mật khẩu (Dùng bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hàm băm mật khẩu
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Hàm kiểm tra mật khẩu (sẽ dùng cho API Login sau này)
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# CẤU HÌNH BẢO MẬT
load_dotenv()

SECRET_KEY = os.environ["JWT_SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # Cài đặt token sống 24 giờ (1 ngày)

# HÀM XỬ LÝ TOKEN (JWT)
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Tạo JWT Token chứa thông tin định danh của người dùng"""
    to_encode = data.copy()
    
    # Thiết lập thời gian hết hạn (Expiration Time)
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Thêm trường 'exp' chuẩn của JWT
    to_encode.update({"exp": expire})
    
    # Mã hóa chuỗi thành JWT
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt