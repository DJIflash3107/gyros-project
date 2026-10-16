"""
Forecasting Service — Orchestration Layer.

Handles database queries for confirmed daily SalesReportObservation records,
validates branch/product existence within business scope, coordinates with the
pure computation forecasting engine, persists forecast runs and prediction results,
and provides retrieval / evaluation interfaces.
"""

from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.product import Product
from app.models.sales_report_observation import SalesReportObservation
from app.models.forecast_run import ForecastRun
from app.models.forecast_result import ForecastResult
from app.models.schemas.forecasting import ForecastRequest, ForecastEvaluateRequest
from app.services import forecasting_engine
from app.helpers.exceptions import NotFoundException
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.pagination import paginate_query


def validate_branch_and_product(db: Session, business_id: int, branch_id: int, product_id: int) -> None:
    """Verifies that the requested branch and product belong to the specified business."""
    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.business_id == business_id,
    ).first()
    if not branch:
        raise NotFoundException(
            message=f"Branch with ID {branch_id} not found in this business",
            errors={"branch_id": f"Branch {branch_id} does not exist in business {business_id}"},
            error_code=ErrorCodeRegistry.FC_BRANCH_NOT_FOUND,
        )

    product = db.query(Product).filter(
        Product.id == product_id,
        Product.business_id == business_id,
    ).first()
    if not product:
        raise NotFoundException(
            message=f"Product with ID {product_id} not found in this business",
            errors={"product_id": f"Product {product_id} does not exist in business {business_id}"},
            error_code=ErrorCodeRegistry.FC_PRODUCT_NOT_FOUND,
        )


def query_sales_observations(
    db: Session,
    business_id: int,
    branch_id: int,
    product_id: int,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Fetches confirmed daily SalesReportObservation records for the branch and product.
    Strictly filters out non-daily granularities, inactive records, and null sold_qty.
    Returns (daily_records, total_active_observation_count).
    """
    daily_obs = (
        db.query(SalesReportObservation)
        .filter(
            SalesReportObservation.business_id == business_id,
            SalesReportObservation.branch_id == branch_id,
            SalesReportObservation.product_id == product_id,
            SalesReportObservation.record_status == "active",
            SalesReportObservation.granularity == "daily",
            SalesReportObservation.sold_qty.isnot(None),
        )
        .order_by(SalesReportObservation.period_start.asc())
        .all()
    )

    total_count = (
        db.query(SalesReportObservation)
        .filter(
            SalesReportObservation.business_id == business_id,
            SalesReportObservation.branch_id == branch_id,
            SalesReportObservation.product_id == product_id,
            SalesReportObservation.record_status == "active",
            SalesReportObservation.sold_qty.isnot(None),
        )
        .count()
    )

    records = [
        {
            "date": obs.period_start,
            "sold_qty": float(obs.sold_qty),
            "granularity": obs.granularity,
        }
        for obs in daily_obs
    ]

    return records, total_count


def check_data_sufficiency(
    db: Session,
    business_id: int,
    branch_id: int,
    product_id: int,
) -> Dict[str, Any]:
    """Validates if sufficient confirmed daily sales observations exist to forecast."""
    validate_branch_and_product(db, business_id, branch_id, product_id)
    records, total_count = query_sales_observations(db, business_id, branch_id, product_id)

    sufficiency = forecasting_engine.check_sufficiency(records, total_raw_count=total_count)
    return {
        "branch_id": branch_id,
        "product_id": product_id,
        **sufficiency,
    }


def generate_forecast(
    db: Session,
    business_id: int,
    data: ForecastRequest,
    current_user_id: Optional[int] = None,
) -> ForecastRun:
    """
    Generates a demand forecast, persists the run and its predictions to the database,
    and returns the created ForecastRun ORM model.
    """
    validate_branch_and_product(db, business_id, data.branch_id, data.product_id)
    records, total_count = query_sales_observations(db, business_id, data.branch_id, data.product_id)

    output = forecasting_engine.forecast(
        records,
        horizon_days=data.horizon_days,
        window_size=data.window_size,
        total_raw_count=total_count,
    )

    run = ForecastRun(
        business_id=business_id,
        branch_id=data.branch_id,
        product_id=data.product_id,
        method=output.method,
        horizon_days=output.horizon_days,
        window_size=output.window_size,
        training_start=output.training_start,
        training_end=output.training_end,
        observations_used=output.observations_used,
        is_reliable=output.is_reliable,
        reliability_note=output.reliability_note,
        created_by_user_id=current_user_id,
    )
    db.add(run)
    db.flush()

    for pt in output.predictions:
        res = ForecastResult(
            forecast_run_id=run.id,
            forecast_date=pt.forecast_date,
            predicted_qty=pt.predicted_qty,
            weekday=pt.weekday,
        )
        db.add(res)

    db.commit()
    db.refresh(run)
    return run


def evaluate_forecast(
    db: Session,
    business_id: int,
    data: ForecastEvaluateRequest,
) -> Dict[str, Any]:
    """
    Runs time-ordered backtesting on historical observations.
    Returns evaluation metrics (MAE, WAPE, forecast bias) and actual vs predicted points.
    """
    validate_branch_and_product(db, business_id, data.branch_id, data.product_id)
    records, _ = query_sales_observations(db, business_id, data.branch_id, data.product_id)

    bt_output = forecasting_engine.backtest(
        records,
        window_size=data.window_size,
        test_days=data.test_days,
    )

    return {
        "branch_id": data.branch_id,
        "product_id": data.product_id,
        "method": bt_output.method,
        "window_size": bt_output.window_size,
        "test_days": bt_output.test_days,
        "training_start": bt_output.training_start,
        "training_end": bt_output.training_end,
        "test_start": bt_output.test_start,
        "test_end": bt_output.test_end,
        "observations_used": bt_output.observations_used,
        "mae": bt_output.mae,
        "wape": bt_output.wape,
        "forecast_bias": bt_output.forecast_bias,
        "is_reliable": bt_output.is_reliable,
        "reliability_note": bt_output.reliability_note,
        "actuals_vs_predicted": bt_output.actuals_vs_predicted,
    }


def get_forecast_run(db: Session, business_id: int, run_id: int) -> ForecastRun:
    """Retrieves a specific ForecastRun along with its prediction points."""
    run = (
        db.query(ForecastRun)
        .filter(
            ForecastRun.id == run_id,
            ForecastRun.business_id == business_id,
        )
        .first()
    )
    if not run:
        raise NotFoundException(
            message=f"Forecast run with ID {run_id} not found in this business",
            errors={"run_id": f"Forecast run {run_id} does not exist in business {business_id}"},
            error_code=ErrorCodeRegistry.FC_RUN_NOT_FOUND,
        )
    return run


def list_forecast_runs(
    db: Session,
    business_id: int,
    branch_id: Optional[int] = None,
    product_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[ForecastRun], dict]:
    """Returns a paginated list of forecast runs for a business."""
    query = db.query(ForecastRun).filter(ForecastRun.business_id == business_id)
    if branch_id is not None:
        query = query.filter(ForecastRun.branch_id == branch_id)
    if product_id is not None:
        query = query.filter(ForecastRun.product_id == product_id)

    query = query.order_by(ForecastRun.created_at.desc(), ForecastRun.id.desc())
    return paginate_query(query, page, page_size)
