from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

ObservationGranularity = Literal["daily", "weekly", "monthly", "custom_range"]
RecordStatus = Literal["active", "superseded", "cancelled"]


class SalesReportObservationCreate(BaseModel):
    branch_id: int
    product_id: int
    source_submission_id: int
    source_staging_row_id: Optional[int] = None
    period_start: date
    period_end: date
    granularity: ObservationGranularity
    prepared_qty: Optional[Decimal] = None
    opening_stock_qty: Optional[Decimal] = None
    received_qty: Optional[Decimal] = None
    available_stock_qty: Optional[Decimal] = None
    sold_qty: Optional[Decimal] = None
    leftover_qty: Optional[Decimal] = None
    spoiled_qty: Optional[Decimal] = None
    damaged_qty: Optional[Decimal] = None
    staff_meals_qty: Optional[Decimal] = None
    donated_qty: Optional[Decimal] = None
    other_disposition_qty: Optional[Decimal] = None
    recorded_revenue: Optional[Decimal] = None
    record_status: RecordStatus = "active"

    @model_validator(mode="after")
    def validate_dates(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must be greater than or equal to period_start")
        return self


class SalesReportObservationUpdate(BaseModel):
    prepared_qty: Optional[Decimal] = None
    opening_stock_qty: Optional[Decimal] = None
    received_qty: Optional[Decimal] = None
    available_stock_qty: Optional[Decimal] = None
    sold_qty: Optional[Decimal] = None
    leftover_qty: Optional[Decimal] = None
    spoiled_qty: Optional[Decimal] = None
    damaged_qty: Optional[Decimal] = None
    staff_meals_qty: Optional[Decimal] = None
    donated_qty: Optional[Decimal] = None
    other_disposition_qty: Optional[Decimal] = None
    recorded_revenue: Optional[Decimal] = None
    record_status: Optional[RecordStatus] = None


class SalesReportObservationResponse(BaseModel):
    id: int
    business_id: int
    branch_id: int
    product_id: int
    source_submission_id: int
    source_staging_row_id: Optional[int] = None
    period_start: date
    period_end: date
    granularity: str
    prepared_qty: Optional[Decimal] = None
    opening_stock_qty: Optional[Decimal] = None
    received_qty: Optional[Decimal] = None
    available_stock_qty: Optional[Decimal] = None
    sold_qty: Optional[Decimal] = None
    leftover_qty: Optional[Decimal] = None
    spoiled_qty: Optional[Decimal] = None
    damaged_qty: Optional[Decimal] = None
    staff_meals_qty: Optional[Decimal] = None
    donated_qty: Optional[Decimal] = None
    other_disposition_qty: Optional[Decimal] = None
    recorded_revenue: Optional[Decimal] = None
    record_status: str
    created_by_user_id: Optional[int] = None
    updated_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
