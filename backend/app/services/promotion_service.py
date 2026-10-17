"""
Promotion Planner Service — Orchestration Layer.

Collects product prices, cost history, and metadata, runs the deterministic
PromotionEngine, enriches with AI narratives, persists promotion proposals,
and manages promotion lifecycle transitions.
"""

from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_price_history import ProductPriceHistory
from app.models.product_cost_history import ProductCostHistory
from app.models.promotion_plan import PromotionPlan
from app.models.schemas.promotion import (
    GeneratePromotionRequest,
    UpdatePromotionStatusRequest,
    EvaluatePromotionRequest,
    PromotionPlanResponse,
    PromotionItemResponse,
    GeneratePromotionResponse,
)
from app.services.promotion_engine import (
    PromotionEngine,
    ItemInputData,
    PlanEvaluation,
)
from app.services.promotion_narrative_generator import PromotionNarrativeGenerator
from app.helpers.pagination import paginate_query
from app.helpers.exceptions import NotFoundException, ValidationException
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.logging import logger


VALID_TRANSITIONS = {
    "draft": ["approved", "rejected"],
    "approved": ["archived"],
    "rejected": ["draft"],
    "archived": [],
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _collect_products(
    db: Session, business_id: int, product_ids: List[int]
) -> Dict[int, Product]:
    """Retrieve existing products for business."""
    if not product_ids:
        return {}
    products = (
        db.query(Product)
        .filter(
            Product.business_id == business_id,
            Product.id.in_(product_ids),
        )
        .all()
    )
    return {p.id: p for p in products}


def _collect_product_prices(
    db: Session, business_id: int, product_ids: List[int]
) -> Dict[int, Decimal]:
    """Retrieve latest effective selling price for each product."""
    if not product_ids:
        return {}
    prices = (
        db.query(ProductPriceHistory)
        .filter(
            ProductPriceHistory.business_id == business_id,
            ProductPriceHistory.product_id.in_(product_ids),
        )
        .order_by(
            ProductPriceHistory.product_id,
            ProductPriceHistory.effective_from.desc(),
            ProductPriceHistory.id.desc(),
        )
        .all()
    )
    result = {}
    for p in prices:
        if p.product_id not in result:
            result[p.product_id] = p.selling_price
    return result


def _collect_product_costs(
    db: Session, business_id: int, product_ids: List[int]
) -> Dict[int, Decimal]:
    """Retrieve latest effective unit cost for each product."""
    if not product_ids:
        return {}
    costs = (
        db.query(ProductCostHistory)
        .filter(
            ProductCostHistory.business_id == business_id,
            ProductCostHistory.product_id.in_(product_ids),
        )
        .order_by(
            ProductCostHistory.product_id,
            ProductCostHistory.effective_from.desc(),
            ProductCostHistory.id.desc(),
        )
        .all()
    )
    result = {}
    for c in costs:
        if c.product_id not in result:
            result[c.product_id] = c.unit_cost
    return result


async def generate_plan(
    db: Session,
    business_id: int,
    request: GeneratePromotionRequest,
    user_id: Optional[int] = None,
) -> GeneratePromotionResponse:
    """
    Generate a new promotion plan:
    1. Collect prices and costs
    2. Run deterministic financial evaluation
    3. Generate AI narrative (title, rationale, steps, risks)
    4. Persist if request.persist is True
    """
    product_ids = [item.product_id for item in request.items]
    product_map = _collect_products(db, business_id, product_ids)

    # Validate all products exist under this business
    for item in request.items:
        if item.product_id not in product_map:
            raise ValidationException(
                message="Product not found",
                errors={"product_id": f"Product ID {item.product_id} does not exist in this business"},
                error_code=ErrorCodeRegistry.VALIDATION_FAILED,
            )

    price_map = _collect_product_prices(db, business_id, product_ids)
    cost_map = _collect_product_costs(db, business_id, product_ids)

    items_data: List[ItemInputData] = []
    for item in request.items:
        prod = product_map[item.product_id]
        orig_price = price_map.get(item.product_id)
        unit_cost = cost_map.get(item.product_id)

        items_data.append(
            ItemInputData(
                product_id=item.product_id,
                product_name=prod.name,
                discount_type=item.discount_type,
                discount_value=item.discount_value,
                original_price=orig_price,
                unit_cost=unit_cost,
                expected_qty=item.expected_qty,
                notes=item.notes,
            )
        )

    # Deterministic calculation
    evaluation: PlanEvaluation = PromotionEngine.evaluate_plan(
        items_data=items_data,
        min_margin_pct=request.min_margin_pct,
    )

    # AI narrative generation
    narrative_gen = PromotionNarrativeGenerator()
    narrative = await narrative_gen.generate_narrative(
        promotion_type=request.promotion_type,
        start_date=request.start_date,
        end_date=request.end_date,
        evaluation=evaluation,
    )

    combined_risks = list(dict.fromkeys(evaluation.risks + narrative.risks))

    if request.persist:
        now = _now_utc()
        plan = PromotionPlan(
            business_id=business_id,
            title=narrative.title,
            promotion_type=request.promotion_type,
            status="draft",
            branch_id=request.branch_id,
            start_date=request.start_date,
            end_date=request.end_date,
            items=[it.to_dict() for it in evaluation.items],
            total_original_revenue=evaluation.total_original_revenue,
            total_discounted_revenue=evaluation.total_discounted_revenue,
            total_estimated_cost=evaluation.total_estimated_cost,
            total_estimated_margin=evaluation.total_estimated_margin,
            avg_margin_pct=evaluation.avg_margin_pct,
            is_financially_validated=evaluation.is_financially_validated,
            min_margin_pct=evaluation.min_margin_pct,
            warnings=evaluation.warnings,
            assumptions=evaluation.assumptions,
            missing_data=evaluation.missing_data,
            risks=combined_risks,
            rationale=narrative.rationale,
            recommended_actions=narrative.recommended_actions,
            created_by_user_id=user_id,
            updated_by_user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        plan_response = PromotionPlanResponse.model_validate(plan)
    else:
        now = _now_utc()
        plan_response = PromotionPlanResponse(
            id=0,
            business_id=business_id,
            title=narrative.title,
            promotion_type=request.promotion_type,
            status="draft",
            branch_id=request.branch_id,
            start_date=request.start_date,
            end_date=request.end_date,
            items=[PromotionItemResponse(**it.to_dict()) for it in evaluation.items],
            total_original_revenue=evaluation.total_original_revenue,
            total_discounted_revenue=evaluation.total_discounted_revenue,
            total_estimated_cost=evaluation.total_estimated_cost,
            total_estimated_margin=evaluation.total_estimated_margin,
            avg_margin_pct=evaluation.avg_margin_pct,
            is_financially_validated=evaluation.is_financially_validated,
            min_margin_pct=evaluation.min_margin_pct,
            warnings=evaluation.warnings,
            assumptions=evaluation.assumptions,
            missing_data=evaluation.missing_data,
            risks=combined_risks,
            rationale=narrative.rationale,
            recommended_actions=narrative.recommended_actions,
            created_by_user_id=user_id,
            approved_by_user_id=None,
            approved_at=None,
            rejected_reason=None,
            created_at=now,
            updated_at=now,
        )

    data_summary = {
        "products_analyzed": len(request.items),
        "price_data_available": sum(1 for it in evaluation.items if it.price_data_available),
        "cost_data_available": sum(1 for it in evaluation.items if it.cost_data_available),
        "financially_validated": evaluation.is_financially_validated,
    }

    return GeneratePromotionResponse(plan=plan_response, data_summary=data_summary)


def list_plans(
    db: Session,
    business_id: int,
    filter_params: Dict[str, Any],
) -> Tuple[List[PromotionPlan], Dict[str, Any]]:
    """Retrieve paginated promotion plans for a business."""
    query = db.query(PromotionPlan).filter(PromotionPlan.business_id == business_id)

    status = filter_params.get("status")
    if status:
        query = query.filter(PromotionPlan.status == status)

    promotion_type = filter_params.get("promotion_type")
    if promotion_type:
        query = query.filter(PromotionPlan.promotion_type == promotion_type)

    branch_id = filter_params.get("branch_id")
    if branch_id:
        query = query.filter(PromotionPlan.branch_id == branch_id)

    start_after = filter_params.get("start_after")
    if start_after:
        query = query.filter(PromotionPlan.start_date >= start_after)

    end_before = filter_params.get("end_before")
    if end_before:
        query = query.filter(PromotionPlan.end_date <= end_before)

    query = query.order_by(PromotionPlan.created_at.desc(), PromotionPlan.id.desc())

    page = int(filter_params.get("page", 1))
    page_size = min(int(filter_params.get("page_size", 20)), 100)

    items, pagination = paginate_query(query, page=page, page_size=page_size)
    return items, pagination


def get_plan(
    db: Session,
    business_id: int,
    plan_id: int,
) -> PromotionPlan:
    """Retrieve a single promotion plan by ID scoped to business."""
    plan = (
        db.query(PromotionPlan)
        .filter(
            PromotionPlan.id == plan_id,
            PromotionPlan.business_id == business_id,
        )
        .first()
    )
    if not plan:
        raise NotFoundException(
            message=f"Promotion plan #{plan_id} not found",
            error_code=ErrorCodeRegistry.PROMO_PLAN_NOT_FOUND,
        )
    return plan


def update_plan_status(
    db: Session,
    business_id: int,
    plan_id: int,
    request: UpdatePromotionStatusRequest,
    user_id: Optional[int] = None,
) -> PromotionPlan:
    """Perform state transitions on promotion plans (draft -> approved / rejected, etc.)."""
    plan = get_plan(db, business_id, plan_id)

    allowed_next = VALID_TRANSITIONS.get(plan.status, [])
    if request.status not in allowed_next:
        raise ValidationException(
            errors={"status": f"Cannot transition promotion plan from '{plan.status}' to '{request.status}'. Allowed: {allowed_next}"},
            message=f"Cannot transition promotion plan from '{plan.status}' to '{request.status}'. Allowed: {allowed_next}",
            error_code=ErrorCodeRegistry.PROMO_INVALID_STATUS_TRANSITION,
        )

    now = _now_utc()
    if request.status == "rejected":
        if not request.rejected_reason or not request.rejected_reason.strip():
            raise ValidationException(
                errors={"rejected_reason": "A rejection reason is required when rejecting a promotion plan"},
                message="A rejection reason is required when rejecting a promotion plan",
                error_code=ErrorCodeRegistry.PROMO_REJECTION_REASON_REQUIRED,
            )
        plan.rejected_reason = request.rejected_reason.strip()

    elif request.status == "approved":
        plan.approved_by_user_id = user_id
        plan.approved_at = now
        plan.rejected_reason = None
    elif request.status == "draft":
        plan.rejected_reason = None
        plan.approved_by_user_id = None
        plan.approved_at = None

    plan.status = request.status
    plan.updated_by_user_id = user_id
    plan.updated_at = now

    db.commit()
    db.refresh(plan)
    return plan


def evaluate_plan(
    db: Session,
    business_id: int,
    plan_id: int,
    request: EvaluatePromotionRequest,
    user_id: Optional[int] = None,
) -> GeneratePromotionResponse:
    """Re-evaluate an existing plan with current prices and cost data."""
    plan = get_plan(db, business_id, plan_id)

    raw_items = plan.items or []
    product_ids = [it["product_id"] for it in raw_items if "product_id" in it]
    product_map = _collect_products(db, business_id, product_ids)
    price_map = _collect_product_prices(db, business_id, product_ids)
    cost_map = _collect_product_costs(db, business_id, product_ids)

    items_data: List[ItemInputData] = []
    for raw in raw_items:
        p_id = raw["product_id"]
        prod_name = product_map[p_id].name if p_id in product_map else raw.get("product_name", f"Product #{p_id}")
        items_data.append(
            ItemInputData(
                product_id=p_id,
                product_name=prod_name,
                discount_type=raw["discount_type"],
                discount_value=Decimal(str(raw["discount_value"])),
                original_price=price_map.get(p_id),
                unit_cost=cost_map.get(p_id),
                expected_qty=raw.get("expected_qty"),
                notes=raw.get("notes"),
            )
        )

    effective_min_margin = request.min_margin_pct if request.min_margin_pct is not None else plan.min_margin_pct
    evaluation: PlanEvaluation = PromotionEngine.evaluate_plan(
        items_data=items_data,
        min_margin_pct=effective_min_margin,
    )

    now = _now_utc()
    plan.items = [it.to_dict() for it in evaluation.items]
    plan.total_original_revenue = evaluation.total_original_revenue
    plan.total_discounted_revenue = evaluation.total_discounted_revenue
    plan.total_estimated_cost = evaluation.total_estimated_cost
    plan.total_estimated_margin = evaluation.total_estimated_margin
    plan.avg_margin_pct = evaluation.avg_margin_pct
    plan.is_financially_validated = evaluation.is_financially_validated
    plan.min_margin_pct = evaluation.min_margin_pct
    plan.warnings = evaluation.warnings
    plan.missing_data = evaluation.missing_data
    plan.risks = list(dict.fromkeys((plan.risks or []) + evaluation.risks))
    plan.updated_by_user_id = user_id
    plan.updated_at = now

    db.commit()
    db.refresh(plan)

    data_summary = {
        "products_analyzed": len(items_data),
        "price_data_available": sum(1 for it in evaluation.items if it.price_data_available),
        "cost_data_available": sum(1 for it in evaluation.items if it.cost_data_available),
        "financially_validated": evaluation.is_financially_validated,
    }

    return GeneratePromotionResponse(
        plan=PromotionPlanResponse.model_validate(plan),
        data_summary=data_summary,
    )
