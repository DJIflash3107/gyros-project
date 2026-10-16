from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

IssueSeverity = Literal["info", "warning", "error", "critical"]
ResolutionStatus = Literal["open", "resolved", "ignored"]


class ImportIssueCreate(BaseModel):
    staging_row_id: Optional[int] = None
    source_row_number: Optional[int] = None
    field_name: Optional[str] = Field(default=None, max_length=100)
    issue_code: str = Field(..., min_length=1, max_length=60)
    severity: IssueSeverity
    message: str = Field(..., min_length=1, max_length=1000)
    raw_value: Optional[str] = None
    resolution_status: ResolutionStatus = "open"


class ImportIssueUpdate(BaseModel):
    resolution_status: Optional[ResolutionStatus] = None
    resolved_by_user_id: Optional[int] = None


class ImportIssueResponse(BaseModel):
    id: int
    submission_id: int
    staging_row_id: Optional[int] = None
    source_row_number: Optional[int] = None
    field_name: Optional[str] = None
    issue_code: str
    severity: str
    message: str
    raw_value: Optional[str] = None
    resolution_status: str
    resolved_by_user_id: Optional[int] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
