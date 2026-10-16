from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class BranchCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    branch_code: Optional[str] = Field(default=None, max_length=40)
    address: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = True


class BranchUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    branch_code: Optional[str] = Field(default=None, max_length=40)
    address: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None


class BranchResponse(BaseModel):
    id: int
    business_id: int
    name: str
    branch_code: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
