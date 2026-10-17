from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.models.user import User
from app.models.business_membership import BusinessMembership
from app.models.schemas.business_action import (
    GenerateActionsRequest,
    UpdateActionStatusRequest,
)
from app.middlewares.auth import get_current_user, require_business_membership
from app.handlers import business_action_handler
from app.helpers.exceptions import ValidationException, AuthorizationException

# Primary router scoped by business
router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/business-actions",
    tags=["Business Actions"],
)

# Secondary router mounted under /api/v1/business-actions
direct_router = APIRouter(
    prefix="/api/v1/business-actions",
    tags=["Business Actions"],
)


def _verify_user_business_role(
    db: Session,
    user: User,
    business_id: int,
    allowed_roles: Optional[List[str]] = None,
) -> BusinessMembership:
    membership = db.query(BusinessMembership).filter(
        BusinessMembership.business_id == business_id,
        BusinessMembership.user_id == user.id,
    ).first()
    if not membership:
        raise AuthorizationException(
            message="Access denied",
            errors={"authorization": "You are not a member of this business"},
        )
    if allowed_roles and membership.role not in allowed_roles:
        raise AuthorizationException(
            message="Access denied",
            errors={"authorization": f"Role '{membership.role}' does not have sufficient permissions"},
        )
    return membership


# ---------------------------------------------------------
# Primary Business-Scoped Endpoints
# ---------------------------------------------------------

@router.post(
    "/generate",
    status_code=200,
    dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))],
)
async def generate_actions(
    business_id: int,
    data: GenerateActionsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate and rank actionable recommendations based on business data."""
    return await business_action_handler.generate_actions_handler(business_id, data, current_user, db)


@router.get("", dependencies=[Depends(require_business_membership())])
@router.get("/", dependencies=[Depends(require_business_membership())], include_in_schema=False)
def list_actions(
    business_id: int,
    status: Optional[str] = Query(None, description="Filter by status (open, in_progress, implemented, dismissed, archived)"),
    category: Optional[str] = Query(None, description="Filter by category (inventory, sales, demand_forecasting, expenses, general)"),
    urgency: Optional[str] = Query(None, description="Filter by urgency (critical, high, medium, low)"),
    evidence_quality: Optional[str] = Query(None, description="Filter by evidence quality (measured, estimated, mixed)"),
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    min_priority: Optional[Decimal] = Query(None, description="Filter by minimum priority score"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List and filter recommendations for the business."""
    filter_params = {
        "status": status,
        "category": category,
        "urgency": urgency,
        "evidence_quality": evidence_quality,
        "branch_id": branch_id,
        "product_id": product_id,
        "min_priority": min_priority,
        "page": page,
        "page_size": page_size,
    }
    return business_action_handler.list_actions_handler(business_id, filter_params, db)


@router.get("/{action_id}", dependencies=[Depends(require_business_membership())])
def get_action_detail(
    business_id: int,
    action_id: int,
    db: Session = Depends(get_db),
):
    """Get recommendation details by ID."""
    return business_action_handler.get_action_handler(business_id, action_id, db)


@router.patch(
    "/{action_id}/status",
    status_code=200,
    dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))],
)
def update_action_status(
    business_id: int,
    action_id: int,
    data: UpdateActionStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update recommendation status (in_progress, implemented, dismissed, archived)."""
    return business_action_handler.update_action_status_handler(
        business_id, action_id, data, current_user, db
    )


# ---------------------------------------------------------
# Direct /api/v1/business-actions Endpoints
# ---------------------------------------------------------

@direct_router.post("/generate", status_code=200)
async def direct_generate_actions(
    data: GenerateActionsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate recommendations via direct endpoint under /api/v1/business-actions/."""
    if not data.business_id:
        raise ValidationException(
            errors={"business_id": "business_id is required in request body when calling direct action center endpoint"}
        )
    _verify_user_business_role(db, current_user, data.business_id, ["owner", "admin", "manager"])
    return await business_action_handler.generate_actions_handler(data.business_id, data, current_user, db)


@direct_router.get("")
@direct_router.get("/", include_in_schema=False)
def direct_list_actions(
    business_id: int = Query(..., description="Business ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    urgency: Optional[str] = Query(None, description="Filter by urgency"),
    evidence_quality: Optional[str] = Query(None, description="Filter by evidence quality"),
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    min_priority: Optional[Decimal] = Query(None, description="Filter by minimum priority score"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List recommendations via direct endpoint under /api/v1/business-actions/."""
    _verify_user_business_role(db, current_user, business_id)
    filter_params = {
        "status": status,
        "category": category,
        "urgency": urgency,
        "evidence_quality": evidence_quality,
        "branch_id": branch_id,
        "product_id": product_id,
        "min_priority": min_priority,
        "page": page,
        "page_size": page_size,
    }
    return business_action_handler.list_actions_handler(business_id, filter_params, db)


@direct_router.get("/{action_id}")
def direct_get_action(
    action_id: int,
    business_id: int = Query(..., description="Business ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get recommendation detail via direct endpoint under /api/v1/business-actions/."""
    _verify_user_business_role(db, current_user, business_id)
    return business_action_handler.get_action_handler(business_id, action_id, db)


@direct_router.patch("/{action_id}/status", status_code=200)
def direct_update_action_status(
    action_id: int,
    data: UpdateActionStatusRequest,
    business_id: int = Query(..., description="Business ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update recommendation status via direct endpoint under /api/v1/business-actions/."""
    _verify_user_business_role(db, current_user, business_id, ["owner", "admin", "manager"])
    return business_action_handler.update_action_status_handler(
        business_id, action_id, data, current_user, db
    )
