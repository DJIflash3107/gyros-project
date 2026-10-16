from typing import Optional, Tuple
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from app.models.product import Product
from app.models.product_price_history import ProductPriceHistory
from app.models.user import User
from app.models.schemas.product_price_history import (
    ProductPriceHistoryCreate,
    ProductPriceHistoryUpdate,
)
from app.helpers.exceptions import NotFoundException, ConflictException, ValidationException
from app.helpers.pagination import paginate_query


def check_price_history_overlap(
    db: Session,
    business_id: int,
    product_id: int,
    start_date,
    end_date,
    exclude_id: Optional[int] = None,
):
    query = db.query(ProductPriceHistory).filter(
        ProductPriceHistory.business_id == business_id,
        ProductPriceHistory.product_id == product_id,
        or_(
            ProductPriceHistory.effective_to.is_(None),
            ProductPriceHistory.effective_to >= start_date,
        ),
    )
    if end_date is not None:
        query = query.filter(ProductPriceHistory.effective_from <= end_date)
    if exclude_id is not None:
        query = query.filter(ProductPriceHistory.id != exclude_id)

    overlap = query.first()
    if overlap:
        raise ConflictException(
            message="Product price period overlap detected",
            errors={
                "effective_period": (
                    f"A price history record already exists for product {product_id} "
                    f"overlapping with period starting {start_date} (existing from {overlap.effective_from} to {overlap.effective_to})"
                )
            },
        )


def create_price_history(
    db: Session,
    business_id: int,
    data: ProductPriceHistoryCreate,
    current_user: User,
) -> ProductPriceHistory:
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

    check_price_history_overlap(
        db,
        business_id=business_id,
        product_id=data.product_id,
        start_date=data.effective_from,
        end_date=data.effective_to,
    )

    price_history = ProductPriceHistory(
        business_id=business_id,
        product_id=data.product_id,
        effective_from=data.effective_from,
        effective_to=data.effective_to,
        selling_price=data.selling_price,
        price_unit=data.price_unit,
        source_submission_id=data.source_submission_id,
        created_by_user_id=current_user.id,
    )
    db.add(price_history)
    db.commit()
    db.refresh(price_history)
    return price_history


def list_price_history(
    db: Session,
    business_id: int,
    product_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list[ProductPriceHistory], dict]:
    query = db.query(ProductPriceHistory).filter(ProductPriceHistory.business_id == business_id)
    if product_id is not None:
        query = query.filter(ProductPriceHistory.product_id == product_id)
    query = query.order_by(ProductPriceHistory.effective_from.desc())
    return paginate_query(query, page, page_size)


def get_price_history(db: Session, business_id: int, price_id: int) -> ProductPriceHistory:
    price_history = db.query(ProductPriceHistory).filter(
        ProductPriceHistory.id == price_id,
        ProductPriceHistory.business_id == business_id,
    ).first()
    if not price_history:
        raise NotFoundException(
            message="Price history record not found",
            errors={"price_history": f"Price history with ID {price_id} does not exist in this business"},
        )
    return price_history


def update_price_history(
    db: Session,
    business_id: int,
    price_id: int,
    data: ProductPriceHistoryUpdate,
) -> ProductPriceHistory:
    price_history = get_price_history(db, business_id, price_id)
    update_data = data.model_dump(exclude_unset=True)

    if "effective_to" in update_data:
        new_effective_to = update_data["effective_to"]
        if new_effective_to is not None and new_effective_to <= price_history.effective_from:
            raise ValidationException(
                message="Invalid effective date range",
                errors={"effective_to": "effective_to must be strictly greater than effective_from"},
            )
        check_price_history_overlap(
            db,
            business_id=business_id,
            product_id=price_history.product_id,
            start_date=price_history.effective_from,
            end_date=new_effective_to,
            exclude_id=price_history.id,
        )

    for key, value in update_data.items():
        setattr(price_history, key, value)

    db.commit()
    db.refresh(price_history)
    return price_history


def delete_price_history(db: Session, business_id: int, price_id: int) -> None:
    price_history = get_price_history(db, business_id, price_id)
    db.delete(price_history)
    db.commit()
