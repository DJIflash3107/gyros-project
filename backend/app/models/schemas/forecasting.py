from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# Request Schemas
class ForecastRequest(BaseModel):
    business_id: Optional[int] = None
    branch_id: int
    product_id: int
    horizon_days: int = Field(default=7, ge=1, le=90)
    window_size: int = Field(default=7, ge=3, le=90)


class ForecastEvaluateRequest(BaseModel):
    business_id: Optional[int] = None
    branch_id: int
    product_id: int
    window_size: int = Field(default=7, ge=3, le=90)
    test_days: int = Field(default=7, ge=1, le=60)


# Response Schemas
class ForecastPointResponse(BaseModel):
    forecast_date: date
    predicted_qty: Decimal
    weekday: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ForecastRunResponse(BaseModel):
    id: int
    business_id: int
    branch_id: int
    product_id: int
    method: str
    horizon_days: int
    window_size: int
    training_start: Optional[date] = None
    training_end: Optional[date] = None
    observations_used: int
    is_reliable: bool
    reliability_note: Optional[str] = None
    mae: Optional[Decimal] = None
    wape: Optional[Decimal] = None
    forecast_bias: Optional[Decimal] = None
    predictions: List[ForecastPointResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActualVsPredicted(BaseModel):
    date: date
    actual: Decimal
    predicted: Decimal

    model_config = ConfigDict(from_attributes=True)


class EvaluationResponse(BaseModel):
    branch_id: int
    product_id: int
    method: str
    window_size: int
    test_days: int
    training_start: Optional[date] = None
    training_end: Optional[date] = None
    test_start: Optional[date] = None
    test_end: Optional[date] = None
    observations_used: int
    mae: Optional[Decimal] = None
    wape: Optional[Decimal] = None
    forecast_bias: Optional[Decimal] = None
    is_reliable: bool
    reliability_note: Optional[str] = None
    actuals_vs_predicted: List[ActualVsPredicted] = []

    model_config = ConfigDict(from_attributes=True)


class DataSufficiencyResponse(BaseModel):
    branch_id: int
    product_id: int
    total_observations: int
    daily_observations: int
    distinct_weekdays: int
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    supports_baseline: bool
    supports_weekday: bool
    message: str

    model_config = ConfigDict(from_attributes=True)
