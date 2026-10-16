from datetime import date
from decimal import Decimal
from typing import Optional, List, Literal, Any
from pydantic import BaseModel, Field, model_validator

from app.models.schemas.sales_report_submission import (
    ReportPeriodType,
    SalesReportSubmissionResponse,
)
from app.models.schemas.sales_report_staging_row import Granularity
from app.models.schemas.import_issue import ImportIssueResponse


class ManualFormRowInput(BaseModel):
    raw_product_name: str = Field(..., min_length=1, max_length=180)
    branch_id: int
    product_id: Optional[int] = None
    period_start: date
    period_end: date
    granularity: Granularity
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

    @model_validator(mode="after")
    def validate_row_dates(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must be greater than or equal to period_start")
        return self


class ManualFormBatchCreate(BaseModel):
    report_period_type: ReportPeriodType
    coverage_start: date
    coverage_end: date
    branch_id: Optional[int] = None
    rows: List[ManualFormRowInput] = Field(..., min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.coverage_end < self.coverage_start:
            raise ValueError("coverage_end must be greater than or equal to coverage_start")
        return self


class ProcessingSummary(BaseModel):
    total_rows: int = 0
    ready_rows: int = 0
    pending_review_rows: int = 0
    needs_correction_rows: int = 0
    issue_count: int = 0


class ProcessingResultResponse(BaseModel):
    submission: SalesReportSubmissionResponse
    summary: ProcessingSummary
    issues: List[ImportIssueResponse] = []


# SSE Event Schemas for photo / streaming
ReportProcessingStep = Literal["uploading", "extracting", "validating", "staging", "complete", "failed"]


class ReportStatusEvent(BaseModel):
    step: ReportProcessingStep
    message: Optional[str] = None


class ExtractionProgressEvent(BaseModel):
    message: str


class ValidationResultEvent(BaseModel):
    total: int
    ready: int
    pending_review: int
    needs_correction: int
    errors: int


class ReportErrorEvent(BaseModel):
    error_code: str
    message: str


class ReportCompleteEvent(BaseModel):
    submission_id: int
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    summary: ProcessingSummary
