from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.schemas.forecasting import (
    ForecastRequest,
    ForecastEvaluateRequest,
    ForecastRunResponse,
    EvaluationResponse,
    DataSufficiencyResponse,
)
from app.models.schemas.pagination import PaginationParams
from app.services import forecasting_service
from app.helpers.response import success_response, paginated_response


def generate_forecast_handler(
    business_id: int,
    data: ForecastRequest,
    current_user: User,
    db: Session,
) -> JSONResponse:
    run = forecasting_service.generate_forecast(
        db,
        business_id=business_id,
        data=data,
        current_user_id=current_user.id,
    )
    msg = (
        "Forecast generated successfully"
        if run.is_reliable
        else "Forecast generated with reliability warning"
    )
    return success_response(
        message=msg,
        data={"forecast_run": ForecastRunResponse.model_validate(run).model_dump(mode="json")},
        status_code=200,
    )


def evaluate_forecast_handler(
    business_id: int,
    data: ForecastEvaluateRequest,
    db: Session,
) -> JSONResponse:
    evaluation = forecasting_service.evaluate_forecast(db, business_id, data)
    return success_response(
        message="Forecast evaluation completed",
        data={"evaluation": EvaluationResponse.model_validate(evaluation).model_dump(mode="json")},
        status_code=200,
    )


def check_sufficiency_handler(
    business_id: int,
    branch_id: int,
    product_id: int,
    db: Session,
) -> JSONResponse:
    sufficiency = forecasting_service.check_data_sufficiency(db, business_id, branch_id, product_id)
    return success_response(
        message="Data sufficiency check completed",
        data={"sufficiency": DataSufficiencyResponse.model_validate(sufficiency).model_dump(mode="json")},
        status_code=200,
    )


def get_run_handler(
    business_id: int,
    run_id: int,
    db: Session,
) -> JSONResponse:
    run = forecasting_service.get_forecast_run(db, business_id, run_id)
    return success_response(
        message="Forecast run retrieved successfully",
        data={"forecast_run": ForecastRunResponse.model_validate(run).model_dump(mode="json")},
        status_code=200,
    )


def list_runs_handler(
    business_id: int,
    branch_id: Optional[int],
    product_id: Optional[int],
    params: PaginationParams,
    db: Session,
) -> JSONResponse:
    items, pagination = forecasting_service.list_forecast_runs(
        db,
        business_id,
        branch_id,
        product_id,
        params.page,
        params.page_size,
    )
    response_items = [ForecastRunResponse.model_validate(r).model_dump(mode="json") for r in items]
    return paginated_response(
        message="Forecast runs retrieved successfully",
        items=response_items,
        resource_key="forecast_runs",
        pagination=pagination,
    )
