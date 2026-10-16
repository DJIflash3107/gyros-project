from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.models.user import User
from app.models.schemas.user import UserCreate, UserUpdate
from app.models.schemas.pagination import PaginationParams
from app.middlewares.auth import get_current_user
from app.handlers import user_handler

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.post("", status_code=201, dependencies=[Depends(get_current_user)])
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
):
    return user_handler.create_user_handler(data, db)


@router.get("", dependencies=[Depends(get_current_user)])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    params = PaginationParams(page=page, page_size=page_size)
    return user_handler.list_users_handler(params, db)


@router.get("/{user_id}", dependencies=[Depends(get_current_user)])
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    return user_handler.get_user_handler(user_id, db)


@router.patch("/{user_id}", dependencies=[Depends(get_current_user)])
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
):
    return user_handler.update_user_handler(user_id, data, db)


@router.delete("/{user_id}", dependencies=[Depends(get_current_user)])
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    return user_handler.delete_user_handler(user_id, db)
