from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PersonProfileCustomerSummary(BaseModel):
    id: int
    customer_code: str
    full_name: str
    phone: str | None = None
    avatar_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PersonProfileVisitSession(BaseModel):
    id: int
    entry_time: datetime
    exit_time: datetime | None = None
    duration_seconds: int | None = None
    is_identified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PersonProfileBaseResponse(BaseModel):
    id: int
    anonymous_code: str
    person_type: str
    visitor_type: str
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    total_visits: int
    confidence_avg: float | None = None
    face_image_url: str | None = None
    created_at: datetime
    customer: PersonProfileCustomerSummary | None = None


class PersonProfileListItem(PersonProfileBaseResponse):
    pass


class PersonProfileDetail(PersonProfileBaseResponse):
    visit_total: int
    visit_sessions: list[PersonProfileVisitSession]

