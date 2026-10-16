from typing import Tuple
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.schemas.user import UserCreate, UserUpdate
from app.configs.security import hash_password
from app.helpers.exceptions import NotFoundException, ConflictException
from app.helpers.pagination import paginate_query


def create_user(db: Session, data: UserCreate) -> User:
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise ConflictException(
            message="User creation failed",
            errors={"email": "A user with this email already exists"},
        )
    user = User(
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.password) if data.password else None,
        is_active=data.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session, page: int = 1, page_size: int = 20) -> Tuple[list[User], dict]:
    query = db.query(User).order_by(User.id.desc())
    return paginate_query(query, page, page_size)


def get_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException(
            message="User not found",
            errors={"user": f"User with ID {user_id} does not exist"},
        )
    return user


def update_user(db: Session, user_id: int, data: UserUpdate) -> User:
    user = get_user(db, user_id)
    update_data = data.model_dump(exclude_unset=True)

    if "email" in update_data and update_data["email"] != user.email:
        existing = db.query(User).filter(User.email == update_data["email"]).first()
        if existing:
            raise ConflictException(
                message="User update failed",
                errors={"email": "A user with this email already exists"},
            )

    if "password" in update_data:
        password = update_data.pop("password")
        if password:
            user.password_hash = hash_password(password)

    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> None:
    user = get_user(db, user_id)
    db.delete(user)
    db.commit()
