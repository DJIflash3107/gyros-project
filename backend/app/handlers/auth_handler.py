from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.schemas.auth import RegisterRequest, LoginRequest, AuthUserResponse
from app.services import auth_service
from app.helpers.response import success_response


def register_handler(data: RegisterRequest, db: Session) -> JSONResponse:
    user = auth_service.register(db, data)
    user_data = AuthUserResponse.model_validate(user).model_dump()
    return success_response(
        message="User registered successfully",
        data={"user": user_data},
        status_code=201,
    )


def login_handler(data: LoginRequest, db: Session) -> JSONResponse:
    user, token = auth_service.authenticate(db, data)
    user_data = AuthUserResponse.model_validate(user).model_dump()
    return success_response(
        message="Login successful",
        data={
            "token": {
                "access_token": token,
                "token_type": "bearer",
            },
            "user": user_data,
        },
    )


def me_handler(current_user: User) -> JSONResponse:
    user_data = AuthUserResponse.model_validate(current_user).model_dump()
    return success_response(
        message="User retrieved successfully",
        data={"user": user_data},
    )
