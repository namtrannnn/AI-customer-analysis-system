from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.customer_identity import CustomerIdentity
from app.models.person_profile import PersonProfile
from app.models.visit_sessions import VisitSession
from app.schemas.person_profile_schema import (
    PersonProfileCustomerSummary,
    PersonProfileDetail,
    PersonProfileListItem,
    PersonProfileVisitSession,
)


SortOrder = Literal["asc", "desc"]


def get_visitor_type(total_visits: int) -> str:
    if total_visits == 1:
        return "new"
    if total_visits > 1:
        return "returning"
    return "unknown"


def _profile_order(sort_order: SortOrder):
    if sort_order == "asc":
        return PersonProfile.last_seen_at.asc().nullslast()
    return PersonProfile.last_seen_at.desc().nullslast()


def _customer_summary(customer: Customer | None) -> PersonProfileCustomerSummary | None:
    if customer is None:
        return None

    return PersonProfileCustomerSummary(
        id=customer.id,
        customer_code=customer.customer_code,
        full_name=customer.full_name,
        phone=customer.phone,
        avatar_url=customer.avatar_url,
    )


def _profile_item(
    profile: PersonProfile,
    customer: Customer | None = None,
) -> PersonProfileListItem:
    return PersonProfileListItem(
        id=profile.id,
        anonymous_code=profile.anonymous_code,
        person_type=profile.person_type,
        visitor_type=get_visitor_type(profile.total_visits),
        first_seen_at=profile.first_seen_at,
        last_seen_at=profile.last_seen_at,
        total_visits=profile.total_visits,
        confidence_avg=profile.confidence_avg,
        face_image_url=profile.face_image_url,
        created_at=profile.created_at,
        customer=_customer_summary(customer),
    )


def _customer_map_for_profiles(
    db: Session,
    profile_ids: list[int],
) -> dict[int, Customer]:
    if not profile_ids:
        return {}

    rows = (
        db.query(CustomerIdentity.person_profile_id, Customer)
        .join(Customer, CustomerIdentity.customer_id == Customer.id)
        .filter(CustomerIdentity.person_profile_id.in_(profile_ids))
        .all()
    )

    customer_map: dict[int, Customer] = {}
    for person_profile_id, customer in rows:
        customer_map.setdefault(person_profile_id, customer)
    return customer_map


def get_person_profiles(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    sort_order: SortOrder = "desc",
) -> list[PersonProfileListItem]:
    profiles = (
        db.query(PersonProfile)
        .order_by(_profile_order(sort_order), PersonProfile.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    customer_map = _customer_map_for_profiles(db, [profile.id for profile in profiles])
    return [
        _profile_item(profile, customer_map.get(profile.id))
        for profile in profiles
    ]


def count_person_profiles(db: Session) -> int:
    return db.query(PersonProfile).count()


def get_person_profile_detail(
    db: Session,
    profile_id: int,
    visit_skip: int = 0,
    visit_limit: int = 100,
) -> PersonProfileDetail:
    profile = db.query(PersonProfile).filter(PersonProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy hồ sơ khách ghé thăm với ID {profile_id}.",
        )

    customer = _customer_map_for_profiles(db, [profile.id]).get(profile.id)
    visit_query = db.query(VisitSession).filter(
        VisitSession.person_profile_id == profile_id
    )
    visit_total = visit_query.count()
    visits = (
        visit_query.order_by(VisitSession.entry_time.desc(), VisitSession.id.desc())
        .offset(visit_skip)
        .limit(visit_limit)
        .all()
    )

    base_item = _profile_item(profile, customer)
    return PersonProfileDetail(
        **base_item.model_dump(),
        visit_total=visit_total,
        visit_sessions=[
            PersonProfileVisitSession.model_validate(visit)
            for visit in visits
        ],
    )

