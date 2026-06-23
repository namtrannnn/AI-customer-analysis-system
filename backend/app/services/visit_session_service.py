from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime
from typing import List, Optional

# Đảm bảo bạn đã import các Model tương ứng
from app.models.visit_sessions import VisitSession
from app.models.person_profile import PersonProfile
from app.schemas.visit_session_schema import VisitSessionCreate, VisitSessionUpdate

class VisitSessionService:
    
    def create_session(self, db: Session, payload: VisitSessionCreate) -> VisitSession:
        """
        Tạo một phiên xuất hiện (Visit Session) mới khi khách hàng bước vào khung hình.
        """
        # VALIDATE NGHIỆP VỤ 1: Kiểm tra xem PersonProfile này có thực sự tồn tại dưới DB chưa
        person_exists = db.query(PersonProfile).filter(PersonProfile.id == payload.person_profile_id).first()
        if not person_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không thể tạo Session. Không tìm thấy khách hàng với ID {payload.person_profile_id}"
            )

        # VALIDATE NGHIỆP VỤ 2: Chống trùng lặp (Tùy chọn)
        # Nếu khách này đang có 1 session chưa kết thúc (exit_time is null) ở cùng 1 nguồn camera, thì không tạo mới
        active_session = db.query(VisitSession).filter(
            VisitSession.person_profile_id == payload.person_profile_id,
            VisitSession.source_identifier == payload.source_identifier,
            VisitSession.exit_time.is_(None)
        ).first()

        if active_session:
            return active_session # Trả về luôn session cũ thay vì tạo rác DB

        # Ghi vào Database
        new_session = VisitSession(
            person_profile_id=payload.person_profile_id,
            source_identifier=payload.source_identifier,
            enter_time=payload.enter_time
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        return new_session

    def end_session(self, db: Session, session_id: int, payload: VisitSessionUpdate) -> VisitSession:
        """
        Cập nhật thời gian rời đi (exit_time) khi khách hàng ra khỏi khung hình hoặc video kết thúc.
        """
        session = db.query(VisitSession).filter(VisitSession.id == session_id).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy Visit Session với ID {session_id}"
            )

        # VALIDATE NGHIỆP VỤ 3: Thời gian rời đi không được diễn ra trước thời gian bước vào
        # Chuyển đổi về cùng timezone (timezone-naive) để so sánh an toàn nếu có lệch múi giờ
        enter_time_naive = session.enter_time.replace(tzinfo=None)
        exit_time_naive = payload.exit_time.replace(tzinfo=None)

        if exit_time_naive < enter_time_naive:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lỗi Logic: Thời gian khách rời đi (exit_time) không thể nhỏ hơn thời gian bước vào (enter_time)."
            )

        session.exit_time = payload.exit_time
        
        # Cập nhật thêm thuộc tính tính toán thời gian ở lại (Duration)
        delta = exit_time_naive - enter_time_naive
        session.duration_seconds = int(delta.total_seconds())

        db.commit()
        db.refresh(session)
        return session

    def get_sessions_by_person(self, db: Session, person_profile_id: int) -> List[VisitSession]:
        """
        Lấy toàn bộ lịch sử xuất hiện của một khách hàng cụ thể (Dùng cho PB04 - Khách hàng xuất hiện nhiều lần).
        """
        return db.query(VisitSession).filter(
            VisitSession.person_profile_id == person_profile_id
        ).order_by(VisitSession.enter_time.desc()).all()


# Khởi tạo Singleton pattern để dùng chung
visit_session_service = VisitSessionService()