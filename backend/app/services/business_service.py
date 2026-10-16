from typing import Tuple
from sqlalchemy.orm import Session
from app.models.business import Business
from app.models.business_membership import BusinessMembership
from app.models.user import User
from app.models.schemas.business import BusinessCreate, BusinessUpdate
from app.helpers.exceptions import NotFoundException
from app.helpers.pagination import paginate_query


def create_business(db: Session, data: BusinessCreate, current_user: User) -> Business:
    business = Business(
        name=data.name,
        currency=data.currency,
        timezone=data.timezone,
    )
    db.add(business)
    db.flush()

    # Creator automatically becomes the owner
    membership = BusinessMembership(
        business_id=business.id,
        user_id=current_user.id,
        role="owner",
    )
    db.add(membership)
    db.commit()
    db.refresh(business)
    return business


def list_businesses(db: Session, current_user: User, page: int = 1, page_size: int = 20) -> Tuple[list[Business], dict]:
    query = (
        db.query(Business)
        .join(BusinessMembership, BusinessMembership.business_id == Business.id)
        .filter(BusinessMembership.user_id == current_user.id)
        .order_by(Business.id.desc())
    )
    return paginate_query(query, page, page_size)


def get_business(db: Session, business_id: int) -> Business:
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise NotFoundException(
            message="Business not found",
            errors={"business": f"Business with ID {business_id} does not exist"},
        )
    return business


def update_business(db: Session, business_id: int, data: BusinessUpdate) -> Business:
    business = get_business(db, business_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(business, key, value)
    db.commit()
    db.refresh(business)
    return business


def delete_business(db: Session, business_id: int) -> None:
    business = get_business(db, business_id)
    db.delete(business)
    db.commit()
