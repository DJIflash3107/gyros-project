from datetime import datetime, date
from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

InputMethod = Literal["spreadsheet", "form", "photo"]
ReportPeriodType = Literal["daily", "weekly", "monthly", "custom_range"]
SubmissionStatus = Literal["pending", "processing", "reviewed", "confirmed", "rejected", "failed"]


class SalesReportSubmissionCreate(BaseModel):
    branch_id: Optional[int] = None
    input_method: InputMethod
    report_period_type: ReportPeriodType
    coverage_start: date
    coverage_end: date
    source_file_name: Optional[str] = Field(default=None, max_length=255)
    source_mime_type: Optional[str] = Field(default=None, max_length=100)
    source_storage_key: Optional[str] = Field(default=None, max_length=512)
    source_sha256: Optional[str] = Field(default=None, min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.coverage_end < self.coverage_start:
            raise ValueError("coverage_end must be greater than or equal to coverage_start")
        return self


class SalesReportSubmissionUpdate(BaseModel):
    branch_id: Optional[int] = None
    status: Optional[SubmissionStatus] = None
    total_rows: Optional[int] = None
    accepted_rows: Optional[int] = None
    rejected_rows: Optional[int] = None


class SalesReportSubmissionResponse(BaseModel):
    id: int
    business_id: int
    submitted_by_user_id: int
    branch_id: Optional[int] = None
    input_method: str
    report_period_type: str
    coverage_start: date
    coverage_end: date
    source_file_name: Optional[str] = None
    source_mime_type: Optional[str] = None
    source_sha256: Optional[str] = None
    status: str
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    confirmed_at: Optional[datetime] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
