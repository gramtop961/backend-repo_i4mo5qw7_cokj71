"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Literal, List, Dict, Any

# Example schemas (replace with your own):

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Add your own schemas here:
# --------------------------------------------------

class Lead(BaseModel):
    """
    Leads captured from the landing page contact form.
    Collection name: "lead"
    """
    name: str = Field(..., description="Full name of the contact")
    email: EmailStr = Field(..., description="Contact email")
    role: Literal["retailer", "consumer", "other"] = Field("consumer", description="Self-identified role")
    company: Optional[str] = Field(None, description="Company name if retailer")
    message: Optional[str] = Field(None, description="Additional context or message")
    consent: bool = Field(True, description="Agreed to be contacted back")

class Retailer(BaseModel):
    """
    Retailer accounts for professional access.
    Collection name: "retailer"
    """
    email: EmailStr = Field(..., description="Login email")
    password_hash: str = Field(..., description="Password hash with salt, format: salt$hash")
    company: Optional[str] = Field(None, description="Company name")
    contact_name: Optional[str] = Field(None, description="Primary contact")
    role: Literal["retailer"] = Field("retailer", description="Account role")

class Session(BaseModel):
    """
    Session tokens for simple auth.
    Collection name: "session"
    """
    token: str = Field(..., description="Bearer token")
    retailer_id: str = Field(..., description="Retailer document id")
    expires_at: float = Field(..., description="Unix timestamp expiry")

class OrderItem(BaseModel):
    sku: str
    title: str
    qty: int
    price: float

class Order(BaseModel):
    """
    Orders belonging to a retailer.
    Collection name: "order"
    """
    retailer_id: str = Field(..., description="Retailer document id")
    order_number: str = Field(..., description="Human readable order number")
    status: Literal["processing", "shipped", "completed", "cancelled"] = Field("processing")
    total_amount: float
    currency: str = Field("EUR")
    items: List[OrderItem] = Field(default_factory=list)
    notes: Optional[str] = None
