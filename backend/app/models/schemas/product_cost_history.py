from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class ProductCostHistoryCreate(BaseModel):
    product_id: int
    effective_from: date
    effective_to: Optional[date] = None
    unit_cost: Decimal = Field(..., ge=0)
    cost_unit: str = Field(..., min_length=1, max_length=20)
    source_submission_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be strictly greater than effective_from")
        return self


class ProductCostHistoryUpdate(BaseModel):
    effective_to: Optional[date] = None
    unit_cost: Optional[Decimal] = Field(default=None, ge=0)
    cost_unit: Optional[str] = Field(default=None, min_length=1, max_length=20)


class ProductCostHistoryResponse(BaseModel):
    id: int
    business_id: int
    product_id: int
    effective_from: date
    effective_to: Optional[date] = None
    unit_cost: Decimal
    cost_unit: str
    source_submission_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
