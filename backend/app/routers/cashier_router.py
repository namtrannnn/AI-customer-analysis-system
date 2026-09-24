import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.cashier_schema import ActiveSessionListResponse, CreateOrderRequest, LinkProfileCustomerRequest
from app.services import cashier_service
from app.core.dependencies import RequirePermission
from app.utils.response import success_response
from app.services.processing_job_manager import processing_job_manager
from app.models.customer import Customer
from app.models.person_profile import PersonProfile

router = APIRouter(
    prefix="/api/cashier",
    tags=["Cashier API"]
)

@router.get("/active-customers", response_model=ActiveSessionListResponse)
def get_active_customers(
    skip: int = Query(0, ge=0, description="Số bản ghi bỏ qua"),
    limit: int = Query(10, ge=1, le=100, description="Số bản ghi tối đa lấy"),
    db: Session = Depends(get_db),
    # Dependency yêu cầu user phải có permission "cashier.view"
    current_user = Depends(RequirePermission("cashier.view")) 
):
    """
    CASH-01: Lấy danh sách khách hàng đang ở trong cửa hàng
    - Trả về thông tin session, profile ẩn danh và thông tin khách hàng (nếu đã định danh)
    """
    result = cashier_service.get_active_customers_in_store(db=db, skip=skip, limit=limit)
    return result

@router.get("/in-store-visitors")
def get_in_store_visitors_api(
    skip: int = Query(0, ge=0, description="Bỏ qua bao nhiêu bản ghi"),
    limit: int = Query(10, ge=1, le=100, description="Số lượng lấy"),
    db: Session = Depends(get_db),
    # Dependency phân quyền
    current_user = Depends(RequirePermission("cashier.view"))
):
    """
    CASH-02: Lấy danh sách khách hàng đang ở trong cửa hàng 
    (chưa có giờ ra - exit_time is NULL)
    """
    result = cashier_service.get_in_store_visitors(db=db, skip=skip, limit=limit)
    
    # Trả về qua helper function success_response
    return success_response(
        data=result,
        message="Lấy danh sách khách hàng đang trong cửa hàng thành công"
    )

@router.post("/orders")
def create_order_api(
    request_data: CreateOrderRequest,
    db: Session = Depends(get_db),
    current_user = Depends(RequirePermission("order.create"))
):
    """CASH-08: Ghi nhận đơn hàng tại quầy"""
    result = cashier_service.create_store_order(db, request_data)
    return success_response(data=result, message="Tạo đơn hàng thành công.")

@router.websocket("/ws")
async def cashier_websocket(websocket: WebSocket):
    await websocket.accept()
    print("✅ [Backend WS] Client đã kết nối thành công vào quầy thu ngân!")
    
    subscriber_id = None
    try:
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()
        
        def on_event(event_data):
            loop.call_soon_threadsafe(queue.put_nowait, event_data)
        
        subscriber_id = processing_job_manager.subscribe_global(on_event)
        
        while True:
            msg = await queue.get()
            safe_msg = jsonable_encoder(msg)
            await websocket.send_json(safe_msg)
            
    except WebSocketDisconnect:
        print("❌ [Backend WS] Client đã ngắt kết nối chủ động.")
    except Exception as e:
        print(f"🔥 [Backend WS] Lỗi: {str(e)}")
    finally:
        if subscriber_id:
            processing_job_manager.unsubscribe_global(subscriber_id)

# @router.post("/link-customer")
# def api_link_profile_to_customer(
#     payload: LinkProfileCustomerRequest,
#     db: Session = Depends(get_db)
# ):
#     """
#     API dùng cho Thu ngân nối một khuôn mặt đang đứng ở quầy với một khách hàng có sẵn trong DB (qua SĐT).
#     """
#     return cashier_service.link_profile_to_existing_customer(
#         db=db, 
#         data=payload
#     )

@router.post("/link-customer")
def api_link_profile_to_customer(
    payload: LinkProfileCustomerRequest,
    db: Session = Depends(get_db),
    current_user = Depends(RequirePermission("customer.create"))
):
    """
    API dùng cho Thu ngân nối một khuôn mặt đang đứng ở quầy với một khách hàng có sẵn trong DB (qua SĐT).
    """
    
    # Gọi service (lưu ý truyền đúng tham số mà service của bạn đang yêu cầu)
    return cashier_service.link_profile_to_existing_customer(
        db=db, 
        data=payload
    )