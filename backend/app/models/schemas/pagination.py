from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number, starting from 1")
    page_size: int = Field(default=20, ge=1, le=100, description="Number of items per page")


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int
