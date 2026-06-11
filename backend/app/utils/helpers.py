import time
import unicodedata
import secrets
import string
from sqlalchemy.orm import Session
from app.models.user import User

# Hàm 1: Xóa dấu tiếng Việt
def remove_vietnamese_accents(text: str) -> str:
    nfkd_form = unicodedata.normalize('NFKD', text)
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])

# Hàm 2: Tự động sinh Username
def generate_corporate_username(full_name: str, db: Session) -> str:
    # Bước 1: Làm sạch và tách chữ (Ví dụ: "Phạm Ngọc Gia Oanh" -> "pham ngoc gia oanh")
    clean_name = remove_vietnamese_accents(full_name).lower().strip()
    parts = clean_name.split()
    
    if not parts:
        return f"user{int(time.time())}"
        
    # Bước 2: Lấy Tên + Chữ cái đầu của Họ đệm (Oanh + p, n, g -> oanhpng)
    first_name = parts[-1]
    initials = "".join([p[0] for p in parts[:-1]])
    base_username = f"{first_name}{initials}"
    
    # Bước 3: Đảm bảo Unique (Nếu oanhpng đã tồn tại, sẽ thành oanhpng1, oanhpng2)
    username = base_username
    counter = 1
    while db.query(User).filter(User.username == username).first():
        username = f"{base_username}{counter}"
        counter += 1
        
    return username

# Hàm 3: Sinh mật khẩu ngẫu nhiên độ bảo mật cao
def generate_random_password(length: int = 10) -> str:
    # Bao gồm chữ hoa, chữ thường, số và ký tự đặc biệt
    alphabet = string.ascii_letters + string.digits + "@#$%^&+="
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        # Đảm bảo có ít nhất 1 chữ thường, 1 chữ hoa và 2 số
        if (any(c.islower() for c in password) 
            and any(c.isupper() for c in password) 
            and sum(c.isdigit() for c in password) >= 2):
            break
    return password