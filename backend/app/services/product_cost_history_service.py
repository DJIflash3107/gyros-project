from typing import Optional, Tuple
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from app.models.product import Product
from app.models.product_cost_history import ProductCostHistory
from app.models.user import User
from app.models.schemas.product_cost_history import (
    ProductCostHistoryCreate,
    ProductCostHistoryUpdate,
)
from app.helpers.exceptions import NotFoundException, ConflictException, ValidationException
from app.helpers.pagination import paginate_query


def check_cost_history_overlap(
    db: Session,
    business_id: int,
    product_id: int,
    start_date,
    end_date,
    exclude_id: Optional[int] = None,
):
    query = db.query(ProductCostHistory).filter(
        ProductCostHistory.business_id == business_id,
        ProductCostHistory.product_id == product_id,
        or_(
            ProductCostHistory.effective_to.is_(None),
            ProductCostHistory.effective_to >= start_date,
        ),
    )
    if end_date is not None:
        query = query.filter(ProductCostHistory.effective_from <= end_date)
    if exclude_id is not None:
        query = query.filter(ProductCostHistory.id != exclude_id)

    overlap = query.first()
    if overlap:
        raise ConflictException(
            message="Product cost period overlap detected",
            errors={
                "effective_period": (
                    f"A cost history record already exists for product {product_id} "
                    f"overlapping with period starting {start_date} (existing from {overlap.effective_from} to {overlap.effective_to})"
                )
            },
        )


def create_cost_history(
    db: Session,
    business_id: int,
    data: ProductCostHistoryCreate,
    current_user: User,
) -> ProductCostHistory:
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

    check_cost_history_overlap(
        db,
        business_id=business_id,
        product_id=data.product_id,
        start_date=data.effective_from,
        end_date=data.effective_to,
    )

    cost_history = ProductCostHistory(
        business_id=business_id,
        product_id=data.product_id,
        effective_from=data.effective_from,
        effective_to=data.effective_to,
        unit_cost=data.unit_cost,
        cost_unit=data.cost_unit,
        source_submission_id=data.source_submission_id,
        created_by_user_id=current_user.id,
    )
    db.add(cost_history)
    db.commit()
    db.refresh(cost_history)
    return cost_history


def list_cost_history(
    db: Session,
    business_id: int,
    product_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list[ProductCostHistory], dict]:
    query = db.query(ProductCostHistory).filter(ProductCostHistory.business_id == business_id)
    if product_id is not None:
        query = query.filter(ProductCostHistory.product_id == product_id)
    query = query.order_by(ProductCostHistory.effective_from.desc())
    return paginate_query(query, page, page_size)


def get_cost_history(db: Session, business_id: int, cost_id: int) -> ProductCostHistory:
    cost_history = db.query(ProductCostHistory).filter(
        ProductCostHistory.id == cost_id,
        ProductCostHistory.business_id == business_id,
    ).first()
    if not cost_history:
        raise NotFoundException(
            message="Cost history record not found",
            errors={"cost_history": f"Cost history with ID {cost_id} does not exist in this business"},
        )
    return cost_history


def update_cost_history(
    db: Session,
    business_id: int,
    cost_id: int,
    data: ProductCostHistoryUpdate,
) -> ProductCostHistory:
    cost_history = get_cost_history(db, business_id, cost_id)
    update_data = data.model_dump(exclude_unset=True)

    if "effective_to" in update_data:
        new_effective_to = update_data["effective_to"]
        if new_effective_to is not None and new_effective_to <= cost_history.effective_from:
            raise ValidationException(
                message="Invalid effective date range",
                errors={"effective_to": "effective_to must be strictly greater than effective_from"},
            )
        check_cost_history_overlap(
            db,
            business_id=business_id,
            product_id=cost_history.product_id,
            start_date=cost_history.effective_from,
            end_date=new_effective_to,
            exclude_id=cost_history.id,
        )

    for key, value in update_data.items():
        setattr(cost_history, key, value)

    db.commit()
    db.refresh(cost_history)
    return cost_history


def delete_cost_history(db: Session, business_id: int, cost_id: int) -> None:
    cost_history = get_cost_history(db, business_id, cost_id)
    db.delete(cost_history)
    db.commit()
