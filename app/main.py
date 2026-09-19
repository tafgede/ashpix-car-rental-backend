from datetime import date, timedelta
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from .database import Base, engine, get_db
from .models import User, Driver, Vehicle, Assignment, WeeklyObligation, Payment, AuditLog
from .schemas import LoginRequest, DriverCreate, VehicleCreate, AssignmentCreate, PaymentCreate, UserCreate
from .auth import hash_password, verify_password, create_token, current_user, require_roles

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ashpix Car Rental Fleet Management", version="2.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])

def serialize(obj):
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k,v in d.items():
        if isinstance(v, (date,)):
            d[k] = v.isoformat()
    return d

def log(db, user, action):
    db.add(AuditLog(username=user.username, action=action))
    db.commit()

def monday(d):
    return d - timedelta(days=d.weekday())

def refresh_status(ob):
    ob.status = "paid" if ob.amount_paid >= ob.amount_due else ("partial" if ob.amount_paid > 0 else "unpaid")

@app.on_event("startup")
def seed():
    db = next(get_db())
    if not db.query(User).first():
        users = [
            ("admin", "admin123", "admin", "admin@ashpix.com", "System Administrator", "+263712345678"),
            ("manager", "manager123", "manager", "manager@ashpix.com", "Fleet Manager", "+263712345679"),
            ("accounts", "accounts123", "accounting", "accounts@ashpix.com", "Accounting Manager", "+263712345680"),
        ]
        for username, password, role, email, full_name, phone in users:
            db.add(User(
                username=username,
                password_hash=hash_password(password),
                role=role,
                email=email,
                full_name=full_name,
                phone=phone,
                is_active=1
            ))
        db.commit()
        print("✅ Ashpix Car Rental default users created!")
    db.close()

@app.get("/")
def root():
    return {"app":"Ashpix Car Rental Fleet Management","status":"running","version":"2.0"}

@app.post("/api/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == data.username).first()
    if not u or not verify_password(data.password, u.password_hash):
        raise HTTPException(401, "Incorrect username or password")
    return {"access_token": create_token(u), "token_type":"bearer",
            "user":{"username":u.username,"role":u.role, "full_name": u.full_name}}

@app.get("/api/me")
def me(user=Depends(current_user)):
    return {"username":user.username,"role":user.role, "full_name": user.full_name}

@app.get("/api/dashboard")
def dashboard(db: Session=Depends(get_db), user=Depends(current_user)):
    is_fin = user.role in ("admin","accounting")
    data = {
        "drivers": db.query(Driver).count(),
        "active_drivers": db.query(Driver).filter(Driver.status=="active").count(),
        "vehicles": db.query(Vehicle).count(),
        "active_vehicles": db.query(Vehicle).filter(Vehicle.status=="active").count(),
        "available_vehicles": db.query(Vehicle).filter(Vehicle.status=="available").count(),
        "repair_vehicles": db.query(Vehicle).filter(Vehicle.status=="repair").count(),
    }
    if is_fin:
        start=monday(date.today())
        obs=db.query(WeeklyObligation).filter(WeeklyObligation.week_start==start).all()
        data["weekly_due"]=sum(x.amount_due for x in obs)
        data["weekly_paid"]=sum(x.amount_paid for x in obs)
        data["weekly_outstanding"]=sum(max(0,x.amount_due-x.amount_paid) for x in obs)
        data["paid_drivers"]=sum(1 for x in obs if x.status=="paid")
        data["partial_drivers"]=sum(1 for x in obs if x.status=="partial")
        data["unpaid_drivers"]=sum(1 for x in obs if x.status=="unpaid")
    return data

@app.get("/api/drivers")
def drivers(db:Session=Depends(get_db), user=Depends(current_user)):
    result=[]
    for d in db.query(Driver).order_by(Driver.name).all():
        item=serialize(d)
        if user.role=="manager":
            item.pop("weekly_cash_in", None)
        paid=sum(p.amount for p in d.payments)
        due=sum(o.amount_due for o in d.obligations)
        item["assigned_vehicle"] = None
        a=db.query(Assignment).filter(Assignment.driver_id==d.id, Assignment.end_date==None).first()
        if a: item["assigned_vehicle"]=a.vehicle.registration
        if user.role in ("admin","accounting"):
            item["total_due"]=due
            item["total_paid"]=paid
            item["balance"]=max(0,due-paid)
        result.append(item)
    return result

@app.post("/api/drivers")
def create_driver(data:DriverCreate, db:Session=Depends(get_db), user=Depends(require_roles("admin", "manager"))):
    count=db.query(Driver).count()+1
    d=Driver(driver_code=f"DRV-{count:04d}", joined_date=data.joined_date or date.today(), **data.model_dump(exclude={"joined_date"}))
    db.add(d); db.commit(); db.refresh(d)
    start=monday(d.joined_date)
    db.add(WeeklyObligation(driver_id=d.id, week_start=start, week_end=start+timedelta(days=6), amount_due=d.weekly_cash_in))
    db.commit(); log(db,user,f"Created driver {d.driver_code}")
    return serialize(d)

@app.get("/api/vehicles")
def vehicles(db:Session=Depends(get_db), user=Depends(current_user)):
    result=[]
    for v in db.query(Vehicle).order_by(Vehicle.registration).all():
        item=serialize(v)
        a=db.query(Assignment).filter(Assignment.vehicle_id==v.id, Assignment.end_date==None).first()
        item["assigned_driver"]=a.driver.name if a else None
        result.append(item)
    return result

@app.post("/api/vehicles")
def create_vehicle(data:VehicleCreate, db:Session=Depends(get_db), user=Depends(require_roles("admin", "manager"))):
    v=Vehicle(**data.model_dump())
    db.add(v); db.commit(); db.refresh(v); log(db,user,f"Created vehicle {v.registration}")
    return serialize(v)

@app.get("/api/assignments")
def assignments(db:Session=Depends(get_db), user=Depends(current_user)):
    return [{
        **serialize(a),
        "driver_name":a.driver.name,
        "vehicle_registration":a.vehicle.registration
    } for a in db.query(Assignment).order_by(Assignment.start_date.desc()).all()]

@app.post("/api/assignments")
def create_assignment(data:AssignmentCreate, db:Session=Depends(get_db), user=Depends(require_roles("admin","manager"))):
    old=db.query(Assignment).filter(Assignment.vehicle_id==data.vehicle_id, Assignment.end_date==None).first()
    if old: old.end_date=date.today()
    old2=db.query(Assignment).filter(Assignment.driver_id==data.driver_id, Assignment.end_date==None).first()
    if old2: old2.end_date=date.today()
    a=Assignment(**data.model_dump(), start_date=data.start_date or date.today())
    db.add(a)
    v=db.get(Vehicle,data.vehicle_id)
    if v: v.status="active"
    db.commit(); log(db,user,f"Assigned driver {data.driver_id} to vehicle {data.vehicle_id}")
    return serialize(a)

@app.get("/api/cash")
def cash(db:Session=Depends(get_db), user=Depends(require_roles("admin","accounting"))):
    start=monday(date.today()); end=start+timedelta(days=6)
    for d in db.query(Driver).all():
        if not db.query(WeeklyObligation).filter_by(driver_id=d.id,week_start=start).first():
            db.add(WeeklyObligation(driver_id=d.id,week_start=start,week_end=end,amount_due=d.weekly_cash_in))
    db.commit()
    obs=db.query(WeeklyObligation).filter(WeeklyObligation.week_start==start).all()
    return [{
        **serialize(o),
        "driver_name":o.driver.name,
        "balance":max(0,o.amount_due-o.amount_paid)
    } for o in obs]

@app.post("/api/payments")
def payment(data:PaymentCreate, db:Session=Depends(get_db), user=Depends(require_roles("admin","accounting"))):
    if data.amount <= 0: raise HTTPException(400,"Payment must be greater than zero")
    p=Payment(**data.model_dump(), payment_date=data.payment_date or date.today(), recorded_by=user.username)
    db.add(p)
    remaining=data.amount
    obs=db.query(WeeklyObligation).filter(WeeklyObligation.driver_id==data.driver_id).order_by(WeeklyObligation.week_start).all()
    for o in obs:
        outstanding=max(0,o.amount_due-o.amount_paid)
        if outstanding>0 and remaining>0:
            applied=min(outstanding,remaining)
            o.amount_paid += applied
            refresh_status(o)
            remaining -= applied
    db.commit(); log(db,user,f"Recorded payment of {data.amount} for driver {data.driver_id}")
    return serialize(p)

@app.get("/api/payments")
def payments(db:Session=Depends(get_db), user=Depends(require_roles("admin","accounting"))):
    return [{**serialize(p),"driver_name":p.driver.name} for p in db.query(Payment).order_by(Payment.payment_date.desc()).all()]

@app.get("/api/reports/driver/{driver_id}")
def driver_report(driver_id:int, db:Session=Depends(get_db), user=Depends(require_roles("admin","accounting"))):
    d=db.get(Driver,driver_id)
    if not d: raise HTTPException(404,"Driver not found")
    return {"driver":serialize(d),
            "obligations":[serialize(o) for o in d.obligations],
            "payments":[serialize(p) for p in d.payments],
            "balance":max(0,sum(o.amount_due for o in d.obligations)-sum(p.amount for p in d.payments))}

@app.get("/api/users")
def users(db:Session=Depends(get_db), user=Depends(require_roles("admin"))):
    return [{"id":u.id,"username":u.username,"role":u.role,"is_active":bool(u.is_active), "full_name": u.full_name, "email": u.email} for u in db.query(User).all()]

@app.post("/api/users")
def create_user(data:UserCreate, db:Session=Depends(get_db), user=Depends(require_roles("admin"))):
    if data.role not in ("admin","manager","accounting"): raise HTTPException(400,"Invalid role")
    if db.query(User).filter(User.username==data.username).first(): raise HTTPException(400,"Username already exists")
    u=User(username=data.username, password_hash=hash_password(data.password), role=data.role, email=data.email, full_name=data.full_name, phone=data.phone or "")
    db.add(u); db.commit(); db.refresh(u); log(db,user,f"Created user {u.username}")
    return {"id":u.id,"username":u.username,"role":u.role}