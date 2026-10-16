from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.models.user import User
from app.models.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import get_current_user, require_business_membership
from app.handlers import expense_handler

router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/expenses",
    tags=["Expenses"],
)


@router.post("", status_code=201, dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def create_expense(
    business_id: int,
    data: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return expense_handler.create_expense_handler(business_id, data, current_user, db)


@router.get("", dependencies=[Depends(require_business_membership())])
def list_expenses(
    business_id: int,
    branch_id: Optional[int] = None,
    category: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    params = PaginationParams(page=page, page_size=page_size)
    return expense_handler.list_expenses_handler(business_id, branch_id, category, params, db)


@router.get("/{expense_id}", dependencies=[Depends(require_business_membership())])
def get_expense(
    business_id: int,
    expense_id: int,
    db: Session = Depends(get_db),
):
    return expense_handler.get_expense_handler(business_id, expense_id, db)


@router.patch("/{expense_id}", dependencies=[Depends(require_business_membership(["owner", "admin", "manager"]))])
def update_expense(
    business_id: int,
    expense_id: int,
    data: ExpenseUpdate,
    db: Session = Depends(get_db),
):
    return expense_handler.update_expense_handler(business_id, expense_id, data, db)


@router.delete("/{expense_id}", dependencies=[Depends(require_business_membership(["owner", "admin"]))])
def delete_expense(
    business_id: int,
    expense_id: int,
    db: Session = Depends(get_db),
):
    return expense_handler.delete_expense_handler(business_id, expense_id, db)
