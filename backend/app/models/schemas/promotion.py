from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator


# ---------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------

class PromotionItemInput(BaseModel):
    product_id: int = Field(..., gt=0, description="Product ID to include in promotion")
    discount_type: str = Field(
        ...,
        pattern="^(percentage|fixed_amount|bundle_price)$",
        description="Type of discount: percentage, fixed_amount, or bundle_price",
    )
    discount_value: Decimal = Field(..., gt=0, description="Value of the discount")
    expected_qty: Optional[int] = Field(None, ge=1, description="Estimated units to sell during promotion")
    notes: Optional[str] = Field(None, max_length=255)

    @model_validator(mode="after")
    def validate_discount_value(self) -> "PromotionItemInput":
        if self.discount_type == "percentage" and self.discount_value > Decimal("100.00"):
            raise ValueError("Percentage discount cannot exceed 100%")
        return self


class GeneratePromotionRequest(BaseModel):
    business_id: Optional[int] = None
    branch_id: Optional[int] = None
    promotion_type: str = Field(
        default="discount",
        pattern="^(discount|bundle|time_limited|bogo)$",
        description="Type of promotion: discount, bundle, time_limited, bogo",
    )
    start_date: date
    end_date: date
    items: List[PromotionItemInput] = Field(..., min_length=1, description="At least one promotion item is required")
    min_margin_pct: Optional[Decimal] = Field(
        None, ge=Decimal("0.0"), le=Decimal("100.0"), description="Configurable minimum acceptable margin percentage"
    )
    persist: bool = Field(default=True, description="Whether to persist the generated plan into the database")

    @model_validator(mode="after")
    def validate_date_range(self) -> "GeneratePromotionRequest":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be strictly after start_date")
        return self


class UpdatePromotionStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected|archived|draft)$")
    rejected_reason: Optional[str] = Field(None, max_length=500)

    @model_validator(mode="after")
    def validate_rejection_reason(self) -> "UpdatePromotionStatusRequest":
        if self.status == "rejected" and (not self.rejected_reason or not self.rejected_reason.strip()):
            raise ValueError("rejected_reason is required when rejecting a promotion plan")
        return self


class EvaluatePromotionRequest(BaseModel):
    business_id: Optional[int] = None
    min_margin_pct: Optional[Decimal] = Field(
        None, ge=Decimal("0.0"), le=Decimal("100.0"), description="Optional override for minimum acceptable margin"
    )


# ---------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------

class PromotionItemResponse(BaseModel):
    product_id: int
    product_name: str
    discount_type: str
    discount_value: Decimal
    original_price: Optional[Decimal] = None
    discounted_price: Optional[Decimal] = None
    unit_cost: Optional[Decimal] = None
    margin_per_unit: Optional[Decimal] = None
    margin_pct: Optional[Decimal] = None
    expected_qty: Optional[int] = None
    estimated_contribution: Optional[Decimal] = None
    cost_data_available: bool = False
    price_data_available: bool = True
    warnings: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PromotionPlanResponse(BaseModel):
    id: int
    business_id: int
    title: str
    promotion_type: str
    status: str
    branch_id: Optional[int] = None
    start_date: date
    end_date: date
    items: List[PromotionItemResponse]
    total_original_revenue: Optional[Decimal] = None
    total_discounted_revenue: Optional[Decimal] = None
    total_estimated_cost: Optional[Decimal] = None
    total_estimated_margin: Optional[Decimal] = None
    avg_margin_pct: Optional[Decimal] = None
    is_financially_validated: bool = False
    min_margin_pct: Optional[Decimal] = None
    warnings: Optional[List[str]] = None
    assumptions: Optional[List[str]] = None
    missing_data: Optional[List[str]] = None
    risks: Optional[List[str]] = None
    rationale: Optional[str] = None
    recommended_actions: Optional[List[str]] = None
    created_by_user_id: Optional[int] = None
    updated_by_user_id: Optional[int] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    rejected_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GeneratePromotionResponse(BaseModel):
    plan: PromotionPlanResponse
    data_summary: Dict[str, Any]
