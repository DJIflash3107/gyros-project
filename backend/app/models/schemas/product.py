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
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
