from typing import Tuple
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.schemas.auth import RegisterRequest, LoginRequest
from app.configs.security import hash_password, verify_password, create_access_token
from app.helpers.exceptions import ConflictException, AuthenticationException


def register(db: Session, data: RegisterRequest) -> User:
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise ConflictException(
            message="User registration failed",
            errors={"email": "A user with this email already exists"},
        )

    user = User(
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, data: LoginRequest) -> Tuple[User, str]:
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        raise AuthenticationException(
            message="Authentication failed",
            errors={"authentication": "Email or password is invalid"},
        )

    if not user.is_active:
        raise AuthenticationException(
            message="Authentication failed",
            errors={"authentication": "User account is inactive"},
        )

    token = create_access_token(subject=user.id)
    return user, token
