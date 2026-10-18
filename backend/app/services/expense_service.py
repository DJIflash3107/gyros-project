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
        status=data.status if getattr(data, "status", None) else "active",
        created_by_user_id=current_user.id,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def create_expenses_batch(
    db: Session,
    business_id: int,
    items: list[ExpenseCreate],
    current_user: User,
) -> Tuple[list[Expense], dict]:
    branch_ids = {item.branch_id for item in items if item.branch_id is not None}
    if branch_ids:
        existing_branch_ids = {
            b.id for b in db.query(Branch.id).filter(Branch.id.in_(branch_ids), Branch.business_id == business_id).all()
        }
        invalid_branches = branch_ids - existing_branch_ids
        if invalid_branches:
            raise NotFoundException(
                message="One or more branches not found",
                errors={"branch_id": f"Branches {list(invalid_branches)} do not exist in business {business_id}"},
            )

    expenses_to_add = [
        Expense(
            business_id=business_id,
            branch_id=item.branch_id,
            expense_date=item.expense_date,
            category=item.category,
            description=item.description,
            amount=item.amount,
            currency=item.currency,
            source_submission_id=item.source_submission_id,
            source_row_number=item.source_row_number,
            status=item.status if getattr(item, "status", None) else "active",
            created_by_user_id=current_user.id,
        )
        for item in items
    ]
    db.add_all(expenses_to_add)
    db.commit()
    for exp in expenses_to_add:
        db.refresh(exp)

    total_amount = sum(item.amount for item in items)
    summary = {
        "total_saved": len(expenses_to_add),
        "total_amount": float(total_amount),
    }
    return expenses_to_add, summary


def approve_expenses(
    db: Session,
    business_id: int,
    expense_ids: list[int],
) -> Tuple[list[Expense], int]:
    """
    Approve draft expenses after user review:
    - If expense has source_submission_id -> status becomes 'ready'
    - If standalone expense (source_submission_id is None) -> status becomes 'active'
    """
    expenses = db.query(Expense).filter(
        Expense.id.in_(expense_ids),
        Expense.business_id == business_id,
        Expense.status == "draft",
    ).all()

    if not expenses:
        raise NotFoundException(
            message="No draft expenses found to approve",
            errors={"expense_ids": f"No draft expenses with IDs {expense_ids} found in business {business_id}"},
        )

    updated = []
    for exp in expenses:
        if exp.source_submission_id is not None:
            exp.status = "ready"
        else:
            exp.status = "active"
        updated.append(exp)

    db.commit()
    for exp in updated:
        db.refresh(exp)
    return updated, len(updated)


def activate_expenses_by_submission(
    db: Session,
    business_id: int,
    submission_id: int,
) -> int:
    """
    Transition all expenses with status 'ready' linked to submission_id to 'active'.
    Called when SalesReportSubmission is confirmed.
    """
    ready_expenses = db.query(Expense).filter(
        Expense.business_id == business_id,
        Expense.source_submission_id == submission_id,
        Expense.status == "ready",
    ).all()

    count = len(ready_expenses)
    for exp in ready_expenses:
        exp.status = "active"

    return count


def discard_draft_expenses(
    db: Session,
    business_id: int,
    expense_ids: list[int],
) -> int:
    """
    Discard (delete) draft expenses that were rejected during user review.
    """
    expenses = db.query(Expense).filter(
        Expense.id.in_(expense_ids),
        Expense.business_id == business_id,
        Expense.status == "draft",
    ).all()

    if not expenses:
        raise NotFoundException(
            message="No draft expenses found to discard",
            errors={"expense_ids": f"No draft expenses with IDs {expense_ids} found in business {business_id}"},
        )

    count = len(expenses)
    for exp in expenses:
        db.delete(exp)
    db.commit()
    return count


def list_expenses(
    db: Session,
    business_id: int,
    branch_id: Optional[int] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list[Expense], dict]:
    query = db.query(Expense).filter(Expense.business_id == business_id)
    if branch_id is not None:
        query = query.filter(Expense.branch_id == branch_id)
    if category is not None:
        query = query.filter(Expense.category == category)
    if status is not None:
        if status != "all":
            query = query.filter(Expense.status == status)
    else:
        query = query.filter(Expense.status == "active")
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
