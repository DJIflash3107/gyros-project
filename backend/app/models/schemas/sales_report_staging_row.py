from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

ReviewStatus = Literal["pending_review", "needs_correction", "ready", "accepted", "rejected"]
Granularity = Literal["daily", "weekly", "monthly", "custom_range"]


class SalesReportStagingRowCreate(BaseModel):
    source_row_number: Optional[int] = None
    source_sheet_name: Optional[str] = None
    source_image_index: Optional[int] = None
    source_image_name: Optional[str] = None
    raw_payload_json: Any
    raw_product_name: Optional[str] = Field(default=None, max_length=180)
    branch_id: Optional[int] = None
    product_id: Optional[int] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    granularity: Optional[Granularity] = None
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
    extraction_confidence_json: Optional[Any] = None
    review_status: ReviewStatus = "pending_review"
    review_notes: Optional[str] = None


class SalesReportStagingRowUpdate(BaseModel):
    source_sheet_name: Optional[str] = None
    source_image_index: Optional[int] = None
    source_image_name: Optional[str] = None
    raw_product_name: Optional[str] = Field(default=None, max_length=180)
    branch_id: Optional[int] = None
    product_id: Optional[int] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    granularity: Optional[Granularity] = None
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
    extraction_confidence_json: Optional[Any] = None
    review_status: Optional[ReviewStatus] = None
    review_notes: Optional[str] = None


class SalesReportStagingRowBulkUpdate(BaseModel):
    row_ids: Optional[list[int]] = None
    apply_to_all: bool = False
    filter_review_status: Optional[ReviewStatus] = None
    review_status: Optional[ReviewStatus] = None
    review_notes: Optional[str] = None
    branch_id: Optional[int] = None
    product_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_bulk_params(self):
        if not self.apply_to_all and not self.row_ids:
            raise ValueError("Either 'apply_to_all' must be True or 'row_ids' must contain at least one ID.")
        if (
            self.review_status is None
            and self.review_notes is None
            and self.branch_id is None
            and self.product_id is None
        ):
            raise ValueError("At least one field to update must be provided.")
        return self


class SalesReportStagingRowResponse(BaseModel):
    id: int
    submission_id: int
    source_row_number: Optional[int] = None
    source_sheet_name: Optional[str] = None
    source_image_index: Optional[int] = None
    source_image_name: Optional[str] = None
    raw_payload_json: Any
    raw_product_name: Optional[str] = None
    branch_id: Optional[int] = None
    product_id: Optional[int] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    granularity: Optional[str] = None
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
    extraction_confidence_json: Optional[Any] = None
    review_status: str
    review_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
