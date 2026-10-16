from typing import Tuple
from sqlalchemy.orm import Session
from app.models.business_membership import BusinessMembership
from app.models.user import User
from app.models.schemas.business_membership import BusinessMembershipCreate, BusinessMembershipUpdate
from app.helpers.exceptions import NotFoundException, ConflictException
from app.helpers.pagination import paginate_query


def create_membership(db: Session, business_id: int, data: BusinessMembershipCreate) -> BusinessMembership:
    # Check if target user exists
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise NotFoundException(
            message="User not found",
            errors={"user_id": f"User with ID {data.user_id} does not exist"},
        )

    existing = db.query(BusinessMembership).filter(
        BusinessMembership.business_id == business_id,
        BusinessMembership.user_id == data.user_id,
    ).first()
    if existing:
        raise ConflictException(
            message="Membership already exists",
            errors={"membership": "User is already a member of this business"},
        )

    membership = BusinessMembership(
        business_id=business_id,
        user_id=data.user_id,
        role=data.role,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def list_memberships(db: Session, business_id: int, page: int = 1, page_size: int = 20) -> Tuple[list[BusinessMembership], dict]:
    query = (
        db.query(BusinessMembership)
        .filter(BusinessMembership.business_id == business_id)
        .order_by(BusinessMembership.id.asc())
    )
    return paginate_query(query, page, page_size)


def get_membership(db: Session, business_id: int, membership_id: int) -> BusinessMembership:
    membership = db.query(BusinessMembership).filter(
        BusinessMembership.id == membership_id,
        BusinessMembership.business_id == business_id,
    ).first()
    if not membership:
        raise NotFoundException(
            message="Membership not found",
            errors={"membership": f"Membership with ID {membership_id} does not exist in this business"},
        )
    return membership


def update_membership(db: Session, business_id: int, membership_id: int, data: BusinessMembershipUpdate) -> BusinessMembership:
    membership = get_membership(db, business_id, membership_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(membership, key, value)
    db.commit()
    db.refresh(membership)
    return membership


def delete_membership(db: Session, business_id: int, membership_id: int) -> None:
    membership = get_membership(db, business_id, membership_id)
    db.delete(membership)
    db.commit()
