from pydantic import BaseModel
from typing import List, Optional

class Point(BaseModel):
    x: float
    y: float

class StoreZoneResponse(BaseModel):
    id: Optional[int] = None
    zone_type: str
    polygon: List[Point]

    class Config:
        from_attributes = True