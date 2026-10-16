from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.schemas.sales_report_observation import (
    SalesReportObservationCreate,
    SalesReportObservationUpdate,
    SalesReportObservationResponse,
)
from app.models.schemas.pagination import PaginationParams
from app.services import sales_report_observation_service
from app.helpers.response import success_response, paginated_response


def create_observation_handler(
    business_id: int,
    data: SalesReportObservationCreate,
    current_user: User,
    db: Session,
) -> JSONResponse:
    observation = sales_report_observation_service.create_observation(db, business_id, data, current_user)
    return success_response(
        message="Observation created successfully",
        data={"observation": SalesReportObservationResponse.model_validate(observation).model_dump()},
        status_code=201,
    )


def list_observations_handler(
    business_id: int,
    branch_id: Optional[int],
    product_id: Optional[int],
    record_status: Optional[str],
    params: PaginationParams,
    db: Session,
) -> JSONResponse:
    items, pagination = sales_report_observation_service.list_observations(
        db, business_id, branch_id, product_id, record_status, params.page, params.page_size
    )
    response_items = [SalesReportObservationResponse.model_validate(o).model_dump() for o in items]
    return paginated_response(
        message="Observations retrieved successfully",
        items=response_items,
        resource_key="observations",
        pagination=pagination,
    )


def get_observation_handler(business_id: int, observation_id: int, db: Session) -> JSONResponse:
    observation = sales_report_observation_service.get_observation(db, business_id, observation_id)
    return success_response(
        message="Observation retrieved successfully",
        data={"observation": SalesReportObservationResponse.model_validate(observation).model_dump()},
    )


def update_observation_handler(
    business_id: int,
    observation_id: int,
    data: SalesReportObservationUpdate,
    current_user: User,
    db: Session,
) -> JSONResponse:
    observation = sales_report_observation_service.update_observation(db, business_id, observation_id, data, current_user)
    return success_response(
        message="Observation updated successfully",
        data={"observation": SalesReportObservationResponse.model_validate(observation).model_dump()},
    )


def delete_observation_handler(business_id: int, observation_id: int, db: Session) -> JSONResponse:
    sales_report_observation_service.delete_observation(db, business_id, observation_id)
    return success_response(
        message="Observation deleted successfully",
        data={},
    )
