from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class BackgroundJobResponse(BaseModel):
    id: int
    business_id: int
    job_type: str
    status: str
    progress: Optional[dict[str, Any]] = None
    progress_version: int = 0
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

