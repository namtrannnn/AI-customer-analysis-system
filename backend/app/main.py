from fastapi import FastAPI, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.utils.response import error_response, success_response
from app.routers import customer_router
from app.routers import user_router
from app.routers import auth_router
from app.routers import role_router
from app.routers import permission_router
from app.routers import video_router
from app.routers import zone_router
from app.routers import track_router
from app.routers import segment_router
from app.routers import person_profile_router
from app.routers import duration_router
from app.routers import daily_statistics_router

app = FastAPI(
    title="AI Customer Analysis API",
    version="1.0.0"
)

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://14.225.254.86:3010",
    "https://intership.hqsolutions.vn",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customer_router.router)
app.include_router(user_router.router)
app.include_router(auth_router.router)
app.include_router(role_router.router)
app.include_router(permission_router.router)
app.include_router(video_router.router)
app.include_router(zone_router.router)
app.include_router(track_router.router)
app.include_router(segment_router.router)
app.include_router(duration_router.router)
app.include_router(daily_statistics_router.router)

app.include_router(person_profile_router.router)

# Xử lý các lỗi chủ động ném ra (raise HTTPException)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            message=str(exc.detail),
            error_code=f"HTTP_{exc.status_code}"
        )
    )

# Xử lý các lỗi do Pydantic chặn lại (truyền thiếu full_name, sai sđt)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Trích xuất các lỗi thành list chuẩn để không bị lỗi JSON serializable
    clean_errors = []
    for err in exc.errors():
        clean_errors.append({
            "loc": err.get("loc"),
            "msg": err.get("msg"),
            "type": err.get("type")
        })
        
    # Gọi hàm error_response để format theo đúng chuẩn hệ thống
    formatted_content = error_response(
        message="Dữ liệu đầu vào không hợp lệ",
        error_code="VALIDATION_ERROR",
        details=clean_errors
    )
        
    return JSONResponse(
        status_code=422,
        content=formatted_content
    )


@app.get("/")
def root():
    return success_response(data=None, message="AI Customer Analysis API is running")


@app.get("/db-test")
def db_test(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT COUNT(*) FROM customers"))
    count = result.scalar_one()
    
    data = {
        "database": "supabase",
        "customers_count": count,
    }
    return success_response(data=data, message="Kết nối Database thành công")
