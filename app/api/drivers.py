from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import shutil
import os
from datetime import date
from ..database import get_db
from ..models import Driver, Assignment, WeeklyObligation, DriverDocument
from ..schemas import DriverCreate, DriverUpdate, DriverResponse
from ..auth import current_user, require_roles

router = APIRouter(prefix="/api/drivers", tags=["drivers"])

# Upload directory setup
UPLOAD_DIR = "uploads/drivers"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/", response_model=List[DriverResponse])
async def get_drivers(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user = Depends(current_user)
):
    query = db.query(Driver)
    
    if search:
        query = query.filter(
            (Driver.first_name.ilike(f"%{search}%")) |
            (Driver.last_name.ilike(f"%{search}%")) |
            (Driver.phone.ilike(f"%{search}%")) |
            (Driver.driver_code.ilike(f"%{search}%"))
        )
    
    if status:
        query = query.filter(Driver.status == status)
    
    drivers = query.offset(skip).limit(limit).all()
    result = []
    
    for d in drivers:
        response = DriverResponse.from_orm(d)
        # Get assigned vehicle
        assignment = db.query(Assignment).filter(
            Assignment.driver_id == d.id,
            Assignment.status == "active"
        ).first()
        response.assigned_vehicle = assignment.vehicle.registration if assignment else None
        
        # Calculate balance
        due = sum(o.amount_due for o in d.obligations)
        paid = sum(p.amount for p in d.payments)
        response.balance = max(0, due - paid)
        
        result.append(response)
    
    return result

@router.post("/", response_model=DriverResponse)
async def create_driver(
    driver: DriverCreate,
    db: Session = Depends(get_db),
    user = Depends(require_roles("admin", "manager"))
):
    # Generate driver code
    count = db.query(Driver).count() + 1
    driver_code = f"DRV-{count:04d}"
    
    db_driver = Driver(driver_code=driver_code, **driver.dict())
    db.add(db_driver)
    db.commit()
    db.refresh(db_driver)
    
    # Create first weekly obligation
    start = date.today()
    db.add(WeeklyObligation(
        driver_id=db_driver.id,
        week_start=start,
        week_end=start + timedelta(days=6),
        amount_due=db_driver.weekly_cash_in
    ))
    db.commit()
    
    return db_driver

@router.get("/{driver_id}", response_model=DriverResponse)
async def get_driver(
    driver_id: int,
    db: Session = Depends(get_db),
    user = Depends(current_user)
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    return driver

@router.put("/{driver_id}", response_model=DriverResponse)
async def update_driver(
    driver_id: int,
    driver_data: DriverUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_roles("admin", "manager"))
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    
    for key, value in driver_data.dict(exclude_unset=True).items():
        setattr(driver, key, value)
    
    db.commit()
    db.refresh(driver)
    return driver

@router.post("/{driver_id}/photo")
async def upload_driver_photo(
    driver_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user = Depends(require_roles("admin", "manager"))
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    
    # Save file
    file_extension = os.path.splitext(file.filename)[1]
    filename = f"{driver_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    driver.profile_photo = file_path
    db.commit()
    
    return {"message": "Photo uploaded successfully", "path": file_path}

@router.delete("/{driver_id}")
async def delete_driver(
    driver_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_roles("admin"))
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    
    # Check for active assignments
    active = db.query(Assignment).filter(
        Assignment.driver_id == driver_id,
        Assignment.status == "active"
    ).first()
    
    if active:
        raise HTTPException(400, "Cannot delete driver with active assignment")
    
    db.delete(driver)
    db.commit()
    return {"message": "Driver deleted successfully"}

@router.post("/{driver_id}/documents")
async def upload_driver_document(
    driver_id: int,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: Session = Depends(get_db),
    user = Depends(require_roles("admin", "manager"))
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    
    # Save file
    file_extension = os.path.splitext(file.filename)[1]
    filename = f"doc_{driver_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    doc = DriverDocument(
        driver_id=driver_id,
        document_type=document_type,
        document_name=file.filename,
        file_path=file_path,
        file_size=len(file.file.read()),
        mime_type=file.content_type,
        uploaded_by=user.username
    )
    
    db.add(doc)
    db.commit()
    
    return {"message": "Document uploaded successfully", "document": doc.id}