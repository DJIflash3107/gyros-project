"""
Business Action Service — Orchestration Layer.

Collects sales observations, expenses, and forecasting data, runs the deterministic
BusinessActionEngine, deduplicates / persists recommendations in `business_actions`,
and manages action status transitions.
"""

from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session

def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

from app.models.business import Business
from app.models.branch import Branch
from app.models.product import Product
from app.models.sales_report_observation import SalesReportObservation
from app.models.expense import Expense
from app.models.forecast_run import ForecastRun
from app.models.forecast_result import ForecastResult
from app.models.business_action import BusinessAction
from app.models.schemas.business_action import (
    GenerateActionsRequest,
    UpdateActionStatusRequest,
    BusinessActionResponse,
    GenerateActionsResponse,
)
from app.services.business_action_engine import (
    BusinessActionEngine,
    EngineInput,
    AggregatedObservation,
    AggregatedExpense,
    AggregatedForecast,
)
from app.services.action_narrative_generator import ActionNarrativeGenerator
from app.helpers.exceptions import AppException, NotFoundException
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.pagination import paginate_query


VALID_TRANSITIONS = {
    "open": ["in_progress", "dismissed"],
    "in_progress": ["implemented", "open", "dismissed"],
    "implemented": ["archived"],
    "dismissed": ["open", "archived"],
    "archived": [],
}


def _collect_observation_data(
    db: Session,
    business_id: int,
    branch_id: Optional[int],
    product_id: Optional[int],
    lookback_days: int,
) -> List[AggregatedObservation]:
    cutoff_date = date.today() - timedelta(days=lookback_days)

    query = (
        db.query(
            SalesReportObservation.branch_id,
            Branch.name.label("branch_name"),
            SalesReportObservation.product_id,
            Product.name.label("product_name"),
            Product.category.label("product_category"),
            func.min(SalesReportObservation.period_start).label("min_date"),
            func.max(SalesReportObservation.period_end).label("max_date"),
            func.sum(func.coalesce(SalesReportObservation.sold_qty, 0)).label("total_sold"),
            func.sum(func.coalesce(SalesReportObservation.spoiled_qty, 0)).label("total_spoiled"),
            func.sum(func.coalesce(SalesReportObservation.damaged_qty, 0)).label("total_damaged"),
            func.sum(func.coalesce(SalesReportObservation.leftover_qty, 0)).label("total_leftover"),
            func.sum(func.coalesce(SalesReportObservation.recorded_revenue, 0)).label("total_revenue"),
            func.count(SalesReportObservation.id).label("obs_count"),
        )
        .outerjoin(Branch, Branch.id == SalesReportObservation.branch_id)
        .outerjoin(Product, Product.id == SalesReportObservation.product_id)
        .filter(
            SalesReportObservation.business_id == business_id,
            SalesReportObservation.record_status == "active",
            SalesReportObservation.period_start >= cutoff_date,
        )
    )

    if branch_id:
        query = query.filter(SalesReportObservation.branch_id == branch_id)
    if product_id:
        query = query.filter(SalesReportObservation.product_id == product_id)

    query = query.group_by(
        SalesReportObservation.branch_id,
        Branch.name,
        SalesReportObservation.product_id,
        Product.name,
        Product.category,
    )

    results = query.all()
    aggregated = []
    for row in results:
        min_d = row.min_date or cutoff_date
        max_d = row.max_date or date.today()
        days_in_period = max(1, (max_d - min_d).days + 1)

        aggregated.append(
            AggregatedObservation(
                branch_id=row.branch_id,
                branch_name=row.branch_name or f"Branch #{row.branch_id}",
                product_id=row.product_id,
                product_name=row.product_name or f"Product #{row.product_id}",
                product_category=row.product_category,
                period_start=min_d,
                period_end=max_d,
                days_in_period=days_in_period,
                total_sold=Decimal(str(row.total_sold or 0)),
                total_spoiled=Decimal(str(row.total_spoiled or 0)),
                total_damaged=Decimal(str(row.total_damaged or 0)),
                total_leftover=Decimal(str(row.total_leftover or 0)),
                total_revenue=Decimal(str(row.total_revenue or 0)),
                observation_count=row.obs_count or 0,
            )
        )
    return aggregated


def _collect_expense_data(
    db: Session,
    business_id: int,
    branch_id: Optional[int],
    lookback_days: int,
) -> List[AggregatedExpense]:
    today = date.today()
    current_start = today - timedelta(days=lookback_days)
    prior_start = today - timedelta(days=lookback_days * 2)

    query_curr = (
        db.query(
            Expense.category,
            Expense.branch_id,
            Branch.name.label("branch_name"),
            func.sum(Expense.amount).label("total_amount"),
            func.count(Expense.id).label("exp_count"),
        )
        .outerjoin(Branch, Branch.id == Expense.branch_id)
        .filter(
            Expense.business_id == business_id,
            Expense.expense_date >= current_start,
        )
    )
    if branch_id:
        query_curr = query_curr.filter(Expense.branch_id == branch_id)

    query_curr = query_curr.group_by(
        Expense.category,
        Expense.branch_id,
        Branch.name,
    )
    curr_results = query_curr.all()

    query_prior = (
        db.query(
            Expense.category,
            Expense.branch_id,
            func.sum(Expense.amount).label("prior_amount"),
        )
        .filter(
            Expense.business_id == business_id,
            Expense.expense_date >= prior_start,
            Expense.expense_date < current_start,
        )
    )
    if branch_id:
        query_prior = query_prior.filter(Expense.branch_id == branch_id)
    query_prior = query_prior.group_by(Expense.category, Expense.branch_id)
    prior_map = {
        (row.category, row.branch_id): Decimal(str(row.prior_amount or 0))
        for row in query_prior.all()
    }

    aggregated = []
    for row in curr_results:
        prior_amt = prior_map.get((row.category, row.branch_id))
        aggregated.append(
            AggregatedExpense(
                category=row.category,
                branch_id=row.branch_id,
                branch_name=row.branch_name,
                total_amount=Decimal(str(row.total_amount or 0)),
                expense_count=row.exp_count or 0,
                period_amount_prior=prior_amt,
            )
        )
    return aggregated


def _collect_forecast_data(
    db: Session,
    business_id: int,
    branch_id: Optional[int],
    product_id: Optional[int],
) -> List[AggregatedForecast]:
    query = (
        db.query(ForecastRun)
        .filter(ForecastRun.business_id == business_id)
        .order_by(ForecastRun.created_at.desc())
    )
    if branch_id:
        query = query.filter(ForecastRun.branch_id == branch_id)
    if product_id:
        query = query.filter(ForecastRun.product_id == product_id)

    runs = query.all()
    seen_pairs = set()
    latest_runs: List[ForecastRun] = []
    for run in runs:
        pair = (run.branch_id, run.product_id)
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            latest_runs.append(run)

    aggregated = []
    for run in latest_runs:
        branch = db.query(Branch).filter(Branch.id == run.branch_id).first()
        product = db.query(Product).filter(Product.id == run.product_id).first()
        branch_name = branch.name if branch else f"Branch #{run.branch_id}"
        product_name = product.name if product else f"Product #{run.product_id}"

        pred_sum = (
            db.query(func.sum(ForecastResult.predicted_qty))
            .filter(ForecastResult.forecast_run_id == run.id)
            .scalar()
        )
        predicted_total_qty = Decimal(str(pred_sum or 0))

        recent_start = date.today() - timedelta(days=run.horizon_days)
        hist_sum = (
            db.query(func.sum(SalesReportObservation.sold_qty))
            .filter(
                SalesReportObservation.business_id == business_id,
                SalesReportObservation.branch_id == run.branch_id,
                SalesReportObservation.product_id == run.product_id,
                SalesReportObservation.record_status == "active",
                SalesReportObservation.period_start >= recent_start,
            )
            .scalar()
        )
        historical_recent_qty = Decimal(str(hist_sum or 0))

        aggregated.append(
            AggregatedForecast(
                forecast_run_id=run.id,
                branch_id=run.branch_id,
                branch_name=branch_name,
                product_id=run.product_id,
                product_name=product_name,
                is_reliable=run.is_reliable,
                mae=run.mae,
                wape=run.wape,
                forecast_bias=run.forecast_bias,
                horizon_days=run.horizon_days,
                predicted_total_qty=predicted_total_qty,
                historical_recent_qty=historical_recent_qty,
            )
        )
    return aggregated


async def generate_actions(
    db: Session,
    business_id: int,
    request: GenerateActionsRequest,
    user_id: Optional[int] = None,
) -> GenerateActionsResponse:
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise NotFoundException(
            message=f"Business with ID {business_id} not found",
            errors={"business_id": f"Business {business_id} does not exist"},
            error_code=ErrorCodeRegistry.NOT_FOUND,
        )

    observations = _collect_observation_data(
        db, business_id, request.branch_id, request.product_id, request.lookback_days
    )
    expenses = _collect_expense_data(
        db, business_id, request.branch_id, request.lookback_days
    )
    forecasts = _collect_forecast_data(
        db, business_id, request.branch_id, request.product_id
    )

    active_product_count = (
        db.query(Product).filter(Product.business_id == business_id, Product.is_active == True).count()
    )
    active_branch_count = (
        db.query(Branch).filter(Branch.business_id == business_id, Branch.is_active == True).count()
    )

    engine_input = EngineInput(
        business_id=business_id,
        business_name=business.name,
        observations=observations,
        expenses=expenses,
        forecasts=forecasts,
        lookback_days=request.lookback_days,
        active_product_count=active_product_count,
        active_branch_count=active_branch_count,
    )

    engine = BusinessActionEngine()
    candidates = engine.evaluate(engine_input)

    if request.categories:
        allowed_cats = set(request.categories)
        candidates = [c for c in candidates if c.category in allowed_cats]

    # AI narrative enrichment (raises on failure — no silent fallback)
    if candidates:
        narrative_gen = ActionNarrativeGenerator()
        candidates = await narrative_gen.enrich_candidates(candidates)

    data_summary = {
        "observations_analyzed": len(observations),
        "expenses_analyzed": len(expenses),
        "forecasts_analyzed": len(forecasts),
        "lookback_days": request.lookback_days,
        "active_branches": active_branch_count,
        "active_products": active_product_count,
    }

    if request.persist:
        now = _now_utc()
        persisted_actions: List[BusinessAction] = []

        for candidate in candidates:
            existing_query = db.query(BusinessAction).filter(
                BusinessAction.business_id == business_id,
                BusinessAction.action_type == candidate.action_type,
                BusinessAction.status.in_(["open", "in_progress"]),
            )
            if candidate.branch_id is not None:
                existing_query = existing_query.filter(BusinessAction.branch_id == candidate.branch_id)
            else:
                existing_query = existing_query.filter(BusinessAction.branch_id.is_(None))

            if candidate.product_id is not None:
                existing_query = existing_query.filter(BusinessAction.product_id == candidate.product_id)
            else:
                existing_query = existing_query.filter(BusinessAction.product_id.is_(None))

            existing = existing_query.first()
            if existing:
                existing.rule_label = candidate.rule_label
                existing.title = candidate.title
                existing.ai_generated = candidate.ai_generated
                existing.priority_score = candidate.priority_score
                existing.urgency = candidate.urgency
                existing.expected_impact = candidate.expected_impact
                existing.evidence_quality = candidate.evidence_quality
                existing.rationale = candidate.rationale
                existing.supporting_data = candidate.supporting_data
                existing.recommended_steps = candidate.recommended_steps
                existing.risks = candidate.risks
                existing.success_metrics = candidate.success_metrics
                existing.limitations = candidate.limitations
                existing.forecast_run_id = candidate.forecast_run_id
                existing.updated_by_user_id = user_id
                existing.updated_at = now
                persisted_actions.append(existing)
            else:
                new_action = BusinessAction(
                    business_id=business_id,
                    action_type=candidate.action_type,
                    rule_label=candidate.rule_label,
                    category=candidate.category,
                    title=candidate.title,
                    ai_generated=candidate.ai_generated,
                    urgency=candidate.urgency,
                    expected_impact=candidate.expected_impact,
                    priority_score=candidate.priority_score,
                    status="open",
                    evidence_quality=candidate.evidence_quality,
                    rationale=candidate.rationale,
                    supporting_data=candidate.supporting_data,
                    recommended_steps=candidate.recommended_steps,
                    risks=candidate.risks,
                    success_metrics=candidate.success_metrics,
                    limitations=candidate.limitations,
                    branch_id=candidate.branch_id,
                    product_id=candidate.product_id,
                    forecast_run_id=candidate.forecast_run_id,
                    created_by_user_id=user_id,
                    updated_by_user_id=user_id,
                    created_at=now,
                    updated_at=now,
                )
                db.add(new_action)
                persisted_actions.append(new_action)

        db.commit()
        for action in persisted_actions:
            db.refresh(action)

        response_items = [
            BusinessActionResponse.model_validate(action) for action in persisted_actions
        ]
        return GenerateActionsResponse(
            generated_count=len(candidates),
            persisted_count=len(persisted_actions),
            actions=response_items,
            data_summary=data_summary,
        )
    else:
        now = _now_utc()
        ephemeral_items = []
        for idx, candidate in enumerate(candidates, start=1):
            ephemeral_items.append(
                BusinessActionResponse(
                    id=idx,
                    business_id=business_id,
                    action_type=candidate.action_type,
                    rule_label=candidate.rule_label,
                    category=candidate.category,
                    title=candidate.title,
                    ai_generated=candidate.ai_generated,
                    urgency=candidate.urgency,
                    expected_impact=candidate.expected_impact,
                    priority_score=candidate.priority_score,
                    status="open",
                    evidence_quality=candidate.evidence_quality,
                    rationale=candidate.rationale,
                    supporting_data=candidate.supporting_data,
                    recommended_steps=candidate.recommended_steps,
                    risks=candidate.risks,
                    success_metrics=candidate.success_metrics,
                    limitations=candidate.limitations,
                    dismissed_reason=None,
                    branch_id=candidate.branch_id,
                    product_id=candidate.product_id,
                    forecast_run_id=candidate.forecast_run_id,
                    created_by_user_id=user_id,
                    updated_by_user_id=user_id,
                    created_at=now,
                    updated_at=now,
                )
            )
        return GenerateActionsResponse(
            generated_count=len(candidates),
            persisted_count=0,
            actions=ephemeral_items,
            data_summary=data_summary,
        )


def list_actions(
    db: Session,
    business_id: int,
    filter_params: Dict[str, Any],
) -> Tuple[List[BusinessAction], Dict[str, Any]]:
    query = db.query(BusinessAction).filter(BusinessAction.business_id == business_id)

    if filter_params.get("status"):
        query = query.filter(BusinessAction.status == filter_params["status"])
    if filter_params.get("category"):
        query = query.filter(BusinessAction.category == filter_params["category"])
    if filter_params.get("urgency"):
        query = query.filter(BusinessAction.urgency == filter_params["urgency"])
    if filter_params.get("evidence_quality"):
        query = query.filter(BusinessAction.evidence_quality == filter_params["evidence_quality"])
    if filter_params.get("branch_id") is not None:
        query = query.filter(BusinessAction.branch_id == filter_params["branch_id"])
    if filter_params.get("product_id") is not None:
        query = query.filter(BusinessAction.product_id == filter_params["product_id"])
    if filter_params.get("min_priority") is not None:
        query = query.filter(BusinessAction.priority_score >= filter_params["min_priority"])

    query = query.order_by(
        BusinessAction.priority_score.desc(),
        BusinessAction.created_at.desc(),
        BusinessAction.id.desc(),
    )

    page = filter_params.get("page", 1)
    page_size = filter_params.get("page_size", 20)
    return paginate_query(query, page=page, page_size=page_size)


def get_action(db: Session, business_id: int, action_id: int) -> BusinessAction:
    action = db.query(BusinessAction).filter(
        BusinessAction.id == action_id,
        BusinessAction.business_id == business_id,
    ).first()
    if not action:
        raise NotFoundException(
            message=f"Business action with ID {action_id} not found in this business",
            errors={"action_id": f"Business action {action_id} does not exist in business {business_id}"},
            error_code=ErrorCodeRegistry.BAC_ACTION_NOT_FOUND,
        )
    return action


def update_action_status(
    db: Session,
    business_id: int,
    action_id: int,
    request: UpdateActionStatusRequest,
    user_id: int,
) -> BusinessAction:
    action = get_action(db, business_id, action_id)

    allowed = VALID_TRANSITIONS.get(action.status, [])
    if request.status not in allowed:
        raise AppException(
            status_code=400,
            message=f"Cannot transition action status from '{action.status}' to '{request.status}'",
            errors={
                "status": f"Invalid transition from '{action.status}' to '{request.status}'. Allowed transitions: {allowed}"
            },
            error_code=ErrorCodeRegistry.BAC_INVALID_STATUS_TRANSITION,
        )

    if request.status == "dismissed":
        if not request.dismissed_reason or not request.dismissed_reason.strip():
            raise AppException(
                status_code=400,
                message="A reason must be provided when dismissing an action",
                errors={"dismissed_reason": "dismissed_reason is required when status is 'dismissed'"},
                error_code=ErrorCodeRegistry.BAC_DISMISSAL_REASON_REQUIRED,
            )
        action.dismissed_reason = request.dismissed_reason.strip()

    action.status = request.status
    action.updated_by_user_id = user_id
    action.updated_at = _now_utc()

    db.commit()
    db.refresh(action)
    return action
