from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

# Khai báo kiểu Generic T để có thể bọc bất kỳ Schema nào (Customer, User,...)
T = TypeVar("T")

class MetaData(BaseModel):
    total: int
    skip: int
    limit: int

class StandardResponse(BaseModel, Generic[T]):
    status: str = "success"
    message: str = "Thành công"
    data: Optional[T] = None
    meta: Optional[MetaData] = None

class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    error_code: Optional[str] = None
    details: Optional[Any] = None