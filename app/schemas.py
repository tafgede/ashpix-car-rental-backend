from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import date, datetime

class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str
    role: str
    phone: Optional[str] = None

class DriverCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    national_id: Optional[str] = None
    licence_number: Optional[str] = None
    licence_expiry: Optional[date] = None
    weekly_cash_in: float = 0
    joined_date: Optional[date] = None
    status: Optional[str] = "active"
    notes: Optional[str] = None

class VehicleCreate(BaseModel):
    registration: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    colour: Optional[str] = None
    vin: Optional[str] = None
    mileage: Optional[float] = 0
    status: Optional[str] = "available"
    insurance_expiry: Optional[date] = None
    licence_expiry: Optional[date] = None
    service_due_date: Optional[date] = None
    notes: Optional[str] = None

class AssignmentCreate(BaseModel):
    driver_id: int
    vehicle_id: int
    start_date: Optional[date] = None
    notes: Optional[str] = None

class PaymentCreate(BaseModel):
    driver_id: int
    amount: float
    payment_date: Optional[date] = None
    method: Optional[str] = "cash"
    reference: Optional[str] = None
    notes: Optional[str] = None