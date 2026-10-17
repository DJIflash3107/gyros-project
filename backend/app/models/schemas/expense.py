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


class ExpenseBatchCreate(BaseModel):
    items: list[ExpenseCreate] = Field(..., min_length=1, description="List of expense items to save in batch")


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


class ExpenseImportItem(BaseModel):
    source_row_number: Optional[int] = None
    branch_id: Optional[int] = None
    branch_name: Optional[str] = None
    expense_date: date
    category: str = Field(..., max_length=80)
    description: Optional[str] = Field(default=None, max_length=255)
    amount: Decimal = Field(..., ge=0)
    currency: str = Field(default="IDR", max_length=3)
    source_file_name: Optional[str] = None
    confidence: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)


class ExpenseImportSummary(BaseModel):
    total_extracted: int = 0
    total_saved: int = 0
    total_amount: Decimal = Decimal("0.00")
    categories_breakdown: dict[str, Decimal] = Field(default_factory=dict)
    file_name: Optional[str] = None
    input_method: str
    persisted: bool = True


class ExpenseImportResponse(BaseModel):
    summary: ExpenseImportSummary
    expenses: list[ExpenseResponse] = Field(default_factory=list)
    items: list[ExpenseImportItem] = Field(default_factory=list)
    issues: list[dict] = Field(default_factory=list)

