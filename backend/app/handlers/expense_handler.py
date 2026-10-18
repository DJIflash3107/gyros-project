from datetime import date
from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.schemas.expense import (
    ExpenseCreate,
    ExpenseBatchCreate,
    ExpenseUpdate,
    ExpenseResponse,
    ExpenseReviewRequest,
)
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


def create_expenses_batch_handler(business_id: int, data: ExpenseBatchCreate, current_user: User, db: Session) -> JSONResponse:
    from app.services.background_job_service import enqueue_job
    job = enqueue_job(db, business_id, current_user.id, "expense_batch_create", {"items": [item.model_dump(mode="json") for item in data.items]})
    return success_response("Expense batch queued", {"job_id": job['id'], "status": job["status"], "status_url": f"/api/v1/businesses/{business_id}/jobs/{job['id']}",}, status_code=202)

def list_expenses_handler(
    business_id: int,
    branch_id: Optional[int],
    category: Optional[str],
    status: Optional[str],
    params: PaginationParams,
    db: Session,
) -> JSONResponse:
    items, pagination = expense_service.list_expenses(db, business_id, branch_id, category, status, params.page, params.page_size)
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


async def import_expenses_handler(business_id: int, files: list, input_method: str, branch_id: Optional[int], default_date: Optional[date], current_user: User, db: Session, source_submission_id: Optional[int] = None) -> JSONResponse:
    from app.services.background_job_service import enqueue_job
    from app.services.background_job_worker import store_upload, delete_upload
    stored = []
    try:
        for index, upload in enumerate(files, start=1):
            content = await upload.read()
            filename = upload.filename or f"expense_import_{index}"
            stored.append({"storage_key": store_upload(business_id, filename, content), "filename": filename, "mime_type": upload.content_type or "application/octet-stream"})
        job = enqueue_job(db, business_id, current_user.id, "expense_import", {"files": stored, "input_method": input_method, "branch_id": branch_id, "default_date": default_date.isoformat() if default_date else None, "source_submission_id": source_submission_id})
    except Exception:
        for item in stored:
            delete_upload(item["storage_key"])
        raise
    return success_response("Expense import queued", {"job_id": job['id'], "status": job["status"], "status_url": f"/api/v1/businesses/{business_id}/jobs/{job['id']}",}, status_code=202)

def approve_expenses_handler(
    business_id: int,
    data: ExpenseReviewRequest,
    db: Session,
) -> JSONResponse:
    expenses, count = expense_service.approve_expenses(db, business_id, data.expense_ids)
    return success_response(
        message=f"{count} expenses approved successfully",
        data={
            "updated_count": count,
            "expenses": [ExpenseResponse.model_validate(e).model_dump() for e in expenses],
        },
    )


def discard_expenses_handler(
    business_id: int,
    data: ExpenseReviewRequest,
    db: Session,
) -> JSONResponse:
    count = expense_service.discard_draft_expenses(db, business_id, data.expense_ids)
    return success_response(
        message=f"{count} draft expenses discarded successfully",
        data={"deleted_count": count},
    )




