from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.models.user import User
from app.models.business_membership import BusinessMembership
from app.models.schemas.promotion import (
    GeneratePromotionRequest,
    UpdatePromotionStatusRequest,
    EvaluatePromotionRequest,
)
from app.middlewares.auth import get_current_user, require_business_membership
from app.handlers import promotion_handler
from app.helpers.exceptions import ValidationException, AuthorizationException

# Primary router scoped by business
router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/promotions",
    tags=["Promotions"],
)

# Secondary router mounted under /api/v1/promotions
direct_router = APIRouter(
    prefix="/api/v1/promotions",
    tags=["Promotions"],
)


def _verify_user_business_role(
    db: Session,
    user: User,
    business_id: int,
    allowed_roles: Optional[List[str]] = None,
) -> BusinessMembership:
    membership = (
        db.query(BusinessMembership)
        .filter(
            BusinessMembership.business_id == business_id,
            BusinessMembership.user_id == user.id,
        )
        .first()
    )
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
async def generate_promotion(
    business_id: int,
    data: GeneratePromotionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate structured promotional proposal with deterministic financial evaluation."""
    return await promotion_handler.generate_plan_handler(business_id, data, current_user, db)


@router.get("", dependencies=[Depends(require_business_membership())])
@router.get("/", dependencies=[Depends(require_business_membership())], include_in_schema=False)
def list_promotions(
    business_id: int,
    status: Optional[str] = Query(None, description="Filter by status (draft, approved, rejected, archived)"),
    promotion_type: Optional[str] = Query(None, description="Filter by promotion type (discount, bundle, time_limited, bogo)"),
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    start_after: Optional[date] = Query(None, description="Filter plans starting on or after date"),
    end_before: Optional[date] = Query(None, description="Filter plans ending on or before date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List promotion plans with pagination and filtering."""
    filter_params = {
        "status": status,
        "promotion_type": promotion_type,
        "branch_id": branch_id,
        "start_after": start_after,
        "end_before": end_before,
        "page": page,
        "page_size": page_size,
    }
    return promotion_handler.list_plans_handler(business_id, filter_params, db)


@router.get("/{plan_id}", dependencies=[Depends(require_business_membership())])
def get_promotion(
    business_id: int,
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed information for a promotion plan."""
    return promotion_handler.get_plan_handler(business_id, plan_id, db)


@router.patch(
    "/{plan_id}/status",
    status_code=200,
    dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))],
)
def update_promotion_status(
    business_id: int,
    plan_id: int,
    data: UpdatePromotionStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transition promotion plan status (approve, reject, archive, re-open)."""
    return promotion_handler.update_plan_status_handler(business_id, plan_id, data, current_user, db)


@router.post(
    "/{plan_id}/evaluate",
    status_code=200,
    dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))],
)
def evaluate_promotion(
    business_id: int,
    plan_id: int,
    data: EvaluatePromotionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-evaluate promotion plan financials against current cost and price data."""
    return promotion_handler.evaluate_plan_handler(business_id, plan_id, data, current_user, db)


# ---------------------------------------------------------
# Direct /api/v1/promotions Endpoints
# ---------------------------------------------------------

@direct_router.post("/generate", status_code=200)
async def direct_generate_promotion(
    data: GeneratePromotionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate promotion plan via direct endpoint under /api/v1/promotions/."""
    if not data.business_id:
        raise ValidationException(
            errors={"business_id": "business_id is required in request body when calling direct promotions endpoint"}
        )
    _verify_user_business_role(db, current_user, data.business_id, ["owner", "admin", "manager"])
    return await promotion_handler.generate_plan_handler(data.business_id, data, current_user, db)


@direct_router.get("")
@direct_router.get("/", include_in_schema=False)
def direct_list_promotions(
    business_id: int = Query(..., description="Business ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    promotion_type: Optional[str] = Query(None, description="Filter by promotion type"),
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    start_after: Optional[date] = Query(None, description="Filter plans starting on or after date"),
    end_before: Optional[date] = Query(None, description="Filter plans ending on or before date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List promotion plans via direct endpoint under /api/v1/promotions/."""
    _verify_user_business_role(db, current_user, business_id)
    filter_params = {
        "status": status,
        "promotion_type": promotion_type,
        "branch_id": branch_id,
        "start_after": start_after,
        "end_before": end_before,
        "page": page,
        "page_size": page_size,
    }
    return promotion_handler.list_plans_handler(business_id, filter_params, db)


@direct_router.get("/{plan_id}")
def direct_get_promotion(
    plan_id: int,
    business_id: int = Query(..., description="Business ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get promotion plan detail via direct endpoint under /api/v1/promotions/."""
    _verify_user_business_role(db, current_user, business_id)
    return promotion_handler.get_plan_handler(business_id, plan_id, db)


@direct_router.patch("/{plan_id}/status", status_code=200)
def direct_update_promotion_status(
    plan_id: int,
    data: UpdatePromotionStatusRequest,
    business_id: int = Query(..., description="Business ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update promotion plan status via direct endpoint under /api/v1/promotions/."""
    _verify_user_business_role(db, current_user, business_id, ["owner", "admin", "manager"])
    return promotion_handler.update_plan_status_handler(
        business_id, plan_id, data, current_user, db
    )


@direct_router.post("/{plan_id}/evaluate", status_code=200)
def direct_evaluate_promotion(
    plan_id: int,
    data: EvaluatePromotionRequest,
    business_id: Optional[int] = Query(None, description="Business ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-evaluate promotion plan via direct endpoint under /api/v1/promotions/."""
    resolved_business_id = data.business_id or business_id
    if not resolved_business_id:
        raise ValidationException(
            errors={"business_id": "business_id is required either in request body or query parameter"}
        )
    _verify_user_business_role(db, current_user, resolved_business_id, ["owner", "admin", "manager"])
    return promotion_handler.evaluate_plan_handler(
        resolved_business_id, plan_id, data, current_user, db
    )
