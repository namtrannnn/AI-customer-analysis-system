from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import RequirePermission
from app.database.session import get_db
from app.schemas import person_profile_schema as schemas
from app.schemas.response_schema import StandardResponse
from app.services import person_profile_service as services
from app.utils.response import success_response


router = APIRouter(
    prefix="/api/person-profiles",
    tags=["Person Profiles"],
)


@router.get("/", response_model=StandardResponse[list[schemas.PersonProfileListItem]])
def get_person_profiles(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    visitor_type: Literal["all", "new", "returning"] = Query(default="all"),
    q: str | None = Query(default=None, description="Tim theo ma an danh, ten, ma hoac so dien thoai khach hang"),
    start_date: date | None = Query(default=None, description="Loc tu ngay last_seen_at"),
    end_date: date | None = Query(default=None, description="Loc den ngay last_seen_at"),
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("person_profile.view")),
):
    profiles = services.get_person_profiles(
        db=db,
        skip=skip,
        limit=limit,
        sort_order=sort_order,
        visitor_type=visitor_type,
        search_query=q,
        start_date=start_date,
        end_date=end_date,
    )
    total = services.count_person_profiles(
        db=db,
        visitor_type=visitor_type,
        search_query=q,
        start_date=start_date,
        end_date=end_date,
    )
    return success_response(
        data=profiles,
        message="Lấy danh sách hồ sơ khách ghé thăm thành công",
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/stats", response_model=StandardResponse[schemas.PersonProfileStatsResponse])
def get_person_profile_stats(
    q: str | None = Query(default=None, description="Tim theo ma an danh, ten, ma hoac so dien thoai khach hang"),
    start_date: date | None = Query(default=None, description="Loc tu ngay last_seen_at"),
    end_date: date | None = Query(default=None, description="Loc den ngay last_seen_at"),
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("person_profile.view")),
):
    stats = services.get_person_profile_stats(
        db=db,
        search_query=q,
        start_date=start_date,
        end_date=end_date,
    )
    return success_response(
        data=stats,
        message="Lay thong ke khach moi va khach quay lai thanh cong",
    )


@router.get("/{profile_id}", response_model=StandardResponse[schemas.PersonProfileDetail])
def get_person_profile_detail(
    profile_id: int,
    visit_skip: int = Query(default=0, ge=0),
    visit_limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(RequirePermission("person_profile.view")),
):
    profile = services.get_person_profile_detail(
        db=db,
        profile_id=profile_id,
        visit_skip=visit_skip,
        visit_limit=visit_limit,
    )
    return success_response(
        data=profile,
        message="Lấy chi tiết hồ sơ khách ghé thăm thành công",
    )
