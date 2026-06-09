from typing import Any, Optional
from app.schemas.response_schema import MetaData

def success_response(data: Any, message: str = "Thành công", total: Optional[int] = None, skip: Optional[int] = None, limit: Optional[int] = None) -> dict:
    response = {
        "status": "success",
        "message": message,
        "data": data
    }
    if total is not None and skip is not None and limit is not None:
        response["meta"] = MetaData(total=total, skip=skip, limit=limit).model_dump()
        
    return response

def error_response(message: str, error_code: str = "BAD_REQUEST", details: Any = None) -> dict:
    return {
        "status": "error",
        "message": message,
        "error_code": error_code,
        "details": details
    }