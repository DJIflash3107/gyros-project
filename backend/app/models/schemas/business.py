from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class BusinessCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    timezone: str = Field(default="Asia/Jakarta", min_length=1, max_length=64)


class BusinessUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    timezone: Optional[str] = Field(default=None, min_length=1, max_length=64)


class BusinessResponse(BaseModel):
    id: int
    name: str
    currency: str
    timezone: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
