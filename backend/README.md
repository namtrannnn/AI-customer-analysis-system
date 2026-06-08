# AI Customer Analysis System - Backend

## 1. Giới thiệu

Backend của dự án **AI Customer Analysis System** được xây dựng bằng **FastAPI**, đóng vai trò cung cấp RESTful API cho Frontend Next.js. Backend xử lý các chức năng như đăng nhập, quản lý khách hàng, quản lý user, nhóm quyền, phân quyền và kết nối cơ sở dữ liệu.

## 2. Công nghệ sử dụng

- Python
- FastAPI
- Uvicorn
- SQLAlchemy
- PostgreSQL / Supabase PostgreSQL
- JWT Authentication
- Docker

## 3. Cấu trúc thư mục

```txt
backend/
├── app/
│   ├── main.py
│   ├── core/
│   ├── database/
│   ├── models/
│   ├── schemas/
│   ├── routers/
│   ├── services/
│   └── utils/
├── .env
├── requirements.txt
└── README.md
```

## 4. Mô tả thư mục

- `main.py`: File khởi động chính của FastAPI, dùng để tạo app, cấu hình CORS và gắn các router.
- `core/`: Chứa cấu hình hệ thống, bảo mật, JWT, hash password và xác thực token.
- `database/`: Chứa cấu hình kết nối database, tạo session và cung cấp hàm `get_db()`.
- `models/`: Chứa các model ánh xạ với bảng trong database như customer, user, role và permission.
- `schemas/`: Chứa Pydantic schema để validate dữ liệu request và response.
- `routers/`: Chứa các API endpoint, đóng vai trò gần giống controller.
- `services/`: Chứa logic nghiệp vụ chính như login, CRUD khách hàng, user, role và phân quyền.
- `utils/`: Chứa các hàm dùng chung như chuẩn hóa response và phân trang.
- `.env`: Chứa biến môi trường như database URL, secret key và cấu hình JWT.
- `requirements.txt`: Chứa danh sách thư viện Python cần cài đặt.

## 5. Luồng xử lý Backend

Backend hoạt động theo kiến trúc phân lớp:

```txt
Frontend
→ Router
→ Schema
→ Service
→ Model
→ Database
→ Response
→ Frontend
```

Ví dụ API đăng nhập:

```txt
POST /api/v1/auth/login
→ auth_router.py
→ auth_schema.py
→ auth_service.py
→ user.py
→ database
→ security.py
→ response
```

Ví dụ API khách hàng:

```txt
GET /api/v1/customers
→ customer_router.py
→ customer_service.py
→ customer.py
→ database
→ response
```

## 6. Cài đặt

Tạo môi trường ảo:

```bash
python -m venv venv
```

Kích hoạt môi trường ảo trên Windows:

```bash
.\venv\Scripts\Activate.ps1
```

Cài đặt thư viện:

```bash
pip install -r requirements.txt
```

## 7. Chạy server

```bash
uvicorn app.main:app --reload
```

Server chạy tại:

```txt
http://localhost:8000
```

Swagger Docs:

```txt
http://localhost:8000/docs
```

## 8. Biến môi trường

Tạo file `.env` trong thư mục `backend`:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/database_name
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

## 9. Ghi chú

Không commit các file sau lên GitHub:

```txt
.env
venv/
__pycache__/
```
