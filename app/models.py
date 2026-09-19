from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text, Boolean, Enum, JSON
from sqlalchemy.orm import relationship
from .database import Base
import enum

class DriverStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"

class VehicleStatus(str, enum.Enum):
    AVAILABLE = "available"
    ACTIVE = "active"
    REPAIR = "repair"
    MAINTENANCE = "maintenance"
    INACTIVE = "inactive"
    SOLD = "sold"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=False)
    role = Column(String(30), nullable=False)
    phone = Column(String(50))
    is_active = Column(Integer, default=1)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Driver(Base):
    __tablename__ = "drivers"
    id = Column(Integer, primary_key=True)
    driver_code = Column(String(30), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    phone = Column(String(50))
    national_id = Column(String(80))
    licence_number = Column(String(80))
    licence_expiry = Column(Date)
    weekly_cash_in = Column(Float, default=0)
    joined_date = Column(Date, default=date.today)
    status = Column(String(30), default="active")
    notes = Column(Text)
    assignments = relationship("Assignment", back_populates="driver")
    obligations = relationship("WeeklyObligation", back_populates="driver", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="driver", cascade="all, delete-orphan")

class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True)
    registration = Column(String(40), unique=True, nullable=False)
    make = Column(String(80))
    model = Column(String(80))
    year = Column(Integer)
    colour = Column(String(50))
    vin = Column(String(100))
    mileage = Column(Float, default=0)
    status = Column(String(30), default="available")
    insurance_expiry = Column(Date)
    licence_expiry = Column(Date)
    service_due_date = Column(Date)
    notes = Column(Text)
    assignments = relationship("Assignment", back_populates="vehicle")

class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    start_date = Column(Date, default=date.today)
    end_date = Column(Date)
    notes = Column(Text)
    driver = relationship("Driver", back_populates="assignments")
    vehicle = relationship("Vehicle", back_populates="assignments")

class WeeklyObligation(Base):
    __tablename__ = "weekly_obligations"
    id = Column(Integer, primary_key=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    amount_due = Column(Float, default=0)
    amount_paid = Column(Float, default=0)
    status = Column(String(30), default="unpaid")
    created_at = Column(DateTime, default=datetime.utcnow)
    driver = relationship("Driver", back_populates="obligations")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    payment_date = Column(Date, default=date.today)
    amount = Column(Float, nullable=False)
    method = Column(String(50), default="cash")
    reference = Column(String(100))
    notes = Column(Text)
    recorded_by = Column(String(80))
    driver = relationship("Driver", back_populates="payments")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    username = Column(String(80))
    action = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)