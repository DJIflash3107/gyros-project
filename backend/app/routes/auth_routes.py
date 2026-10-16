from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.models.user import User
from app.models.schemas.auth import RegisterRequest, LoginRequest
from app.middlewares.auth import get_current_user
from app.handlers import auth_handler

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/register", status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    return auth_handler.register_handler(data, db)


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    return auth_handler.login_handler(data, db)


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return auth_handler.me_handler(current_user)
