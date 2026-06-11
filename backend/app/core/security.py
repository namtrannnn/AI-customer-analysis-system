from passlib.context import CryptContext

# Cấu hình CryptContext để băm mật khẩu (Dùng bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hàm băm mật khẩu
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Hàm kiểm tra mật khẩu (sẽ dùng cho API Login sau này)
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)