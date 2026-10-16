from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class ProductAliasCreate(BaseModel):
    product_id: int
    alias_name: str = Field(..., min_length=1, max_length=150)
    normalized_alias: Optional[str] = Field(default=None, max_length=180)

    @model_validator(mode="after")
    def populate_normalized_alias(self):
        if not self.normalized_alias:
            self.normalized_alias = self.alias_name.strip().lower()
        return self


class ProductAliasUpdate(BaseModel):
    alias_name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    normalized_alias: Optional[str] = Field(default=None, max_length=180)


class ProductAliasResponse(BaseModel):
    id: int
    business_id: int
    product_id: int
    alias_name: str
    normalized_alias: str
    created_by_user_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
