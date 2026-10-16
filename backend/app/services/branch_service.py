from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.branch import Branch
from app.models.schemas.branch import BranchCreate, BranchUpdate
from app.helpers.exceptions import NotFoundException, ConflictException
from app.helpers.pagination import paginate_query


def create_branch(db: Session, business_id: int, data: BranchCreate) -> Branch:
    existing = db.query(Branch).filter(
        Branch.business_id == business_id,
        Branch.name == data.name,
    ).first()
    if existing:
        raise ConflictException(
            message="Branch creation failed",
            errors={"name": f"A branch with the name '{data.name}' already exists in this business"},
        )

    branch = Branch(
        business_id=business_id,
        name=data.name,
        branch_code=data.branch_code,
        address=data.address,
        is_active=data.is_active,
    )
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return branch


def list_branches(
    db: Session,
    business_id: int,
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list[Branch], dict]:
    query = db.query(Branch).filter(Branch.business_id == business_id)
    if is_active is not None:
        query = query.filter(Branch.is_active == is_active)
    query = query.order_by(Branch.id.asc())
    return paginate_query(query, page, page_size)


def get_branch(db: Session, business_id: int, branch_id: int) -> Branch:
    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.business_id == business_id,
    ).first()
    if not branch:
        raise NotFoundException(
            message="Branch not found",
            errors={"branch": f"Branch with ID {branch_id} does not exist in this business"},
        )
    return branch


def update_branch(db: Session, business_id: int, branch_id: int, data: BranchUpdate) -> Branch:
    branch = get_branch(db, business_id, branch_id)
    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] != branch.name:
        existing = db.query(Branch).filter(
            Branch.business_id == business_id,
            Branch.name == update_data["name"],
        ).first()
        if existing:
            raise ConflictException(
                message="Branch update failed",
                errors={"name": f"A branch with the name '{update_data['name']}' already exists in this business"},
            )

    for key, value in update_data.items():
        setattr(branch, key, value)

    db.commit()
    db.refresh(branch)
    return branch


def delete_branch(db: Session, business_id: int, branch_id: int) -> None:
    branch = get_branch(db, business_id, branch_id)
    db.delete(branch)
    db.commit()
