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



def execute_invoke_action_center(business_id: int, action: Optional[str] = None) -> Dict[str, Any]:
    """Stub tool for Business Action Center."""
    return {
        "summary": "Business Action Center service is not yet available in this environment.",
        "data": {
            "status": "not_available",
            "service": "action_center",
            "message": "Business Action Center service is not yet available in this environment.",
            "business_id": business_id,
            "action": action,
        },
    }


def execute_invoke_promotion_planner(business_id: int, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Stub tool for Promotion Planner."""
    return {
        "summary": "Promotion Planner service is not yet available in this environment.",
        "data": {
            "status": "not_available",
            "service": "promotion_planner",
            "message": "Promotion Planner service is not yet available in this environment.",
            "business_id": business_id,
            "params": params,
        },
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
                action=safe_args.get("action"),
            )
        elif tool_name == "invoke_promotion_planner":
            return execute_invoke_promotion_planner(
                business_id,
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
        action: Optional[str] = None,
        business_id: Optional[int] = None,
    ) -> dict:
        """Invoke Business Action Center recommendations (stub service)."""
        return execute_invoke_action_center(bound_business_id, action=action)

    @tool
    def invoke_promotion_planner(
        params: Optional[dict] = None,
        business_id: Optional[int] = None,
    ) -> dict:
        """Create or evaluate promotion plans (stub service)."""
        return execute_invoke_promotion_planner(bound_business_id, params=params)

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
