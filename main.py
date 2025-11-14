import os
import secrets
import time
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, Literal, List
from database import create_document, get_documents, db
from schemas import Lead, Retailer, Session, Order, OrderItem
from bson import ObjectId

app = FastAPI(title="LastDrop API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "LastDrop backend up"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "❌ Unknown"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

class LeadIn(BaseModel):
    name: str
    email: EmailStr
    role: Literal["retailer", "consumer", "other"] = "consumer"
    company: Optional[str] = None
    message: Optional[str] = None
    consent: bool = True

@app.post("/api/leads")
def create_lead(lead: LeadIn):
    try:
        lead_id = create_document("lead", lead.model_dump())
        return {"status": "ok", "id": lead_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------- Simple Auth for Retailers ----------------------

class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    company: Optional[str] = None
    contact_name: Optional[str] = None

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    token: str

SALT = "ld_static_salt_v1"  # In production, store a per-user salt + strong hashing

def hash_password(pw: str) -> str:
    import hashlib
    digest = hashlib.sha256((SALT + pw).encode()).hexdigest()
    return f"{SALT}${digest}"

@app.post("/api/auth/register")
def register(data: RegisterIn):
    # Check if exists
    existing = list(db["retailer"].find({"email": data.email})) if db else []
    if existing:
        raise HTTPException(status_code=400, detail="Account already exists")
    doc = Retailer(
        email=data.email,
        password_hash=hash_password(data.password),
        company=data.company,
        contact_name=data.contact_name,
    ).model_dump()
    rid = create_document("retailer", doc)
    return {"status": "ok", "id": rid}

@app.post("/api/auth/login", response_model=TokenOut)
def login(data: LoginIn):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    rec = db["retailer"].find_one({"email": data.email})
    if not rec or rec.get("password_hash") != hash_password(data.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_urlsafe(32)
    sess = Session(token=token, retailer_id=str(rec.get("_id")), expires_at=time.time()+60*60*24*7)
    create_document("session", sess.model_dump())
    return TokenOut(token=token)

# Dependency to get current retailer from Bearer token

def get_current_retailer(authorization: Optional[str] = Header(None)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    sess = db["session"].find_one({"token": token})
    if not sess or sess.get("expires_at", 0) < time.time():
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    retailer = db["retailer"].find_one({"_id": ObjectId(sess["retailer_id"])}) if ObjectId is not None else None
    if not retailer:
        raise HTTPException(status_code=401, detail="Retailer not found")
    return retailer

# ---------------------- Orders Endpoints (Retailer area) ----------------------

class OrderIn(BaseModel):
    order_number: str
    status: Literal["processing", "shipped", "completed", "cancelled"] = "processing"
    total_amount: float
    currency: str = "EUR"
    items: List[OrderItem] = []
    notes: Optional[str] = None

@app.get("/api/orders")
def list_orders(current=Depends(get_current_retailer)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    orders = list(db["order"].find({"retailer_id": str(current["_id"])}))
    for o in orders:
        o["_id"] = str(o["_id"])
    return {"orders": orders}

@app.post("/api/orders")
def create_order(data: OrderIn, current=Depends(get_current_retailer)):
    ord_doc = Order(
        retailer_id=str(current["_id"]),
        order_number=data.order_number,
        status=data.status,
        total_amount=data.total_amount,
        currency=data.currency,
        items=data.items,
        notes=data.notes,
    ).model_dump()
    oid = create_document("order", ord_doc)
    return {"status": "ok", "id": oid}

@app.put("/api/orders/{order_id}")
def update_order(order_id: str, data: OrderIn, current=Depends(get_current_retailer)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    db["order"].update_one({"_id": ObjectId(order_id), "retailer_id": str(current["_id"])}, {"$set": data.model_dump()})
    return {"status": "ok"}

@app.delete("/api/orders/{order_id}")
def delete_order(order_id: str, current=Depends(get_current_retailer)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    db["order"].delete_one({"_id": ObjectId(order_id), "retailer_id": str(current["_id"])})
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
