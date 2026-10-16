from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.branch import Branch
from app.models.expense import Expense
from app.models.user import User
from app.models.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.helpers.exceptions import NotFoundException
from app.helpers.pagination import paginate_query


def create_expense(
    db: Session,
    business_id: int,
    data: ExpenseCreate,
    current_user: User,
) -> Expense:
    if data.branch_id is not None:
        branch = db.query(Branch).filter(
            Branch.id == data.branch_id,
            Branch.business_id == business_id,
        ).first()
        if not branch:
            raise NotFoundException(
                message="Branch not found",
                errors={"branch_id": f"Branch with ID {data.branch_id} does not exist in this business"},
            )

    expense = Expense(
        business_id=business_id,
        branch_id=data.branch_id,
        expense_date=data.expense_date,
        category=data.category,
        description=data.description,
        amount=data.amount,
        currency=data.currency,
        source_submission_id=data.source_submission_id,
        source_row_number=data.source_row_number,
        created_by_user_id=current_user.id,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def list_expenses(
    db: Session,
    business_id: int,
    branch_id: Optional[int] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list[Expense], dict]:
    query = db.query(Expense).filter(Expense.business_id == business_id)
    if branch_id is not None:
        query = query.filter(Expense.branch_id == branch_id)
    if category is not None:
        query = query.filter(Expense.category == category)
    query = query.order_by(Expense.expense_date.desc(), Expense.id.desc())
    return paginate_query(query, page, page_size)


def get_expense(db: Session, business_id: int, expense_id: int) -> Expense:
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.business_id == business_id,
    ).first()
    if not expense:
        raise NotFoundException(
            message="Expense not found",
            errors={"expense": f"Expense with ID {expense_id} does not exist in this business"},
        )
    return expense


def update_expense(
    db: Session,
    business_id: int,
    expense_id: int,
    data: ExpenseUpdate,
) -> Expense:
    expense = get_expense(db, business_id, expense_id)
    update_data = data.model_dump(exclude_unset=True)

    if "branch_id" in update_data and update_data["branch_id"] is not None:
        branch = db.query(Branch).filter(
            Branch.id == update_data["branch_id"],
            Branch.business_id == business_id,
        ).first()
        if not branch:
            raise NotFoundException(
                message="Branch not found",
                errors={"branch_id": f"Branch with ID {update_data['branch_id']} does not exist in this business"},
            )

    for key, value in update_data.items():
        setattr(expense, key, value)

    db.commit()
    db.refresh(expense)
    return expense


def delete_expense(db: Session, business_id: int, expense_id: int) -> None:
    expense = get_expense(db, business_id, expense_id)
    db.delete(expense)
    db.commit()
