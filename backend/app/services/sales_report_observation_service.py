from typing import Optional, Tuple
from sqlalchemy import and_
from sqlalchemy.orm import Session
from app.models.branch import Branch
from app.models.product import Product
from app.models.sales_report_observation import SalesReportObservation
from app.models.user import User
from app.models.schemas.sales_report_observation import (
    SalesReportObservationCreate,
    SalesReportObservationUpdate,
)
from app.helpers.exceptions import NotFoundException, ConflictException
from app.helpers.pagination import paginate_query


def check_observation_overlap(
    db: Session,
    business_id: int,
    branch_id: int,
    product_id: int,
    start_date,
    end_date,
    exclude_id: Optional[int] = None,
):
    query = db.query(SalesReportObservation).filter(
        SalesReportObservation.business_id == business_id,
        SalesReportObservation.branch_id == branch_id,
        SalesReportObservation.product_id == product_id,
        SalesReportObservation.record_status == "active",
        and_(
            SalesReportObservation.period_start <= end_date,
            SalesReportObservation.period_end >= start_date,
        ),
    )
    if exclude_id is not None:
        query = query.filter(SalesReportObservation.id != exclude_id)

    overlap = query.first()
    if overlap:
        raise ConflictException(
            message="Observation period overlap detected",
            errors={
                "period": (
                    f"An active observation already exists for branch {branch_id}, product {product_id} "
                    f"overlapping period {start_date} to {end_date} (existing: {overlap.period_start} to {overlap.period_end})"
                )
            },
        )


def create_observation(
    db: Session,
    business_id: int,
    data: SalesReportObservationCreate,
    current_user: User,
) -> SalesReportObservation:
    # Ensure branch belongs to business
    branch = db.query(Branch).filter(
        Branch.id == data.branch_id,
        Branch.business_id == business_id,
    ).first()
    if not branch:
        raise NotFoundException(
            message="Branch not found",
            errors={"branch_id": f"Branch with ID {data.branch_id} does not exist in this business"},
        )

    # Ensure product belongs to business
    product = db.query(Product).filter(
        Product.id == data.product_id,
        Product.business_id == business_id,
    ).first()
    if not product:
        raise NotFoundException(
            message="Product not found",
            errors={"product_id": f"Product with ID {data.product_id} does not exist in this business"},
        )

    # Check for date overlap
    check_observation_overlap(
        db,
        business_id=business_id,
        branch_id=data.branch_id,
        product_id=data.product_id,
        start_date=data.period_start,
        end_date=data.period_end,
    )

    observation = SalesReportObservation(
        business_id=business_id,
        branch_id=data.branch_id,
        product_id=data.product_id,
        source_submission_id=data.source_submission_id,
        source_staging_row_id=data.source_staging_row_id,
        period_start=data.period_start,
        period_end=data.period_end,
        granularity=data.granularity,
        prepared_qty=data.prepared_qty,
        opening_stock_qty=data.opening_stock_qty,
        received_qty=data.received_qty,
        available_stock_qty=data.available_stock_qty,
        sold_qty=data.sold_qty,
        leftover_qty=data.leftover_qty,
        spoiled_qty=data.spoiled_qty,
        damaged_qty=data.damaged_qty,
        staff_meals_qty=data.staff_meals_qty,
        donated_qty=data.donated_qty,
        other_disposition_qty=data.other_disposition_qty,
        recorded_revenue=data.recorded_revenue,
        record_status=data.record_status,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(observation)
    db.commit()
    db.refresh(observation)
    return observation


def list_observations(
    db: Session,
    business_id: int,
    branch_id: Optional[int] = None,
    product_id: Optional[int] = None,
    record_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list[SalesReportObservation], dict]:
    query = db.query(SalesReportObservation).filter(SalesReportObservation.business_id == business_id)
    if branch_id is not None:
        query = query.filter(SalesReportObservation.branch_id == branch_id)
    if product_id is not None:
        query = query.filter(SalesReportObservation.product_id == product_id)
    if record_status is not None:
        query = query.filter(SalesReportObservation.record_status == record_status)
    query = query.order_by(SalesReportObservation.period_start.desc())
    return paginate_query(query, page, page_size)


def get_observation(db: Session, business_id: int, observation_id: int) -> SalesReportObservation:
    observation = db.query(SalesReportObservation).filter(
        SalesReportObservation.id == observation_id,
        SalesReportObservation.business_id == business_id,
    ).first()
    if not observation:
        raise NotFoundException(
            message="Observation not found",
            errors={"observation": f"Observation with ID {observation_id} does not exist in this business"},
        )
    return observation


def update_observation(
    db: Session,
    business_id: int,
    observation_id: int,
    data: SalesReportObservationUpdate,
    current_user: User,
) -> SalesReportObservation:
    observation = get_observation(db, business_id, observation_id)
    update_data = data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(observation, key, value)

    observation.updated_by_user_id = current_user.id
    db.commit()
    db.refresh(observation)
    return observation


def delete_observation(db: Session, business_id: int, observation_id: int) -> None:
    observation = get_observation(db, business_id, observation_id)
    db.delete(observation)
    db.commit()
