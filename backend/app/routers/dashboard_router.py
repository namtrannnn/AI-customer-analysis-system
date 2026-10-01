"""
Dashboard Realtime Router
WebSocket /api/dashboard/ws — forward detection events từ AI pipeline
Pattern giống cashier_router.py
"""
import asyncio
from datetime import date, datetime

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.visit_sessions import VisitSession
from app.models.daily_statistic import DailyStatistic
from app.services.processing_job_manager import processing_job_manager
from app.utils.response import success_response

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard Realtime"])


@router.get("/today-stats")
def get_today_stats(db: Session = Depends(get_db)):
    """Lấy thống kê hôm nay từ DB."""
    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time())

    current_count = db.query(VisitSession).filter(
        VisitSession.exit_time.is_(None)
    ).count()

    today_total = db.query(VisitSession).filter(
        VisitSession.entry_time >= start_of_day
    ).count()

    daily = db.query(DailyStatistic).filter(
        DailyStatistic.statistic_date == today
    ).first()

    avg_stay_minutes = round((daily.avg_duration_seconds or 0) / 60, 1) if daily else 0

    # Query doanh thu + đơn hàng hôm nay trực tiếp từ bảng orders
    from app.models.order import Order
    from sqlalchemy import func as sqlfunc
    order_stats = db.query(
        sqlfunc.count(Order.id).label("total_orders"),
        sqlfunc.coalesce(sqlfunc.sum(Order.total_amount), 0).label("total_revenue"),
    ).filter(
        Order.order_time >= start_of_day
    ).first()

    today_revenue = float(order_stats.total_revenue) if order_stats else 0.0
    today_orders  = int(order_stats.total_orders)    if order_stats else 0

    return success_response(
        data={
            "current_count":    current_count,
            "today_total":      today_total,
            "today_revenue":    today_revenue,
            "today_orders":     today_orders,
            "avg_stay_minutes": avg_stay_minutes,
        },
        message="Lấy thống kê hôm nay thành công"
    )


@router.websocket("/ws")
async def dashboard_websocket(websocket: WebSocket):
    """
    WebSocket realtime cho Dashboard.
    Nhận detection events từ AI pipeline → forward sang FE.
    Pattern giống /api/cashier/ws
    """
    await websocket.accept()
    print("✅ [Dashboard WS] Client kết nối!")

    subscriber_id = None
    try:
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()

        def on_event(event_data):
            loop.call_soon_threadsafe(queue.put_nowait, event_data)

        subscriber_id = processing_job_manager.subscribe_global(on_event)

        while True:
            msg = await queue.get()
            msg_type = msg.get("type")

            # Forward complete/error → FE reset counter
            if msg_type in ("complete", "error"):
                await websocket.send_json(jsonable_encoder(msg))
                continue

            # Chỉ xử lý detection events
            if msg_type != "detection":
                continue

            data = msg.get("data", {})
            confidence = data.get("confidence", 0)

            # Bỏ qua detection chất lượng thấp
            if confidence < 0.50:
                continue

            # Gửi presence_update — FE tự deduplicate theo track_id
            await websocket.send_json(jsonable_encoder({
                "type": "presence_update",
                "data": {
                    "anonymous_code":           data.get("anonymous_code"),
                    "track_id":                 data.get("track_id"),
                    "confidence":               confidence,
                    "customer_id":              data.get("customer_id"),
                    "customer_name":            data.get("customer_name"),
                    "source_timestamp_seconds": data.get("source_timestamp_seconds"),
                }
            }))

    except WebSocketDisconnect:
        print("❌ [Dashboard WS] Client ngắt kết nối.")
    except Exception as e:
        print(f"🔥 [Dashboard WS] Lỗi: {e}")
    finally:
        if subscriber_id:
            processing_job_manager.unsubscribe_global(subscriber_id)
