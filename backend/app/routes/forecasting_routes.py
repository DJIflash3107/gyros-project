from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.models.user import User
from app.models.business_membership import BusinessMembership
from app.models.schemas.forecasting import (
    ForecastRequest,
    ForecastEvaluateRequest,
)
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import get_current_user, require_business_membership
from app.handlers import forecasting_handler
from app.helpers.exceptions import ValidationException, AuthorizationException

# Primary router scoped by business (per Gyros multi-tenant standards)
router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/forecasting",
    tags=["Forecasting"],
)

# Secondary router mounted under /api/v1/forecasting (for direct path access)
direct_router = APIRouter(
    prefix="/api/v1/forecasting",
    tags=["Forecasting"],
)


# ---------------------------------------------------------
# Primary Business-Scoped Endpoints
# ---------------------------------------------------------

@router.post("/predict", status_code=200, dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def predict_demand(
    business_id: int,
    data: ForecastRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate and persist a product demand forecast."""
    return forecasting_handler.generate_forecast_handler(business_id, data, current_user, db)


@router.post("/evaluate", status_code=200, dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def evaluate_forecast(
    business_id: int,
    data: ForecastEvaluateRequest,
    db: Session = Depends(get_db),
):
    """Run time-ordered backtesting and return MAE, WAPE, and bias metrics."""
    return forecasting_handler.evaluate_forecast_handler(business_id, data, db)


@router.get("/sufficiency", dependencies=[Depends(require_business_membership())])
def check_sufficiency(
    business_id: int,
    branch_id: int = Query(..., description="Branch ID"),
    product_id: int = Query(..., description="Product ID"),
    db: Session = Depends(get_db),
):
    """Check if sufficient confirmed daily sales observations exist for forecasting."""
    return forecasting_handler.check_sufficiency_handler(business_id, branch_id, product_id, db)


@router.get("/runs", dependencies=[Depends(require_business_membership())])
def list_forecast_runs(
    business_id: int,
    branch_id: Optional[int] = Query(None, description="Filter by branch ID"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List past forecast runs for a business with pagination."""
    params = PaginationParams(page=page, page_size=page_size)
    return forecasting_handler.list_runs_handler(business_id, branch_id, product_id, params, db)


@router.get("/runs/{run_id}", dependencies=[Depends(require_business_membership())])
def get_forecast_run(
    business_id: int,
    run_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific forecast run along with its prediction points."""
    return forecasting_handler.get_run_handler(business_id, run_id, db)


# ---------------------------------------------------------
# Direct /api/v1/forecasting/ Endpoints
# ---------------------------------------------------------

def _verify_user_business_role(db: Session, user: User, business_id: int, allowed_roles: Optional[list[str]] = None) -> BusinessMembership:
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


@direct_router.post("/predict", status_code=200)
def direct_predict_demand(
    data: ForecastRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate demand forecast via direct endpoint under /api/v1/forecasting/."""
    if not data.business_id:
        raise ValidationException(
            errors={"business_id": "business_id is required in request body when calling direct forecasting endpoint"}
        )
    _verify_user_business_role(db, current_user, data.business_id, ["owner", "admin", "manager"])
    return forecasting_handler.generate_forecast_handler(data.business_id, data, current_user, db)


@direct_router.post("/evaluate", status_code=200)
def direct_evaluate_forecast(
    data: ForecastEvaluateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Evaluate forecast via direct endpoint under /api/v1/forecasting/."""
    if not data.business_id:
        raise ValidationException(
            errors={"business_id": "business_id is required in request body when calling direct forecasting endpoint"}
        )
    _verify_user_business_role(db, current_user, data.business_id, ["owner", "admin", "manager"])
    return forecasting_handler.evaluate_forecast_handler(data.business_id, data, db)


@direct_router.get("/sufficiency")
def direct_check_sufficiency(
    business_id: int = Query(..., description="Business ID"),
    branch_id: int = Query(..., description="Branch ID"),
    product_id: int = Query(..., description="Product ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check data sufficiency via direct endpoint under /api/v1/forecasting/."""
    _verify_user_business_role(db, current_user, business_id)
    return forecasting_handler.check_sufficiency_handler(business_id, branch_id, product_id, db)
