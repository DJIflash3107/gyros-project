from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.schemas.expense import ExpenseCreate, ExpenseUpdate, ExpenseResponse
from app.models.schemas.pagination import PaginationParams
from app.services import expense_service
from app.helpers.response import success_response, paginated_response


def create_expense_handler(
    business_id: int,
    data: ExpenseCreate,
    current_user: User,
    db: Session,
) -> JSONResponse:
    expense = expense_service.create_expense(db, business_id, data, current_user)
    return success_response(
        message="Expense created successfully",
        data={"expense": ExpenseResponse.model_validate(expense).model_dump()},
        status_code=201,
    )


def list_expenses_handler(
    business_id: int,
    branch_id: Optional[int],
    category: Optional[str],
    params: PaginationParams,
    db: Session,
) -> JSONResponse:
    items, pagination = expense_service.list_expenses(db, business_id, branch_id, category, params.page, params.page_size)
    response_items = [ExpenseResponse.model_validate(e).model_dump() for e in items]
    return paginated_response(
        message="Expenses retrieved successfully",
        items=response_items,
        resource_key="expenses",
        pagination=pagination,
    )


def get_expense_handler(business_id: int, expense_id: int, db: Session) -> JSONResponse:
    expense = expense_service.get_expense(db, business_id, expense_id)
    return success_response(
        message="Expense retrieved successfully",
        data={"expense": ExpenseResponse.model_validate(expense).model_dump()},
    )


def update_expense_handler(
    business_id: int,
    expense_id: int,
    data: ExpenseUpdate,
    db: Session,
) -> JSONResponse:
    expense = expense_service.update_expense(db, business_id, expense_id, data)
    return success_response(
        message="Expense updated successfully",
        data={"expense": ExpenseResponse.model_validate(expense).model_dump()},
    )


def delete_expense_handler(business_id: int, expense_id: int, db: Session) -> JSONResponse:
    expense_service.delete_expense(db, business_id, expense_id)
    return success_response(
        message="Expense deleted successfully",
        data={},
    )
