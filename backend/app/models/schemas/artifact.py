from datetime import datetime, date
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


ArtifactTypeLiteral = Literal["report", "plan", "file", "image"]
ReportFormatLiteral = Literal["csv", "xlsx", "pdf"]
ReportTypeLiteral = Literal[
    "sales_summary",
    "financial_summary",
    "inventory_status",
    "forecast_export",
    "promotion_summary",
    "action_center_summary",
]
ImagePurposeLiteral = Literal[
    "product_catalog",
    "promotional_poster",
    "promotion_visual",
]
ImageOrientationLiteral = Literal["square", "portrait", "landscape"]
ArtifactStatusLiteral = Literal["pending", "generating", "ready", "failed"]


# Request Schemas
class GenerateReportRequest(BaseModel):
    report_type: ReportTypeLiteral
    file_format: ReportFormatLiteral = "xlsx"
    branch_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    title: Optional[str] = Field(None, max_length=255)
    parameters: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_dates(self) -> "GenerateReportRequest":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        return self


class GeneratePlanArtifactRequest(BaseModel):
    source_plan_id: int
    file_format: ReportFormatLiteral = "pdf"
    title: Optional[str] = Field(None, max_length=255)
    include_financials: bool = True
    include_schedule: bool = True


# Disallowed keywords for image generation (safety / off-topic filter)
OFF_TOPIC_KEYWORDS = {
    "weapon", "gun", "knife", "violence", "blood", "kill", "nude", "naked",
    "porn", "nsfw", "celebrity", "politician", "crypto", "casino", "gambling",
    "hate", "racist", "drugs", "illegal", "zombie", "monster", "war", "military"
}

# Positive business-context keywords (at least some relevance to F&B business is expected)
FB_BUSINESS_KEYWORDS = [
    "food", "beverage", "drink", "coffee", "tea", "menu", "restaurant", "cafe",
    "culinary", "dish", "meal", "snack", "dessert", "product", "catalog", "promo",
    "poster", "discount", "offer", "special", "combo", "bakery", "kitchen", "delicious",
    "fresh", "taste", "flavor", "bottle", "cup", "packaging", "plate", "bowl", "boba",
    "burger", "pizza", "noodles", "rice", "fried", "grill", "juice", "shake", "cake",
    "pastry", "breakfast", "lunch", "dinner", "catering", "bistro", "eatery", "sale",
    "deal", "voucher", "event", "ramadan", "holiday", "weekend", "barista", "chef",
    "toast", "sandwich", "chicken", "beef", "seafood", "soup", "salad", "ice cream"
]


class GenerateImageRequest(BaseModel):
    purpose: ImagePurposeLiteral
    prompt: str = Field(..., min_length=10, max_length=1000)
    negative_prompt: Optional[str] = Field(None, max_length=500)
    orientation: ImageOrientationLiteral = "square"
    product_id: Optional[int] = None
    promotion_plan_id: Optional[int] = None
    title: Optional[str] = Field(None, max_length=255)
    style: Optional[str] = Field(None, max_length=50)

    @field_validator("prompt")
    @classmethod
    def validate_business_prompt(cls, v: str) -> str:
        prompt_lower = v.lower()
        # Check off-topic / policy violations
        for word in OFF_TOPIC_KEYWORDS:
            if word in prompt_lower:
                raise ValueError(f"Prompt contains disallowed content: '{word}'")

        # Check for F&B business relevance
        has_fb_keyword = any(kw in prompt_lower for kw in FB_BUSINESS_KEYWORDS)
        if not has_fb_keyword:
            raise ValueError(
                "Prompt must be relevant to food & beverage business (e.g. food, drinks, restaurant, menu, promotional poster, product catalog)"
            )
        return v.strip()


class ArtifactFilterParams(BaseModel):
    artifact_type: Optional[ArtifactTypeLiteral] = None
    file_format: Optional[str] = None
    purpose: Optional[str] = None
    status: Optional[ArtifactStatusLiteral] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)


# Response Schemas
class ArtifactResponse(BaseModel):
    id: int
    business_id: int
    title: str
    artifact_type: str
    file_format: str
    storage_backend: str
    file_size_bytes: int
    mime_type: str
    sha256_hash: Optional[str] = None
    purpose: Optional[str] = None
    source_entity_type: Optional[str] = None
    source_entity_id: Optional[int] = None
    generation_params: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    status: str
    error_message: Optional[str] = None
    created_by_user_id: Optional[int] = None
    expires_at: Optional[datetime] = None
    download_count: int = 0
    last_downloaded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    download_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DownloadUrlResponse(BaseModel):
    artifact_id: int
    download_url: str
    expires_in_seconds: int
    file_name: str
    mime_type: str
    file_size_bytes: int
