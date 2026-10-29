"""Request bodies (validated by pydantic)."""
from typing import List, Optional

from pydantic import BaseModel


class ShipmentIn(BaseModel):
    vendor: str
    country: str
    shipment_mode: str
    inco_term: str
    fulfill_via: str
    product_group: str
    quantity: float = 1000
    value: float = 10000
    planned_lead_time_days: Optional[float] = None
    weight_kg: Optional[float] = None
    freight_cost_usd: Optional[float] = None


class DelayReasonIn(BaseModel):
    reason: str
    note: Optional[str] = ""


class FeedbackIn(BaseModel):
    answers: List[int]
    comment: Optional[str] = ""


class RegisterIn(BaseModel):
    name: str
    email: str
    password: str
    country: str
    district: str


class LoginIn(BaseModel):
    email: str
    password: str


class UserUpdateIn(BaseModel):
    approved: Optional[bool] = None
    role: Optional[str] = None
    country: Optional[str] = None
    district: Optional[str] = None


class BatchIn(BaseModel):
    shipments: List[ShipmentIn]


class ReportIn(BaseModel):
    facility: str
    district: str
    country: str
    product_group: str
    note: Optional[str] = ""
