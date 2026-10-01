"""
Notification Router — Realtime WebSocket notification channel for Face Detections
Endpoint: /api/notifications/ws
Logic: Chỉ gửi thông báo 1 LẦN DUY NHẤT cho mỗi người (track_id / anonymous_code) trong mỗi lượt chạy video.
"""
import asyncio
import uuid
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from app.services.processing_job_manager import processing_job_manager

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.websocket("/ws")
async def notifications_websocket(websocket: WebSocket):
    """
    WebSocket Realtime cho Thông báo toàn hệ thống.
    Chỉ nổ thông báo KHI DANH TÍNH ĐÃ ĐƯỢC XÁC NHẬN (identity_status == CONFIRMED).
    Mỗi track_id hoặc anonymous_code chỉ được thông báo tối đa 1 lần trong 1 phiên chạy.
    """
    await websocket.accept()
    print("✅ [Notification WS] Client kết nối thông báo Realtime!")

    subscriber_id = None
    notified_tracks: set[int] = set()
    notified_identities: set[str] = set()
    current_job_id: str | None = None

    try:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def on_event(event_data):
            loop.call_soon_threadsafe(queue.put_nowait, event_data)

        subscriber_id = processing_job_manager.subscribe_global(on_event)

        while True:
            msg = await queue.get()
            msg_type = msg.get("type")

            # Reset bộ nhớ khi sang job mới hoặc khi video hoàn tất / reset
            msg_job_id = msg.get("job_id") or msg.get("data", {}).get("job_id")
            if msg_job_id and msg_job_id != current_job_id:
                current_job_id = msg_job_id
                notified_tracks.clear()
                notified_identities.clear()

            if msg_type in ("complete", "error", "reset", "start", "job_start"):
                notified_tracks.clear()
                notified_identities.clear()
                continue

            if msg_type != "detection":
                continue

            data = msg.get("data", {})

            # ── GATE 1: Chỉ thông báo khi danh tính đã CONFIRMED ──
            identity_status = data.get("identity_status", "PENDING")
            if identity_status != "CONFIRMED":
                continue

            # ── GATE 2: Confidence tối thiểu ──
            confidence = data.get("confidence", 0)
            if confidence and confidence < 0.40:
                continue

            # ── GATE 3: Phải có mã danh tính chính thức ──
            anonymous_code = data.get("anonymous_code")
            customer_id = data.get("customer_id")
            customer_name = data.get("customer_name")
            session_profile_id = data.get("session_profile_id")

            if not anonymous_code and not customer_name and not customer_id and not session_profile_id:
                continue

            # Loại bỏ mã tạm thời
            code_str = str(anonymous_code or "")
            if "TENTATIVE" in code_str.upper() or "PENDING" in code_str.upper() or "TEMP" in code_str.upper():
                continue

            # ── GATE 4: Xây dựng identity_key duy nhất ──
            # Ưu tiên customer_id -> person_profile_id -> anonymous_code -> session_profile_id
            identity_key = None
            if customer_id:
                identity_key = f"cust_{customer_id}"
            elif data.get("person_profile_id"):
                identity_key = f"prof_{data['person_profile_id']}"
            elif anonymous_code:
                identity_key = f"anon_{anonymous_code}"
            elif session_profile_id:
                identity_key = f"sprof_{session_profile_id}"

            track_id = data.get("track_id")

            # ── GATE 5: Kiểm tra Dedup trong phiên chạy này ──
            if customer_id and customer_name:
                # NẾU LÀ KHÁCH QUEN ĐÃ XÁC NHẬN TÊN (Ví dụ: Alex, Lê Minh Cường):
                # Cho phép nổ thông báo Khách quen Tên thật! Chỉ chặn nếu chính Tên Khách Quen này đã được báo rồi.
                if identity_key in notified_identities:
                    continue
            else:
                # NẾU LÀ KHÁCH ẨN DANH (Chưa nhận diện tên):
                if identity_key and identity_key in notified_identities:
                    continue
                if track_id is not None and track_id in notified_tracks:
                    continue

            # ── Đánh dấu đã thông báo ──
            if track_id is not None:
                notified_tracks.add(track_id)
            if identity_key:
                notified_identities.add(identity_key)

            # ── Build thông báo ──
            display_name = customer_name or session_profile_id or anonymous_code or "Khách hàng"
            person_type = "identified" if (customer_name and customer_id) else "anonymous"

            if person_type == "identified":
                title = "Khách quen vừa ghé cửa hàng"
                message = f"Phát hiện {display_name} — khách hàng đã nhận diện."
            else:
                title = "Có khách vừa vào cửa hàng"
                message = f"Phát hiện {display_name} vừa bước vào cửa hàng."

            notif_payload = {
                "type": "FACE_DETECTED",
                "data": {
                    "id": str(uuid.uuid4()),
                    "track_id": track_id,
                    "person_key": identity_key or f"track_{track_id}",
                    "anonymous_code": anonymous_code,
                    "customer_id": customer_id,
                    "title": title,
                    "message": message,
                    "customer_name": display_name,
                    "person_type": person_type,
                    "confidence": confidence,
                    "source_timestamp_seconds": data.get("source_timestamp_seconds", 0),
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
            }

            await websocket.send_json(jsonable_encoder(notif_payload))

    except WebSocketDisconnect:
        print("❌ [Notification WS] Client ngắt kết nối thông báo.")
    except Exception as e:
        print(f"🔥 [Notification WS] Lỗi: {e}")
    finally:
        if subscriber_id:
            processing_job_manager.unsubscribe_global(subscriber_id)

