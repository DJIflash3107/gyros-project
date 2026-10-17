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
    status: str = "active"
    auto_created_from: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BranchDraftResponse(BaseModel):
    """Returned when a branch is auto-created as draft during import."""
    id: int
    business_id: int
    name: str
    status: str = "draft"
    missing_fields: list[str] = []
    auto_created_from: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BranchActivate(BaseModel):
    """User fills missing fields to activate a draft branch."""
    branch_code: Optional[str] = Field(default=None, max_length=40)
    address: Optional[str] = Field(default=None, max_length=255)
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)

