from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

MembershipRole = Literal["owner", "admin", "manager", "viewer"]


class BusinessMembershipCreate(BaseModel):
    user_id: int
    role: MembershipRole


class BusinessMembershipUpdate(BaseModel):
    role: Optional[MembershipRole] = None


class BusinessMembershipResponse(BaseModel):
    id: int
    business_id: int
    user_id: int
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
