import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from langchain_core.tools import tool, BaseTool

from app.services import (
    business_service,
    branch_service,
    business_membership_service,
    sales_report_observation_service,
    sales_report_submission_service,
    expense_service,
    product_service,
)

logger = logging.getLogger(__name__)


def execute_business_summary(db: Session, business_id: int) -> Dict[str, Any]:
    """Execute business summary lookup in read-only mode."""
    try:
        biz = business_service.get_business(db, business_id)
        branches, _ = branch_service.list_branches(db, business_id=business_id, page=1, page_size=100)
        members, _ = business_membership_service.list_memberships(db, business_id=business_id, page=1, page_size=100)
        return {
            "summary": f"Business '{biz.name}' has {len(branches)} branch(es) and {len(members)} team member(s).",
            "data": {
                "business_id": biz.id,
                "business_name": biz.name,
                "currency": biz.currency,
                "timezone": biz.timezone,
                "branch_count": len(branches),
                "branches": [
                    {
                        "id": b.id,
                        "name": b.name,
                        "branch_code": b.branch_code,
                        "is_active": b.is_active,
                    }
                    for b in branches
                ],
                "member_count": len(members),
            },
        }
    except Exception as e:
        logger.warning(f"Error executing business_summary for business {business_id}: {type(e).__name__}")
        return {
            "summary": "Failed to retrieve business summary",
            "data": None,
            "error": "Unable to retrieve business summary",
        }


def execute_sales_analytics(
    db: Session,
    business_id: int,
    period: Optional[str] = None,
    branch_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute sales analytics aggregation in read-only mode."""
    try:
        observations, _ = sales_report_observation_service.list_observations(
            db, business_id=business_id, branch_id=branch_id, page=1, page_size=100
        )
        submissions, _ = sales_report_submission_service.list_submissions(
            db, business_id=business_id, page=1, page_size=20
        )
        total_revenue = sum(float(o.recorded_revenue or 0) for o in observations)
        total_sold_qty = sum(float(o.sold_qty or 0) for o in observations)

        product_counts: Dict[int, float] = {}
        for o in observations:
            pid = o.product_id
            product_counts[pid] = product_counts.get(pid, 0.0) + float(o.sold_qty or 0)

        top_products = [
            {"product_id": pid, "sold_qty": qty}
            for pid, qty in sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        return {
            "summary": f"Found {len(observations)} sales records across {len(submissions)} submission(s) with total revenue of {total_revenue:.2f}.",
            "data": {
                "business_id": business_id,
                "branch_id": branch_id,
                "period": period,
                "total_revenue": total_revenue,
                "total_sold_qty": total_sold_qty,
                "observations_count": len(observations),
                "submissions_count": len(submissions),
                "top_products": top_products,
            },
        }
    except Exception as e:
        logger.warning(f"Error executing sales_analytics for business {business_id}: {type(e).__name__}")
        return {
            "summary": "Failed to retrieve sales analytics",
            "data": None,
            "error": "Unable to retrieve sales analytics",
        }


def execute_expense_summary(
    db: Session,
    business_id: int,
    period: Optional[str] = None,
    branch_id: Optional[int] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute expense breakdown in read-only mode."""
    try:
        expenses, _ = expense_service.list_expenses(
            db, business_id=business_id, branch_id=branch_id, category=category, page=1, page_size=100
        )
        total_expenses = sum(float(e.amount or 0) for e in expenses)
        by_category: Dict[str, float] = {}
        for e in expenses:
            cat = e.category or "uncategorized"
            by_category[cat] = by_category.get(cat, 0.0) + float(e.amount or 0)

        recent_expenses = [
            {
                "id": e.id,
                "category": e.category,
                "amount": float(e.amount),
                "currency": e.currency,
                "description": e.description,
                "expense_date": str(e.expense_date),
            }
            for e in expenses[:10]
        ]

        return {
            "summary": f"Found {len(expenses)} expense item(s) totaling {total_expenses:.2f}.",
            "data": {
                "business_id": business_id,
                "branch_id": branch_id,
                "category": category,
                "period": period,
                "total_expenses": total_expenses,
                "expense_count": len(expenses),
                "by_category": by_category,
                "recent_expenses": recent_expenses,
            },
        }
    except Exception as e:
        logger.warning(f"Error executing expense_summary for business {business_id}: {type(e).__name__}")
        return {
            "summary": "Failed to retrieve expense summary",
            "data": None,
            "error": "Unable to retrieve expense summary",
        }


def execute_product_catalog(
    db: Session,
    business_id: int,
    category: Optional[str] = None,
    active_only: Optional[bool] = None,
) -> Dict[str, Any]:
    """Execute product catalog listing in read-only mode."""
    try:
        is_active = True if active_only else None
        products, _ = product_service.list_products(
            db, business_id=business_id, category=category, is_active=is_active, page=1, page_size=100
        )
        categories = sorted(list(set(p.category for p in products if p.category)))
        return {
            "summary": f"Product catalog contains {len(products)} item(s) across {len(categories)} category/categories.",
            "data": {
                "business_id": business_id,
                "total_products": len(products),
                "categories": categories,
                "products": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "sku": p.sku,
                        "category": p.category,
                        "base_unit": p.base_unit,
                        "is_active": p.is_active,
                    }
                    for p in products
                ],
            },
        }
    except Exception as e:
        logger.warning(f"Error executing product_catalog for business {business_id}: {type(e).__name__}")
        return {
            "summary": "Failed to retrieve product catalog",
            "data": None,
            "error": "Unable to retrieve product catalog",
        }


def execute_invoke_forecasting(
    business_id: int,
    db: Optional[Session] = None,
    branch_id: Optional[int] = None,
    product_id: Optional[int] = None,
    horizon_days: int = 7,
    window_size: int = 7,
    metric: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute demand forecasting via the forecasting service. Never invents predictions."""
    if db is None or branch_id is None or product_id is None:
        return {
            "summary": "Forecasting service is not yet available for general metric queries without specific branch_id and product_id.",
            "data": {
                "status": "not_available",
                "service": "forecasting",
                "message": "Forecasting requires a specific branch_id and product_id.",
                "business_id": business_id,
                "metric": metric,
            },
        }

    from app.services import forecasting_service
    from app.models.schemas.forecasting import ForecastRequest

    try:
        req = ForecastRequest(
            branch_id=branch_id,
            product_id=product_id,
            horizon_days=horizon_days,
            window_size=window_size,
        )
        run = forecasting_service.generate_forecast(db, business_id=business_id, data=req)
        predictions_data = [
            {
                "forecast_date": str(p.forecast_date),
                "predicted_qty": str(p.predicted_qty),
                "weekday": p.weekday,
            }
            for p in run.predictions
        ]
        return {
            "summary": f"Forecast generated for product {product_id} at branch {branch_id}: {len(predictions_data)} day horizon ({run.method})",
            "data": {
                "status": "success",
                "run_id": run.id,
                "method": run.method,
                "is_reliable": run.is_reliable,
                "reliability_note": run.reliability_note,
                "horizon_days": run.horizon_days,
                "window_size": run.window_size,
                "training_start": str(run.training_start) if run.training_start else None,
                "training_end": str(run.training_end) if run.training_end else None,
                "observations_used": run.observations_used,
                "predictions": predictions_data,
            },
        }
    except Exception as e:
        logger.warning(f"Error executing forecasting for business {business_id}: {type(e).__name__}: {str(e)}")
        return {
            "summary": f"Forecasting failed: {str(e)}",
            "data": None,
            "error": str(e),
        }



def execute_invoke_action_center(
    business_id: int,
    db: Optional[Session] = None,
    action: Optional[str] = "generate",
    branch_id: Optional[int] = None,
    product_id: Optional[int] = None,
    category: Optional[str] = None,
    lookback_days: int = 30,
    persist: bool = False,
) -> Dict[str, Any]:
    """Execute Business Action Center recommendations."""
    if db is None:
        return {
            "summary": "Business Action Center service is not yet available without a database session.",
            "data": {
                "status": "not_available",
                "service": "action_center",
                "message": "Business Action Center requires an active database session.",
                "business_id": business_id,
                "action": action,
            },
        }

    from app.services import business_action_service
    from app.models.schemas.business_action import GenerateActionsRequest

    import asyncio
    import concurrent.futures

    try:
        categories = [category] if category else None
        req = GenerateActionsRequest(
            branch_id=branch_id,
            product_id=product_id,
            categories=categories,
            lookback_days=lookback_days,
            persist=persist,
        )
        coro = business_action_service.generate_actions(
            db, business_id=business_id, request=req
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(asyncio.run, coro).result()
        else:
            result = asyncio.run(coro)
        actions_summary = [
            {
                "id": a.id,
                "title": a.title,
                "action_type": a.action_type,
                "category": a.category,
                "urgency": a.urgency,
                "expected_impact": a.expected_impact,
                "priority_score": float(a.priority_score),
                "evidence_quality": a.evidence_quality,
                "rationale": a.rationale,
                "recommended_steps": a.recommended_steps,
            }
            for a in result.actions[:5]
        ]
        return {
            "summary": f"Generated {result.generated_count} business recommendations ({len(actions_summary)} top actions shown).",
            "data": {
                "status": "success",
                "generated_count": result.generated_count,
                "persisted_count": result.persisted_count,
                "data_summary": result.data_summary,
                "top_recommendations": actions_summary,
            },
        }
    except Exception as e:
        logger.warning(f"Error executing action center for business {business_id}: {type(e).__name__}: {str(e)}")
        return {
            "summary": f"Action Center failed: {str(e)}",
            "data": None,
            "error": str(e),
        }


def execute_invoke_promotion_planner(
    business_id: int,
    db: Optional[Session] = None,
    action: Optional[str] = "generate",
    promotion_type: Optional[str] = None,
    product_ids: Optional[List[int]] = None,
    items: Optional[List[Dict[str, Any]]] = None,
    discount_pct: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    branch_id: Optional[int] = None,
    min_margin_pct: Optional[float] = None,
    plan_id: Optional[int] = None,
    persist: bool = False,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute Promotion Planner recommendations, listing, or evaluation."""
    if db is None:
        return {
            "summary": "Promotion Planner service is not yet available without a database session.",
            "data": {
                "status": "not_available",
                "service": "promotion_planner",
                "message": "Promotion Planner requires an active database session.",
                "business_id": business_id,
                "action": action,
            },
        }

    # If params dictionary passed, extract values
    if params and isinstance(params, dict):
        action = params.get("action", action)
        promotion_type = params.get("promotion_type", promotion_type)
        product_ids = params.get("product_ids", product_ids)
        items = params.get("items", items)
        discount_pct = params.get("discount_pct", discount_pct)
        start_date = params.get("start_date", start_date)
        end_date = params.get("end_date", end_date)
        branch_id = params.get("branch_id", branch_id)
        min_margin_pct = params.get("min_margin_pct", min_margin_pct)
        plan_id = params.get("plan_id", plan_id)
        persist = params.get("persist", persist)

    from datetime import date, timedelta
    from decimal import Decimal
    from app.models.product import Product
    from app.services import promotion_service
    from app.models.schemas.promotion import (
        GeneratePromotionRequest,
        PromotionItemInput,
        EvaluatePromotionRequest,
        PromotionPlanResponse,
    )
    import asyncio
    import concurrent.futures

    try:
        if action == "list":
            filter_params = {
                "branch_id": branch_id,
                "promotion_type": promotion_type,
                "page": 1,
                "page_size": 10,
            }
            plan_items, pagination = promotion_service.list_plans(
                db, business_id=business_id, filter_params=filter_params
            )
            return {
                "summary": f"Found {pagination.get('total', len(plan_items))} promotion plans for business {business_id}.",
                "data": {
                    "status": "success",
                    "plans": [PromotionPlanResponse.model_validate(p).model_dump(mode="json") for p in plan_items],
                    "pagination": pagination,
                },
            }

        elif action == "evaluate":
            if not plan_id:
                return {
                    "summary": "plan_id is required to evaluate a promotion plan.",
                    "data": None,
                    "error": "Missing plan_id",
                }
            eval_req = EvaluatePromotionRequest(
                business_id=business_id,
                min_margin_pct=Decimal(str(min_margin_pct)) if min_margin_pct is not None else None,
            )
            eval_res = promotion_service.evaluate_plan(
                db, business_id=business_id, plan_id=plan_id, request=eval_req
            )
            return {
                "summary": f"Evaluated promotion plan #{plan_id}. Financially validated: {eval_res.plan.is_financially_validated}.",
                "data": {
                    "status": "success",
                    "plan": eval_res.plan.model_dump(mode="json"),
                    "data_summary": eval_res.data_summary,
                },
            }

        else:
            # Default action: "generate"
            today = date.today()
            if start_date:
                s_date = date.fromisoformat(str(start_date)) if isinstance(start_date, str) else start_date
            else:
                s_date = today + timedelta(days=1)

            if end_date:
                e_date = date.fromisoformat(str(end_date)) if isinstance(end_date, str) else end_date
            else:
                e_date = s_date + timedelta(days=14)

            # Build PromotionItemInput list
            promo_items: List[PromotionItemInput] = []
            if items:
                for it in items:
                    promo_items.append(
                        PromotionItemInput(
                            product_id=it["product_id"],
                            discount_type=it.get("discount_type", "percentage"),
                            discount_value=Decimal(str(it.get("discount_value", discount_pct or 15.0))),
                            expected_qty=it.get("expected_qty"),
                            notes=it.get("notes"),
                        )
                    )
            elif product_ids:
                d_val = Decimal(str(discount_pct if discount_pct is not None else 15.0))
                for pid in product_ids:
                    promo_items.append(
                        PromotionItemInput(
                            product_id=pid,
                            discount_type="percentage",
                            discount_value=d_val,
                        )
                    )
            else:
                # Pick active products from DB if none specified
                active_prods = (
                    db.query(Product)
                    .filter(Product.business_id == business_id, Product.is_active == True)
                    .limit(3)
                    .all()
                )
                if not active_prods:
                    return {
                        "summary": "No active products found to generate promotion.",
                        "data": None,
                        "error": "No active products found for this business",
                    }
                d_val = Decimal(str(discount_pct if discount_pct is not None else 15.0))
                for p in active_prods:
                    promo_items.append(
                        PromotionItemInput(
                            product_id=p.id,
                            discount_type="percentage",
                            discount_value=d_val,
                        )
                    )

            req = GeneratePromotionRequest(
                business_id=business_id,
                branch_id=branch_id,
                promotion_type=promotion_type or "discount",
                start_date=s_date,
                end_date=e_date,
                items=promo_items,
                min_margin_pct=Decimal(str(min_margin_pct)) if min_margin_pct is not None else None,
                persist=persist,
            )

            coro = promotion_service.generate_plan(db, business_id=business_id, request=req)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    result = pool.submit(asyncio.run, coro).result()
            else:
                result = asyncio.run(coro)

            return {
                "summary": f"Generated promotion plan: '{result.plan.title}' with {len(result.plan.items)} item(s). Financially validated: {result.plan.is_financially_validated}.",
                "data": {
                    "status": "success",
                    "plan": result.plan.model_dump(mode="json"),
                    "data_summary": result.data_summary,
                },
            }
    except Exception as e:
        logger.warning(f"Error executing promotion planner for business {business_id}: {type(e).__name__}: {str(e)}")
        return {
            "summary": f"Promotion Planner failed: {str(e)}",
            "data": None,
            "error": str(e),
        }



def execute_invoke_artifact_service(business_id: int, artifact_type: Optional[str] = None) -> Dict[str, Any]:
    """Stub tool for Artifact Service."""
    return {
        "summary": "Artifact service is not yet available in this environment.",
        "data": {
            "status": "not_available",
            "service": "artifact_service",
            "message": "Artifact service is not yet available in this environment.",
            "business_id": business_id,
            "artifact_type": artifact_type,
        },
    }


def execute_tool_by_name(
    tool_name: str,
    tool_args: Dict[str, Any],
    db: Session,
    business_id: int,
) -> Dict[str, Any]:
    """
    Safely dispatch a tool execution by name.
    Always forces business_id to match the authorized tenant.
    Never raises uncaught exceptions.
    """
    safe_args = dict(tool_args or {})
    # Always override business_id with authorized business_id
    safe_args["business_id"] = business_id

    try:
        if tool_name == "business_summary":
            return execute_business_summary(db, business_id)
        elif tool_name == "sales_analytics":
            return execute_sales_analytics(
                db,
                business_id,
                period=safe_args.get("period"),
                branch_id=safe_args.get("branch_id"),
            )
        elif tool_name == "expense_summary":
            return execute_expense_summary(
                db,
                business_id,
                period=safe_args.get("period"),
                branch_id=safe_args.get("branch_id"),
                category=safe_args.get("category"),
            )
        elif tool_name == "product_catalog":
            return execute_product_catalog(
                db,
                business_id,
                category=safe_args.get("category"),
                active_only=safe_args.get("active_only"),
            )
        elif tool_name == "invoke_forecasting":
            return execute_invoke_forecasting(
                business_id,
                db=db,
                branch_id=safe_args.get("branch_id"),
                product_id=safe_args.get("product_id"),
                horizon_days=safe_args.get("horizon_days", 7),
                window_size=safe_args.get("window_size", 7),
                metric=safe_args.get("metric"),
            )
        elif tool_name == "invoke_action_center":
            return execute_invoke_action_center(
                business_id,
                db=db,
                action=safe_args.get("action", "generate"),
                branch_id=safe_args.get("branch_id"),
                product_id=safe_args.get("product_id"),
                category=safe_args.get("category"),
                lookback_days=safe_args.get("lookback_days", 30),
            )
        elif tool_name == "invoke_promotion_planner":
            return execute_invoke_promotion_planner(
                business_id,
                db=db,
                action=safe_args.get("action", "generate"),
                promotion_type=safe_args.get("promotion_type"),
                product_ids=safe_args.get("product_ids"),
                items=safe_args.get("items"),
                discount_pct=safe_args.get("discount_pct"),
                start_date=safe_args.get("start_date"),
                end_date=safe_args.get("end_date"),
                branch_id=safe_args.get("branch_id"),
                min_margin_pct=safe_args.get("min_margin_pct"),
                plan_id=safe_args.get("plan_id"),
                persist=safe_args.get("persist", False),
                params=safe_args.get("params"),
            )

        elif tool_name == "invoke_artifact_service":
            return execute_invoke_artifact_service(
                business_id,
                artifact_type=safe_args.get("artifact_type"),
            )
        else:
            return {
                "summary": f"Unknown tool: {tool_name}",
                "data": None,
                "error": f"Tool '{tool_name}' is not recognized.",
            }
    except Exception as e:
        logger.warning(f"Error executing tool {tool_name}: {type(e).__name__}")
        return {
            "summary": f"Tool execution failed for {tool_name}",
            "data": None,
            "error": "A tool execution error occurred.",
        }


def get_agent_tools(db: Session, business_id: int) -> List[BaseTool]:
    """
    Create LangChain BaseTool wrappers bound to the authorized db session and business_id.
    Prevents cross-tenant parameter poisoning by forcing business_id.
    """
    bound_business_id = business_id
    bound_db = db

    @tool
    def business_summary(business_id: Optional[int] = None) -> dict:
        """Get a high-level summary of the business including branches, member count, and recent activity."""
        return execute_business_summary(bound_db, bound_business_id)

    @tool
    def sales_analytics(
        period: Optional[str] = None,
        branch_id: Optional[int] = None,
        business_id: Optional[int] = None,
    ) -> dict:
        """Analyze sales, revenue, and product volumes for the business."""
        return execute_sales_analytics(bound_db, bound_business_id, period=period, branch_id=branch_id)

    @tool
    def expense_summary(
        period: Optional[str] = None,
        branch_id: Optional[int] = None,
        category: Optional[str] = None,
        business_id: Optional[int] = None,
    ) -> dict:
        """Get expense breakdown, category totals, and recent expenses for the business."""
        return execute_expense_summary(
            bound_db, bound_business_id, period=period, branch_id=branch_id, category=category
        )

    @tool
    def product_catalog(
        category: Optional[str] = None,
        active_only: Optional[bool] = None,
        business_id: Optional[int] = None,
    ) -> dict:
        """View products in the catalog with category, SKU, and active status."""
        return execute_product_catalog(
            bound_db, bound_business_id, category=category, active_only=active_only
        )

    @tool
    def invoke_forecasting(
        branch_id: Optional[int] = None,
        product_id: Optional[int] = None,
        horizon_days: int = 7,
        window_size: int = 7,
        metric: Optional[str] = None,
        business_id: Optional[int] = None,
    ) -> dict:
        """Generate demand forecasts for a product at a branch using historical sales observations."""
        return execute_invoke_forecasting(
            bound_business_id,
            db=bound_db,
            branch_id=branch_id,
            product_id=product_id,
            horizon_days=horizon_days,
            window_size=window_size,
            metric=metric,
        )


    @tool
    def invoke_action_center(
        action: Optional[str] = "generate",
        branch_id: Optional[int] = None,
        product_id: Optional[int] = None,
        category: Optional[str] = None,
        lookback_days: Optional[int] = 30,
        business_id: Optional[int] = None,
    ) -> dict:
        """Generate and evaluate actionable business recommendations across inventory, sales, demand forecasting, and expenses."""
        return execute_invoke_action_center(
            bound_business_id,
            db=bound_db,
            action=action,
            branch_id=branch_id,
            product_id=product_id,
            category=category,
            lookback_days=lookback_days or 30,
        )

    @tool
    def invoke_promotion_planner(
        action: Optional[str] = "generate",
        promotion_type: Optional[str] = "discount",
        product_ids: Optional[List[int]] = None,
        discount_pct: Optional[float] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        branch_id: Optional[int] = None,
        min_margin_pct: Optional[float] = None,
        plan_id: Optional[int] = None,
        persist: bool = False,
        params: Optional[dict] = None,
        business_id: Optional[int] = None,
    ) -> dict:
        """Create, list, or evaluate promotional plans (discounts, bundles, time-limited offers) with deterministic financial calculations."""
        return execute_invoke_promotion_planner(
            bound_business_id,
            db=bound_db,
            action=action,
            promotion_type=promotion_type,
            product_ids=product_ids,
            discount_pct=discount_pct,
            start_date=start_date,
            end_date=end_date,
            branch_id=branch_id,
            min_margin_pct=min_margin_pct,
            plan_id=plan_id,
            persist=persist,
            params=params,
        )


    @tool
    def invoke_artifact_service(
        artifact_type: Optional[str] = None,
        business_id: Optional[int] = None,
    ) -> dict:
        """Generate or retrieve business artifacts and reports (stub service)."""
        return execute_invoke_artifact_service(bound_business_id, artifact_type=artifact_type)

    return [
        business_summary,
        sales_analytics,
        expense_summary,
        product_catalog,
        invoke_forecasting,
        invoke_action_center,
        invoke_promotion_planner,
        invoke_artifact_service,
    ]
