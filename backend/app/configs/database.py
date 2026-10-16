from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from app.configs.settings import settings


class Base(DeclarativeBase):
    pass


def get_engine_args(url: str) -> dict:
    engine_kwargs = {}
    if url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs.update({
            "pool_pre_ping": True,
            "pool_recycle": 1800,
            "pool_size": 10,
            "max_overflow": 20,
        })
    return engine_kwargs


engine = create_engine(settings.DATABASE_URL, **get_engine_args(settings.DATABASE_URL))

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
