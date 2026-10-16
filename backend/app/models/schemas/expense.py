from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ExpenseCreate(BaseModel):
    branch_id: Optional[int] = None
    expense_date: date
    category: str = Field(..., min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=255)
    amount: Decimal = Field(..., ge=0)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    source_submission_id: Optional[int] = None
    source_row_number: Optional[int] = None


class ExpenseUpdate(BaseModel):
    branch_id: Optional[int] = None
    expense_date: Optional[date] = None
    category: Optional[str] = Field(default=None, min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=255)
    amount: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)


class ExpenseResponse(BaseModel):
    id: int
    business_id: int
    branch_id: Optional[int] = None
    expense_date: date
    category: str
    description: Optional[str] = None
    amount: Decimal
    currency: str
    source_submission_id: Optional[int] = None
    source_row_number: Optional[int] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
