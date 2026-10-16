from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.schemas.user import UserCreate, UserUpdate, UserResponse
from app.models.schemas.pagination import PaginationParams
from app.services import user_service
from app.helpers.response import success_response, paginated_response


def create_user_handler(data: UserCreate, db: Session) -> JSONResponse:
    user = user_service.create_user(db, data)
    return success_response(
        message="User created successfully",
        data={"user": UserResponse.model_validate(user).model_dump()},
        status_code=201,
    )


def list_users_handler(params: PaginationParams, db: Session) -> JSONResponse:
    items, pagination = user_service.list_users(db, params.page, params.page_size)
    response_items = [UserResponse.model_validate(u).model_dump() for u in items]
    return paginated_response(
        message="Users retrieved successfully",
        items=response_items,
        resource_key="users",
        pagination=pagination,
    )


def get_user_handler(user_id: int, db: Session) -> JSONResponse:
    user = user_service.get_user(db, user_id)
    return success_response(
        message="User retrieved successfully",
        data={"user": UserResponse.model_validate(user).model_dump()},
    )


def update_user_handler(user_id: int, data: UserUpdate, db: Session) -> JSONResponse:
    user = user_service.update_user(db, user_id, data)
    return success_response(
        message="User updated successfully",
        data={"user": UserResponse.model_validate(user).model_dump()},
    )


def delete_user_handler(user_id: int, db: Session) -> JSONResponse:
    user_service.delete_user(db, user_id)
    return success_response(
        message="User deleted successfully",
        data={},
    )
