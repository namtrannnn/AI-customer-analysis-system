from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """
    Lớp Base gốc cho toàn bộ các Model trong hệ thống.
    Các model định nghĩa trong thư mục app/models/ sẽ kế thừa lớp này.
    """
    pass