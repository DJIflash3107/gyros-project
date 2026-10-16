# AGENTS.md — Gyros Project Backend

This document is the authoritative guide for AI agents working on the Gyros Project backend.
Read it fully before modifying any code.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Technology Stack](#2-technology-stack)
3. [Folder Structure](#3-folder-structure)
4. [Request Lifecycle](#4-request-lifecycle)
5. [Configuration & Environment](#5-configuration--environment)
6. [Database Layer](#6-database-layer)
7. [Models (ORM)](#7-models-orm)
8. [Schemas (Pydantic)](#8-schemas-pydantic)
9. [Authentication & Authorization](#9-authentication--authorization)
10. [Services](#10-services)
11. [Handlers](#11-handlers)
12. [Routes](#12-routes)
13. [Exception Handling](#13-exception-handling)
14. [Response Envelopes](#14-response-envelopes)
15. [Logging & Error Codes](#15-logging--error-codes)
16. [Migrations (Alembic)](#16-migrations-alembic)
17. [Testing](#17-testing)
18. [Coding Conventions](#18-coding-conventions)
19. [Adding a New Entity (Checklist)](#19-adding-a-new-entity-checklist)

---

## 1. Project Overview

The Gyros Project backend is a REST API that manages multi-tenant business data (businesses,
branches, products, sales reporting, expenses). It uses a layered architecture:
**Routes → Handlers → Services → SQLAlchemy Session → MySQL**.

All endpoints live under the `/api/v1/` prefix.

---

## 2. Technology Stack

| Concern | Library / Tool |
|---|---|
| Web framework | FastAPI 0.115+ |
| Request validation | Pydantic v2 (`pydantic-settings` for config) |
| ORM | SQLAlchemy 2.x (declarative, sync) |
| Database (production) | MySQL via `pymysql` |
| Database (tests) | SQLite in-memory (`StaticPool`) |
| Auth tokens | PyJWT (`HS256`) |
| Password hashing | `bcrypt` |
| Migrations | Alembic |
| Testing | `pytest` + `pytest-asyncio`, `httpx` via `TestClient` |
| Python version | 3.11+ |

> **Do not** introduce new dependencies without updating `requirements.txt`.

---

## 3. Folder Structure

```
backend/
├── app/
│   ├── configs/
│   │   ├── database.py       # Engine, Base, SessionLocal, get_db()
│   │   ├── security.py       # hash_password, verify_password, create/decode_access_token
│   │   └── settings.py       # Pydantic Settings class (reads from .env)
│   ├── handlers/
│   │   └── <entity>_handler.py   # HTTP-layer functions (request → response)
│   ├── helpers/
│   │   ├── error_codes.py    # ErrorCodeRegistry + generate_error_code()
│   │   ├── exceptions.py     # AppException hierarchy
│   │   ├── logging.py        # setup_logging(), logger, request_id_var, error_code_var
│   │   ├── pagination.py     # paginate() helper
│   │   └── response.py       # success_response, error_response, paginated_response
│   ├── middlewares/
│   │   └── request_context.py    # RequestContextMiddleware (injects request_id)
│   ├── models/
│   │   ├── __init__.py       # Imports all ORM models so Alembic can discover them
│   │   ├── types.py          # BigIntId, IntUnsigned — dialect-aware column types
│   │   ├── <entity>.py       # One file per SQLAlchemy model
│   │   └── schemas/
│   │       └── <entity>.py   # Pydantic schemas for that entity
│   ├── routes/
│   │   ├── __init__.py       # Re-exports all routers
│   │   └── <entity>_routes.py    # APIRouter + path declarations
│   ├── services/
│   │   └── <entity>_service.py   # Business logic and DB interaction
│   └── main.py               # FastAPI app, middleware, exception handlers, router mounts
├── alembic/
│   ├── env.py                # Alembic environment (imports Base from configs.database)
│   └── versions/             # Migration scripts
├── tests/
│   ├── conftest.py           # In-memory SQLite fixtures (app, client, db)
│   └── test_*.py             # Feature-grouped test files
├── .env                      # Local secrets (git-ignored)
├── .env.example              # Template for .env
├── alembic.ini
└── requirements.txt
```

---

## 4. Request Lifecycle

```
Client
  │
  ▼
RequestContextMiddleware          # Generates & stores request_id (UUID)
  │
  ▼
FastAPI Router                    # Path/method matching, dependency injection
  │
  ├── get_current_user()          # JWT decode → User ORM object   (auth guard)
  ├── require_business_membership() # Membership role check        (authz guard)
  └── get_db()                    # Yields SQLAlchemy Session
  │
  ▼
Handler function                  # Unpacks request schema, calls service, builds response
  │
  ▼
Service function                  # Business logic + DB queries (raises AppException on error)
  │
  ▼
SQLAlchemy Session → MySQL
```

Exceptions bubble up and are caught by the centralized handlers in `main.py`.

---

## 5. Configuration & Environment

All settings are in `app/configs/settings.py` via `pydantic_settings.BaseSettings`.
Values are read from `.env` (case-sensitive). See `.env.example` for required keys.

```
DATABASE_URL=mysql+pymysql://user:pass@host:3306/gyros_db?charset=utf8mb4
JWT_SECRET_KEY=<min 32 chars>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
APP_NAME=GyrosProject
APP_ENV=development
APP_DEBUG=true
LOG_LEVEL=INFO
```

Import via:

```python
from app.configs.settings import settings
```

> Never hardcode secrets. Always read from `settings`.

---

## 6. Database Layer

### Engine & Session

Defined in `app/configs/database.py`:

- `Base` — `DeclarativeBase` subclass; all ORM models inherit from it.
- `engine` — Created from `settings.DATABASE_URL` with MySQL-specific pool settings.
- `SessionLocal` — `sessionmaker` bound to `engine`.
- `get_db()` — FastAPI dependency that yields a `Session` and auto-rolls back on error.

```python
from app.configs.database import get_db, Base
```

### Session Usage in Services

Always accept `db: Session` as a parameter. Never create sessions manually inside services.

```python
from sqlalchemy.orm import Session

def get_product(db: Session, business_id: int, product_id: int):
    product = db.query(Product).filter_by(business_id=business_id, id=product_id).first()
    if not product:
        raise NotFoundException(f"Product {product_id} not found")
    return product
```

### Dialect-Aware Column Types

`app/models/types.py` provides:

- `BigIntId` — `BIGINT UNSIGNED` on MySQL, `INTEGER` on SQLite.
- `IntUnsigned` — `INT UNSIGNED` on MySQL, `INTEGER` on SQLite.

Use these for all `id` and unsigned integer columns so tests work with SQLite.

```python
from app.models.types import BigIntId, IntUnsigned
```

---

## 7. Models (ORM)

### Conventions

- One file per entity under `app/models/`.
- All models inherit `Base` from `app.configs.database`.
- Table names are plural snake_case (e.g., `businesses`, `product_aliases`).
- All primary keys use `BigIntId` with `autoincrement=True`.
- Foreign keys reference `<table>.<column>` (string form), with `ondelete` cascade where appropriate.
- Timestamps: `created_at` and `updated_at` use `DateTime` with `server_default` and `onupdate`.
- **Register every new model** in `app/models/__init__.py` so Alembic detects it.

### Relationship overlaps

When two relationships share a join path (e.g., a model with multiple FK paths to the same table),
add `overlaps="<relationship_name>"` to suppress SQLAlchemy warnings.

---

## 8. Schemas (Pydantic)

Schemas live in `app/models/schemas/<entity>.py`.

### Required config

Every schema that reads from ORM objects must set:

```python
from pydantic import ConfigDict

class MySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
```

### Naming pattern

| Schema class | Purpose |
|---|---|
| `<Entity>Create` | POST request body |
| `<Entity>Update` | PUT/PATCH request body (all fields optional) |
| `<Entity>Response` | Single resource response |
| `<Entity>ListResponse` | List/paginated response |

### Validation

Use `@field_validator` and `model_validator` for cross-field validation.
Raise `ValueError` (not `AppException`) inside validators — FastAPI + our handler converts it.

---

## 9. Authentication & Authorization

### Auth helpers (`app/configs/security.py`)

| Function | Description |
|---|---|
| `hash_password(password)` | Returns bcrypt hash string |
| `verify_password(plain, hashed)` | Constant-time comparison |
| `create_access_token(subject, claims, expires_delta)` | Returns signed JWT string |
| `decode_access_token(token)` | Returns payload dict or raises `AuthenticationException` |

### FastAPI dependencies

| Dependency | Description |
|---|---|
| `get_current_user` | Decodes `Authorization: Bearer <token>`, returns `User` ORM object |
| `require_business_membership` | Checks caller is a member of the `business_id` in the path |

### Usage in routes

```python
from app.helpers import get_current_user, require_business_membership
from app.models.user import User

@router.get("/businesses/{business_id}/products")
def list_products(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_business_membership()),
):
    ...
```

> Protected routes MUST declare both `get_current_user` and `require_business_membership` where
> applicable. Public routes (login, register) use neither.

---

## 10. Services

Services contain all business logic and direct database interaction.

### Rules

1. Accept `db: Session` as the first parameter after entity IDs.
2. Never return `JSONResponse` — return ORM objects or plain dicts.
3. Raise `AppException` subclasses (never raw HTTP exceptions).
4. Use explicit transactions for multi-step writes: `db.add()` → `db.flush()` → `db.commit()`.
5. Call `db.refresh(obj)` after commit to populate server-generated fields.

### Example skeleton

```python
from sqlalchemy.orm import Session
from app.helpers.exceptions import NotFoundException, ConflictException

def create_thing(db: Session, business_id: int, data: ThingCreate) -> Thing:
    existing = db.query(Thing).filter_by(business_id=business_id, name=data.name).first()
    if existing:
        raise ConflictException(f"Thing '{data.name}' already exists")
    obj = Thing(business_id=business_id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
```

---

## 11. Handlers

Handlers are thin HTTP-layer functions that bridge routes and services.

### Rules

1. One file per entity: `app/handlers/<entity>_handler.py`.
2. Accept typed, validated Pydantic schemas from FastAPI.
3. Call the corresponding service function.
4. Return `success_response(...)` or `paginated_response(...)`.
5. Do **not** contain business logic or DB queries.

### Example skeleton

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from app.configs.database import get_db
from app.helpers.response import success_response
from app.models.schemas.thing import ThingCreate, ThingResponse
from app.services import thing_service

def create_thing_handler(business_id: int, body: ThingCreate, db: Session = Depends(get_db)):
    thing = thing_service.create_thing(db, business_id, body)
    return success_response(
        "Thing created",
        {"thing": ThingResponse.model_validate(thing).model_dump()},
        status_code=201,
    )
```

---

## 12. Routes

Route files declare APIRouter instances, path strings, HTTP methods, and wire handlers.

### Conventions

- File: `app/routes/<entity>_routes.py`
- Prefix: `/api/v1/<resource>` (plural)
- Tag: entity name (for OpenAPI grouping)
- Register in `app/routes/__init__.py` and mount in `app/main.py`

```python
from fastapi import APIRouter, Depends
from app.helpers import get_current_user, require_business_membership

router = APIRouter(prefix="/api/v1/businesses/{business_id}/things", tags=["Things"])

router.add_api_route(
    "",
    endpoint=create_thing_handler,
    methods=["POST"],
    dependencies=[Depends(get_current_user), Depends(require_business_membership())],
)
```

> After adding a new router, you **must** import and mount it in both `app/routes/__init__.py`
> and `app/main.py` (`app.include_router(...)`).

---

## 13. Exception Handling

All custom exceptions inherit from `AppException` (`app/helpers/exceptions.py`).

| Class | HTTP Status | Default Error Code |
|---|---|---|
| `ValidationException` | 422 | `ERR-42200` |
| `AuthenticationException` | 401 | `ERR-40001` |
| `AuthorizationException` | 403 | `ERR-40003` |
| `NotFoundException` | 404 | `ERR-40004` |
| `ConflictException` | 409 | `ERR-40009` |
| `InternalException` | 500 | random `ERR-XXXXX` |

Handlers in `main.py` catch `AppException`, `RequestValidationError`, `StarletteHTTPException`,
and bare `Exception` (fallback). **Do not** add new `@app.exception_handler` unless adding a new
exception base class.

### Raising exceptions in services

```python
from app.helpers.exceptions import NotFoundException, ConflictException

raise NotFoundException("Product 42 not found")
raise ConflictException(message="Alias already exists", errors={"alias": "must be unique"})
```

---

## 14. Response Envelopes

All responses use the standardized envelope from `app/helpers/response.py`.

**Success:**
```json
{
  "message": { "success": "Human-readable success message" },
  "error": {},
  "data": { "thing": { ... } }
}
```

**Error:**
```json
{
  "message": { "error": "Human-readable error message" },
  "error": { "field": "description" },
  "data": {}
}
```

**Paginated:**
```json
{
  "message": { "success": "..." },
  "error": {},
  "data": {
    "things": [ ... ],
    "pagination": { "page": 1, "per_page": 20, "total": 100 }
  }
}
```

> Always use `success_response()`, `error_response()`, or `paginated_response()`. Never construct
> raw dicts or return plain `dict` from handlers.

---

## 15. Logging & Error Codes

### Logger

```python
from app.helpers.logging import logger

logger.info("Something happened")
logger.warning("Recoverable issue")
logger.error("Unrecoverable issue")
```

Each log line automatically includes the `request_id` (correlation ID) set by
`RequestContextMiddleware`.

### Error codes

- `ErrorCodeRegistry` contains named static codes for known error conditions.
- `generate_error_code()` produces random `ERR-XXXXX` codes for unexpected errors.
- Set `error_code_var` when you want the code to appear in the log line:

```python
from app.helpers.logging import error_code_var
error_code_var.set("ERR-40004")
```

This is handled automatically by the exception handlers in `main.py`.

---

## 16. Migrations (Alembic)

### Setup

`alembic.ini` and `alembic/env.py` are pre-configured. The env imports `Base` from
`app.configs.database` and all models via `app.models` (which must re-export every model).

### Common commands (run from `backend/`)

```bash
# Create a new migration (autogenerate from model diffs)
alembic revision --autogenerate -m "describe_change"

# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# Show current revision
alembic current
```

### Rules

- Never edit a migration that has already been applied to a shared environment.
- Keep migrations focused: one logical change per revision.
- When adding a model, also add it to `app/models/__init__.py` so autogenerate detects it.

---

## 17. Testing

### Setup

Tests use `pytest` with an in-memory SQLite database for full isolation (no MySQL required).

```bash
# Run all tests from backend/
pytest

# Run a specific file
pytest tests/test_auth.py

# Verbose output
pytest -v
```

### Fixtures (`tests/conftest.py`)

| Fixture | Scope | Description |
|---|---|---|
| `engine` | function | Creates a fresh SQLite in-memory engine |
| `tables` | function | Runs `Base.metadata.create_all` / `drop_all` per test |
| `db` | function | Yields a Session against the test engine |
| `client` | function | `TestClient` with `get_db` overridden to use test session |

### Rules

1. Each test must be fully independent — no shared state across tests.
2. Use the `client` fixture for HTTP-level tests.
3. Use the `db` fixture for direct service-level tests.
4. Tests for a new entity go in a new `test_<entity>.py` file.
5. Test both happy-path and error cases (404, 409, 403, etc.).

### Auth in tests

Register + login within the test (or use `client.post("/api/v1/auth/login", ...)`) to get a token,
then pass `headers={"Authorization": f"Bearer {token}"}`.

---

## 18. Coding Conventions

### General

- Python 3.11+ syntax and type hints throughout.
- `snake_case` for variables, functions, files, columns.
- `PascalCase` for class names.
- One class/model per file (ORM models). Schemas may group related schemas in one file.
- Keep imports ordered: stdlib → third-party → local (`app.*`).

### SQLAlchemy

- Use `db.query(Model).filter_by(...)` for simple lookups.
- Use `select()` + `db.execute()` for complex queries.
- Prefer explicit `db.commit()` + `db.refresh(obj)` over implicit flushes.
- Never use `db.execute(text(...))` with raw SQL unless absolutely necessary.

### Pydantic

- All response schemas must have `model_config = ConfigDict(from_attributes=True)`.
- Use `model_validate(orm_obj)` to serialize ORM objects to schemas.
- Use `model_dump()` to convert to dict for response payloads.
- Mark optional fields with `Optional[T] = None`.

### FastAPI

- Use `Depends()` for all dependency injection (session, auth).
- Declare response models on the router when possible for auto-documentation.
- Avoid logic inside route functions — delegate to handlers.

### Error handling

- Never `raise HTTPException` directly. Use `AppException` subclasses.
- Always pass both `message` (human-readable) and `errors` (field→detail dict) to exceptions.

---

## 19. Adding a New Entity (Checklist)

Follow this order to add a new resource. Replace `<entity>` with the new entity name.

- [ ] **Model**: Create `app/models/<entity>.py` with ORM class inheriting `Base`.
- [ ] **Register model**: Add import to `app/models/__init__.py`.
- [ ] **Schema**: Create `app/models/schemas/<entity>.py` with `Create`, `Update`, `Response`, `ListResponse` classes.
- [ ] **Service**: Create `app/services/<entity>_service.py` with CRUD functions.
- [ ] **Handler**: Create `app/handlers/<entity>_handler.py` calling service functions.
- [ ] **Routes**: Create `app/routes/<entity>_routes.py` with `APIRouter` and path declarations.
- [ ] **Register route**: Import router in `app/routes/__init__.py` and add to `__all__`.
- [ ] **Mount route**: Import and call `app.include_router(...)` in `app/main.py`.
- [ ] **Migration**: Run `alembic revision --autogenerate -m "add_<entity>_table"` and review the generated file.
- [ ] **Tests**: Create `tests/test_<entity>.py` covering creation, retrieval, update, deletion, and error cases.
