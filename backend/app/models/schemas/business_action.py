from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# Request Schemas
class GenerateActionsRequest(BaseModel):
    business_id: Optional[int] = None
    branch_id: Optional[int] = None
    product_id: Optional[int] = None
    categories: Optional[List[str]] = None
    lookback_days: int = Field(default=30, ge=7, le=365)
    persist: bool = Field(default=True)


class UpdateActionStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(in_progress|implemented|dismissed|archived)$")
    dismissed_reason: Optional[str] = Field(None, max_length=255)


# Response Schemas
class BusinessActionResponse(BaseModel):
    id: int
    business_id: int
    action_type: str
    rule_label: str
    category: str
    title: str
    ai_generated: bool = Field(default=True)
    urgency: str
    expected_impact: str
    priority_score: Decimal
    status: str
    evidence_quality: str
    rationale: str
    supporting_data: Optional[Dict[str, Any]] = None
    recommended_steps: Optional[List[str]] = None
    risks: Optional[List[str]] = None
    success_metrics: Optional[List[str]] = None
    limitations: Optional[str] = None
    dismissed_reason: Optional[str] = None
    branch_id: Optional[int] = None
    product_id: Optional[int] = None
    forecast_run_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    updated_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GenerateActionsResponse(BaseModel):
    generated_count: int
    persisted_count: int
    actions: List[BusinessActionResponse]
    data_summary: Dict[str, Any]
