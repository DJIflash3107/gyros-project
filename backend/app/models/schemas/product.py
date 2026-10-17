from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    sku: Optional[str] = Field(default=None, max_length=60)
    category: Optional[str] = Field(default=None, max_length=80)
    base_unit: str = Field(..., min_length=1, max_length=20)
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    sku: Optional[str] = Field(default=None, max_length=60)
    category: Optional[str] = Field(default=None, max_length=80)
    base_unit: Optional[str] = Field(default=None, min_length=1, max_length=20)
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    id: int
    business_id: int
    name: str
    sku: Optional[str] = None
    category: Optional[str] = None
    base_unit: str
    is_active: bool
    status: str = "active"
    auto_created_from: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductDraftResponse(BaseModel):
    """Returned when a product is auto-created as draft during import."""
    id: int
    business_id: int
    name: str
    status: str = "draft"
    missing_fields: list[str] = []
    auto_created_from: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProductActivate(BaseModel):
    """User fills missing fields to activate a draft product."""
    base_unit: str = Field(..., min_length=1, max_length=20)
    sku: Optional[str] = Field(default=None, max_length=60)
    category: Optional[str] = Field(default=None, max_length=80)
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)

