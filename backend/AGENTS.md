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
20. [AI Integration (AMD Token Factory)](#20-ai-integration-amd-token-factory)
21. [Business Operations Agent (LangGraph)](#21-business-operations-agent-langgraph)
22. [Sales Report Processing & Staging Workflow](#22-sales-report-processing--staging-workflow)
23. [Dynamic Profiling & LLM Semantic Mapping](#23-dynamic-profiling--llm-semantic-mapping)
24. [Multi-Sheet Workbook Processing](#24-multi-sheet-workbook-processing)
25. [Demand Forecasting Service](#25-demand-forecasting-service)

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
| Agent & LLM orchestration | LangGraph 0.4+, LangChain Core 0.3+, LangChain OpenAI 0.3+ |
| LLM Gateway / Provider | AMD Token Factory (OpenAI-compatible, vision & chat) |
| Spreadsheet parsing | `openpyxl` 3.1+ (Excel .xlsx), `csv` stdlib (CSV) |
| Testing | `pytest` + `pytest-asyncio`, `httpx` via `TestClient` |
| Python version | 3.11+ |

> **Do not** introduce new dependencies without updating `requirements.txt`.

---

## 3. Folder Structure

```
backend/
├── app/
│   ├── agent/                # Business Operations Agent (LangGraph)
│   │   ├── graph.py          # StateGraph workflow, nodes, conditional edges
│   │   ├── prompts.py        # System prompt guardrails & response sanitizer
│   │   ├── state.py          # AgentState TypedDict definition
│   │   └── tools.py          # 8 read-only operational tools & LangChain bindings
│   ├── configs/
│   │   ├── amd_client.py     # AMD Token Factory client (retries, backoff, streaming)
│   │   ├── database.py       # Engine, Base, SessionLocal, get_db()
│   │   ├── security.py       # hash_password, verify_password, create/decode_access_token
│   │   └── settings.py       # Pydantic Settings (DB, JWT, AMD, Agent, Vision, Semantic Mapping)
│   ├── handlers/
│   │   ├── agent_handler.py                  # Agent streaming chat handler (SSE StreamingResponse)
│   │   ├── ai_handler.py                     # AI endpoints handler (models, health, completions)
│   │   ├── sales_report_submission_handler.py # Process, batch form, confirm & CRUD handlers
│   │   ├── sales_report_staging_row_handler.py# Staging row review & status updates (including bulk)
│   │   ├── sales_report_observation_handler.py# Confirmed sales observation queries
│   │   ├── forecasting_handler.py            # Forecasting predict, evaluate, and sufficiency handlers
│   │   ├── import_issue_handler.py           # Import validation issue queries
│   │   ├── product_alias_handler.py          # Product alias management
│   │   └── <entity>_handler.py               # HTTP-layer functions (request → response)
│   ├── helpers/
│   │   ├── error_codes.py    # ErrorCodeRegistry (standard, AI, agent, report processing, forecasting)
│   │   ├── exceptions.py     # AppException hierarchy (includes AIServiceException, etc.)
│   │   ├── logging.py        # setup_logging(), logger, request_id_var, error_code_var
│   │   ├── pagination.py     # paginate() helper
│   │   └── response.py       # success_response, error_response, paginated_response
│   ├── middlewares/
│   │   ├── auth.py               # get_current_user & require_business_membership
│   │   └── request_context.py    # RequestContextMiddleware (injects request_id)
│   ├── models/
│   │   ├── __init__.py       # Imports all ORM models so Alembic can discover them
│   │   ├── types.py          # BigIntId, IntUnsigned — dialect-aware column types
│   │   ├── sales_report_submission.py   # Ingestion submissions (status, sha256, counters)
│   │   ├── sales_report_staging_row.py  # Staging rows (never auto-finalized, review status, source sheet)
│   │   ├── sales_report_observation.py  # Confirmed observations (unique business/branch/product/period)
│   │   ├── forecast_run.py              # Forecast runs metadata (model type, params, error metrics)
│   │   ├── forecast_result.py           # Forecast period points (point, lower, upper bounds)
│   │   ├── import_issue.py              # Staging validation & extraction issues
│   │   ├── product_alias.py             # Raw name to product alias mapping
│   │   └── <entity>.py       # One file per SQLAlchemy model
│   ├── models/schemas/
│   │   ├── agent.py                  # Pydantic schemas for SSE events and chat request
│   │   ├── ai.py                     # Pydantic schemas for AI models, health, and chat
│   │   ├── sales_report_processing.py # ManualFormBatchCreate, ProcessingResultResponse, SSE schemas
│   │   ├── sales_report_submission.py # Submission Create/Update/Response
│   │   ├── sales_report_staging_row.py# Staging row Create/Update/BulkUpdate/Response
│   │   ├── sales_report_observation.py# Confirmed observation schemas
│   │   ├── forecasting.py            # ForecastRequest, ForecastEvaluateRequest, ForecastRunResponse
│   │   ├── import_issue.py           # Import issue schemas
│   │   ├── product_alias.py          # Product alias schemas
│   │   └── <entity>.py               # Pydantic schemas for that entity
│   ├── routes/
│   │   ├── __init__.py                   # Re-exports all routers
│   │   ├── agent_routes.py               # /api/v1/agent routes (POST chat)
│   │   ├── ai_routes.py                  # /api/v1/ai routes (models, health, chat)
│   │   ├── sales_report_submission_routes.py # /process, /batch_form, /{id}/confirm, CRUD
│   │   ├── sales_report_staging_row_routes.py# Staging rows CRUD and /bulk update
│   │   ├── sales_report_observation_routes.py
│   │   ├── forecasting_routes.py         # /api/v1/businesses/{id}/forecasting (predict, evaluate, sufficiency)
│   │   ├── import_issue_routes.py
│   │   ├── product_alias_routes.py
│   │   └── <entity>_routes.py            # APIRouter + path declarations
│   ├── services/
│   │   ├── agent_service.py                  # LangGraph astream_events orchestration & SSE streaming
│   │   ├── ai_service.py                     # AI discovery, capability inference, chat logic
│   │   ├── sales_report_processing_service.py # Orchestrator: spreadsheet/photo/form -> staging
│   │   ├── input_profiler.py                 # Structural profiler (headers, types, sample data, merged cells)
│   │   ├── semantic_mapper.py                # LLM-based column-to-canonical schema mapping & sheet role classifier
│   │   ├── spreadsheet_parser.py             # Excel/CSV parser with dynamic mapping + multi-sheet support
│   │   ├── photo_extractor.py                # AMD VLM extraction with SSE progress streaming
│   │   ├── validation_engine.py              # 10-step centralized validation & alias resolution
│   │   ├── sales_report_submission_service.py # Submissions CRUD & atomic observation confirmation
│   │   ├── sales_report_staging_row_service.py# Staging row persistence & bulk status updates
│   │   ├── sales_report_observation_service.py# Confirmed observations & overlap checks
│   │   ├── forecasting_engine.py             # Predictive time-series models (SMA, EMA, Holt-Winters, Backtesting)
│   │   ├── forecasting_service.py            # Forecasting orchestration, validation & DB persistence
│   │   ├── import_issue_service.py           # Issue persistence
│   │   ├── product_alias_service.py          # Alias resolution
│   │   └── <entity>_service.py               # Business logic and DB interaction
│   └── main.py               # FastAPI app, lifespan, middleware, exception handlers, router mounts
├── alembic/
│   ├── env.py                # Alembic environment (imports Base from configs.database)
│   └── versions/             # Migration scripts
├── tests/
│   ├── conftest.py                       # In-memory SQLite fixtures (app, client, db, users)
│   ├── test_agent_*.py                   # Agent auth, graph, streaming, and tool suites
│   ├── test_ai_endpoints.py              # Tests for /api/v1/ai routes
│   ├── test_amd_client.py                # Tests for AMDTokenFactoryClient
│   ├── test_sales_report_processing.py   # Multi-channel ingestion, validation, and confirmation tests
│   ├── test_multi_sheet_processing.py    # Multi-sheet Excel workbook ingestion tests
│   ├── test_sales_report_staging_row_bulk.py # Staging row bulk update tests
│   ├── test_semantic_mapping.py          # Profiler, LLM semantic mapper, and fallback tests
│   ├── test_forecasting_engine.py        # Forecasting models (SMA, EMA, Holt-Winters) tests
│   ├── test_forecasting_endpoints.py     # Forecasting predict, evaluate, and sufficiency tests
│   ├── test_sales_submissions.py         # Submissions CRUD and review lifecycle
│   └── test_*.py                         # Feature-grouped test files
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

# AMD Token Factory Configuration
AMD_API_BASE_URL=https://developer.amd.com.cn/radeon/api/v1
AMD_API_KEY=rc-...               # Required for AI features
AMD_DEFAULT_MODEL=DeepSeek-V4-Flash
AMD_REQUEST_TIMEOUT=600          # 10 min, per AMD docs
AMD_STREAM_CHUNK_TIMEOUT=600     # 10 min max gap between stream chunks
AMD_MAX_RETRIES=3                # Retries on 429/502/503 with backoff + jitter

# Agent Configuration (LangGraph)
AGENT_MAX_TURNS=10               # Max tool round-trips per conversation turn
AGENT_REQUEST_TIMEOUT=120        # Max total execution time in seconds
AGENT_MAX_TOKENS=4096            # Max generation tokens per response
AGENT_TEMPERATURE=0.3            # Conservative temperature for business ops

# Vision Configuration (Photo Extraction)
VISION_MODEL_OVERRIDE=""         # Force specific vision model (empty = auto-discover)
VISION_MAX_IMAGE_SIZE_MB=5       # Max photo upload size
VISION_EXTRACTION_TEMPERATURE=0.1 # Low temperature for accurate OCR

# Semantic Mapping Configuration (Dynamic Column Profiling)
SEMANTIC_MAPPING_ENABLED=true    # Toggle LLM dynamic mapping
SEMANTIC_MAPPING_MODEL=""        # Model for column mapping (empty = AMD_DEFAULT_MODEL)
SEMANTIC_MAPPING_TEMPERATURE=0.0 # Deterministic schema mapping
SEMANTIC_MAPPING_CONFIDENCE_THRESHOLD=0.7 # Minimum confidence score threshold
```

Import via:

```python
from app.configs.settings import settings
```

> Never hardcode secrets. Always read from `settings`.
> When `AMD_API_KEY` is empty, the server starts normally but AI endpoints return standardized 503 (`ERR-AI-501`).

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
| `AIServiceException` | 502 | `ERR-AI-500` |
| `AIRateLimitException` | 429 | `ERR-AI-429` |
| `AIConfigException` | 503 | `ERR-AI-501` |
| `AgentTimeoutException` | 408 | `ERR-AGT-408` |
| `AgentCancelledException` | 499 | `ERR-AGT-499` |

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

- `ErrorCodeRegistry` contains named static codes for known error conditions:
  - Standard errors: `ERR-40001` (Auth failed), `ERR-40003` (Forbidden), `ERR-40004` (Not found), `ERR-40009` (Conflict), `ERR-42200` (Validation failed), `ERR-50000` (Internal), `ERR-60001` (DB error).
  - AI / AMD Token Factory:
    - `ERR-AI-400`: Invalid parameter / model rejected by AMD gateway
    - `ERR-AI-401`: Missing or invalid AMD API key
    - `ERR-AI-403`: AMD account review pending / forbidden
    - `ERR-AI-429`: AMD rate limit exceeded (after retries exhausted)
    - `ERR-AI-500`: AMD provider / gateway 5xx error
    - `ERR-AI-501`: AI service not configured (`AMD_API_KEY` missing)
    - `ERR-AI-503`: AMD connection failure or timeout
  - Business Operations Agent:
    - `ERR-AGT-400`: Bad agent request / invalid payload
    - `ERR-AGT-408`: Agent request timeout exceeded
    - `ERR-AGT-429`: Agent rate limit exceeded during tool execution
    - `ERR-AGT-499`: Client disconnected during processing
    - `ERR-AGT-500`: Internal agent / graph error
    - `ERR-AGT-503`: Agent service unavailable (unconfigured key or LLM down)
  - Sales Report Ingestion & Processing:
    - `ERR-RPT-001`: Malformed or corrupt file bytes
    - `ERR-RPT-002`: Empty file (no data rows found)
    - `ERR-RPT-003`: File exceeds size limit (>10 MB)
    - `ERR-RPT-004`: Unsupported MIME type for input method
    - `ERR-RPT-005`: Duplicate submission detected (SHA-256 match)
    - `ERR-RPT-006`: Row or cell parse failure
    - `ERR-RPT-010`: Vision model unavailable / unconfigured
    - `ERR-RPT-011`: Vision model extraction failed / invalid output
    - `ERR-RPT-012`: Image exceeds size limit (>5 MB)
    - `ERR-RPT-020`: Semantic column mapping failed
    - `ERR-RPT-021`: Low confidence column mapping (< threshold)
    - `ERR-RPT-099`: Generic report processing error
  - Validation Engine Issue Codes (recorded on `ImportIssue`):
    - `RPT-VAL-001`: Product resolution failure (error)
    - `RPT-VAL-002`: Branch does not exist or inactive (error)
    - `RPT-VAL-003`: Invalid period date range (error)
    - `RPT-VAL-004`: Date outside submission coverage window (warning)
    - `RPT-VAL-005`: Granularity inconsistent with period (warning)
    - `RPT-VAL-006`: Negative quantity or revenue (error)
    - `RPT-VAL-007`: Intra-submission duplicate row (warning)
    - `RPT-VAL-008`: Cross-submission overlap with existing active observation (warning)
    - `RPT-VAL-009`: Stock balance inconsistency (info)
    - `RPT-VAL-010`: Revenue plausibility warning (info)
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
| `clean_database` | autouse | Runs `Base.metadata.create_all` / `drop_all` around each test |
| `db_session` | function | Yields a Session against the in-memory SQLite engine |
| `client` | function | `TestClient` with `get_db` overridden to use `db_session` |
| `auth_user` | function | Registers and logs in primary user, returns user dict and `Authorization` header |
| `second_user` | function | Registers and logs in second user for multi-tenant isolation tests |

### Test Commands

```bash
# Run all tests (141 tests)
pytest

# Run sales report processing, multi-sheet, bulk update, and semantic mapping tests
pytest tests/test_sales_report_processing.py tests/test_multi_sheet_processing.py tests/test_sales_report_staging_row_bulk.py tests/test_semantic_mapping.py tests/test_sales_submissions.py -v

# Run forecasting tests (engine and endpoints)
pytest tests/test_forecasting_engine.py tests/test_forecasting_endpoints.py -v

# Run agent tests
pytest tests/test_agent_auth.py tests/test_agent_tools.py tests/test_agent_graph.py tests/test_agent_streaming.py -v

# Run AI provider tests
pytest tests/test_amd_client.py tests/test_ai_endpoints.py -v
```

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

---

## 20. AI Integration (AMD Token Factory)

The backend integrates AMD Radeon Cloud Token Factory for free, OpenAI-compatible LLM endpoints.

### Architecture

```
Client
  │
  ▼
ai_routes.py (/api/v1/ai)
  │
  ▼
ai_handler.py (builds success_response / StreamingResponse)
  │
  ▼
ai_service.py (capability inference, health check, chat orchestration)
  │
  ▼
amd_client.py (httpx.AsyncClient + backoff retry + error parser)
  │
  ▼
AMD Gateway (https://developer.amd.com.cn/radeon/api/v1)
```

### Components

| File | Layer | Purpose |
|---|---|---|
| `app/configs/amd_client.py` | Config / Client | Low-level HTTP client (`AMDTokenFactoryClient`), retry with backoff + jitter for 429/502/503, dual error parser, SSE stream generator. |
| `app/services/ai_service.py` | Service | Business logic: `list_models()`, `check_health()`, `chat_completion()`, `chat_completion_stream()`. Enforces **no placeholder output on failure**. |
| `app/handlers/ai_handler.py` | Handler | Formats responses using `success_response()` and `StreamingResponse` for SSE. |
| `app/routes/ai_routes.py` | Route | APIRouter prefixed at `/api/v1/ai`. |
| `app/models/schemas/ai.py` | Schema | Pydantic schemas: `AIModelInfo`, `AIHealthResponse`, `ChatMessage`, `ChatCompletionRequest`. |

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/ai/models` | Discover models at runtime with capability flags (`supports_vision`, `supports_reasoning`, `supports_tools`). |
| `GET` | `/api/v1/ai/health` | Operational health check (returns `unconfigured`, `healthy`, or `unavailable` with latency and usage). |
| `POST` | `/api/v1/ai/chat/completions` | Chat completions. If `stream: true`, streams SSE tokens ending with `data: [DONE]`. |

### Gateway & Model Rules

1. **Parameters accepted by AMD Gateway:** `model`, `messages`, `stream`, `temperature`, `top_p`, `max_tokens`, `presence_penalty`, `frequency_penalty`, `response_format`, `tools`, `tool_choice`, `parallel_tool_calls`, `reasoning_effort`.
2. **Silently dropped:** `stop`, `seed`, `logit_bias`, `logprobs`, `top_k`, `min_p`, `repetition_penalty`.
3. **Rejected with 400:** `thinking: {...}` and `reasoning.enabled` (use `reasoning_effort` instead).
4. **Timeouts:** 10 minutes (600s) default request timeout; 10 minutes max gap between streaming chunks.
5. **Rate limits:** Per-key 30 RPM, 8 concurrent requests. Shared across the entire team key.
6. **Graceful startup:** If `AMD_API_KEY` is not set, the server starts normally; AI discovery/chat endpoints return standardized 503 (`ERR-AI-501`), and `/api/v1/ai/health` returns `status: "unconfigured"`.
7. **No placeholder output:** If an AI request fails, always raise the mapped `AppException` subclass. Never mock or return fallback placeholder text to the caller.

### LangGraph Integration Readiness

The provider-specific transport and error handling are strictly isolated in `amd_client.py`. Downstream agents or LangGraph workflows can bind to `ai_service` or wrap `get_amd_client()` cleanly without protocol pollution.

### Testing Commands

```bash
# Run AI unit and integration tests
.venv/Scripts/python -m pytest tests/test_amd_client.py tests/test_ai_endpoints.py -v

# Run full test suite
.venv/Scripts/python -m pytest -v
```

---

## 21. Business Operations Agent (LangGraph)

Phase 2 builds an agentic Business Operations assistant using **LangGraph** and the **AMD Token Factory** provider from Phase 1. The agent delivers real-time streaming conversational assistance over Server-Sent Events (SSE) while enforcing strict read-only constraints, tenant isolation, and security guardrails.

### Architecture

```
Client (POST /api/v1/agent/businesses/{business_id}/chat)
  │
  ▼
agent_routes.py ─────────────────────────── JWT auth + business membership
  │
  ▼
agent_handler.py ────────────────────────── StreamingResponse with text/event-stream
  │
  ▼
agent_service.py ────────────────────────── graph.astream_events() + SSE event mapper
  │
  ▼
agent_graph.py ──────────────────────────── LangGraph StateGraph
  ├── route_request_node ────────────────── Analyzes intent, tool calling
  ├── execute_tools_node ────────────────── Calls read-only tools asynchronously
  ├── generate_response_node ────────────── LLM final synthesis (token-by-token stream)
  └── handle_error_node ────────────────── Catches errors → safe agent_error event
  │
  ▼
agent_tools.py ──────────────────────────── Read-only operational tool functions
  ├── business_summary ──────────────────── Aggregates business metadata and branches
  ├── sales_analytics ───────────────────── Aggregates sales observations and revenue
  ├── expense_summary ───────────────────── Aggregates expenses by category
  ├── product_catalog ───────────────────── Queries product catalog and status
  ├── invoke_forecasting ────────────────── Stub (future forecasting service)
  ├── invoke_action_center ──────────────── Stub (future Business Action Center)
  ├── invoke_promotion_planner ──────────── Stub (future Promotion Planner)
  └── invoke_artifact_service ───────────── Stub (future artifact generator)
```

### Components

| File | Layer | Purpose |
|---|---|---|
| `app/models/schemas/agent.py` | Schema | Pydantic schemas: `AgentSSEEvent`, `AgentChatRequest`, event data models (`AgentStatusEvent`, `ToolStartEvent`, `ToolResultEvent`, `MessageDeltaEvent`, `ApprovalRequiredEvent`, `AgentErrorEvent`, `AgentCompleteEvent`). |
| `app/agent/state.py` | Agent | `AgentState` TypedDict for LangGraph state management. |
| `app/agent/prompts.py` | Agent | System prompt template and `sanitize_response()` to strip chain-of-thought `<think>` blocks. |
| `app/agent/tools.py` | Agent | Read-only tool execution functions and LangChain `BaseTool` wrappers. |
| `app/agent/graph.py` | Agent | `StateGraph` workflow, nodes (`route_request`, `execute_tools`, `generate_response`, `handle_error`), and conditional edges (`should_use_tools`, `check_continue`). |
| `app/services/agent_service.py` | Service | Graph execution via `astream_events(version="v2")`, event mapping to `AgentSSEEvent`, timeouts, and client disconnect handling. |
| `app/handlers/agent_handler.py` | Handler | `agent_chat_handler` returning `StreamingResponse` with `text/event-stream`. |
| `app/routes/agent_routes.py` | Route | `APIRouter` at `/api/v1/agent/businesses/{business_id}/chat`. |

### Endpoints

| Method | Path | Auth / Authz | Description |
|---|---|---|---|
| `POST` | `/api/v1/agent/businesses/{business_id}/chat` | JWT + Business Membership | Streams structured SSE events for agent conversation. |

### SSE Stream Event Protocol

Events are streamed as `data: {json}\n\n` followed by a terminal `data: [DONE]\n\n`:

1. `agent_status` — Graph lifecycle status (`routing`, `executing_tools`, `generating_response`).
2. `tool_start` — Emitted when a tool begins execution with sanitized input.
3. `tool_result` — Emitted when a tool completes with summary and aggregated data.
4. `message_delta` — Incremental tokens from the LLM final synthesis.
5. `approval_required` — Reserved for future action authorization workflows.
6. `agent_error` — Emitted on failure with standardized error code (e.g., `ERR-AGT-408`, `ERR-AGT-500`).
7. `agent_complete` — Terminal event with `tools_used`, `duration_ms`, and `total_tokens`.

### Security Guardrails

1. **Read-Only Enforcement:** Agent tools NEVER execute `INSERT`, `UPDATE`, `DELETE`, or raw SQL (`db.execute(text(...))`). All data queries use existing ORM service functions.
2. **Strict Multi-Tenant Isolation:** The `business_id` is extracted from the URL and enforced via `require_business_membership()`. All tool queries strictly filter by the authorized `business_id`.
3. **Chain-of-Thought Sanitization:** `<think>` and `reasoning` blocks are stripped by `sanitize_response()` and never streamed in `message_delta` events.
4. **No Internal Leakage:** Database table names, SQL queries, credentials, and Python stack traces are never exposed to the client or LLM.
5. **Timeouts and Cancellation:** Configurable timeout via `AGENT_REQUEST_TIMEOUT` (emits `ERR-AGT-408`). Client disconnects (`Request.is_disconnected()`) abort the generator gracefully.

### Configuration (`.env`)

```ini
AGENT_MAX_TURNS=10
AGENT_REQUEST_TIMEOUT=120
AGENT_MAX_TOKENS=4096
AGENT_TEMPERATURE=0.3
```

### Testing Commands

```bash
# Run agent test suites
.venv/Scripts/python -m pytest tests/test_agent_auth.py tests/test_agent_tools.py tests/test_agent_graph.py tests/test_agent_streaming.py -v

# Run full project test suite
.venv/Scripts/python -m pytest -v
```

---

## 22. Sales Report Processing & Staging Workflow

The backend supports multi-channel ingestion of sales reports across spreadsheets (`.xlsx`, `.xls`, `.csv`), batch manual forms, and sales-record photos. All extracted data flows through a **staging-only** pipeline that enforces data integrity, tenant isolation, and explicit human confirmation before final observations are created.

### Architecture Overview

```
                      Client Upload / Submission
                                 │
     ┌───────────────────────────┼───────────────────────────┐
     ▼                           ▼                           ▼
Spreadsheet (.xlsx/.csv)   Batch Manual Form           Photo / Receipt Image
(POST .../process)         (POST .../batch_form)       (POST .../process [SSE])
     │                           │                           │
     ▼                           ▼                           ▼
input_profiler.py                │                     photo_extractor.py
     │                           │                     (AMD Vision VLM)
     ▼                           │                           │
semantic_mapper.py               │                           │
(AMD Token Factory)              │                           │
     │                           │                           │
     ▼                           │                           │
spreadsheet_parser.py            │                           │
     │                           │                           │
     └───────────────────────────┼───────────────────────────┘
                                 ▼
                       validation_engine.py
              (10 business integrity checks + alias resolution)
                                 │
                                 ▼
                      SalesReportSubmission
                     (status: "reviewed")
                                 │
                       1:N Staging Rows
                     SalesReportStagingRow
        (review_status: "ready" | "pending_review" | "needs_correction")
                                 │
                                 │ (User reviews staging rows)
                                 │ (Explicit POST .../confirm)
                                 ▼
                     sales_report_submission_service.py
                           (confirm_submission)
                                 │
                                 ▼
                     SalesReportObservation
                 (Immutable confirmed observation)
```

### Ingestion Channels

| Input Method | Endpoint | Payload Format | Limits & Handling |
|---|---|---|---|
| `spreadsheet` | `POST /api/v1/businesses/{business_id}/sales_report_submissions/process` | `multipart/form-data` (`.xlsx`, `.xls`, `.csv`) | Max 10 MB. SHA-256 duplicate detection. Automatically profiles layout and performs LLM semantic mapping. |
| `form` (batch) | `POST /api/v1/businesses/{business_id}/sales_report_submissions/batch_form` | `application/json` (`ManualFormBatchCreate`) | 1 to 500 rows per batch. Direct DB staging with product alias resolution and full validation. |
| `photo` | `POST /api/v1/businesses/{business_id}/sales_report_submissions/process` | `multipart/form-data` (`image/jpeg`, `image/png`, `image/webp`) | Max 5 MB. Requires vision-capable AMD model. Always streams real-time SSE progress events. |

### Core Safety Invariants

1. **Staging-Only Invariant:** Extraction outputs are **ALWAYS** stored as `SalesReportStagingRow`. Raw inputs are never converted directly into `SalesReportObservation`.
2. **Never Auto-Confirm OCR/Vision Data:** Vision-extracted rows are forced to `review_status="pending_review"` regardless of score to mandate human verification.
3. **Strict Human Confirmation:** Staging rows become confirmed observations only via an explicit authenticated call to `POST .../sales_report_submissions/{submission_id}/confirm`.
4. **Needs Correction Exclusion:** Rows with `review_status="needs_correction"` are skipped and excluded from observation creation during confirmation.
5. **Atomic Finalization:** Confirmation executes in a single database transaction. If any observation fails constraint validation, the entire transaction rolls back.
6. **SHA-256 De-duplication:** Submissions compute SHA-256 digests of uploaded files to block duplicate ingestion of active submissions.
7. **Cross-Submission Overlap Protection:** The validation engine compares proposed staging periods against confirmed `SalesReportObservation` records to prevent double-counting.

### Centralized Validation Engine (`validation_engine.py`)

Validation executes 10 sequential checks on all rows across all channels:

1. `RPT-VAL-001` (Error): **Product resolution** — Resolves `raw_product_name` against exact active products, then case-insensitive `ProductAlias` mappings.
2. `RPT-VAL-002` (Error): **Branch existence** — Validates that `branch_id` belongs to the target business and is active.
3. `RPT-VAL-003` (Error): **Date validity** — Ensures `period_start <= period_end` and dates are valid.
4. `RPT-VAL-004` (Warning): **Coverage window** — Verifies row dates lie within submission `coverage_start` and `coverage_end`.
5. `RPT-VAL-005` (Warning): **Granularity match** — Confirms `granularity` matches `report_period_type` or period span.
6. `RPT-VAL-006` (Error): **Quantity bounds** — Validates non-negative values for all quantities and recorded revenue.
7. `RPT-VAL-007` (Warning): **Intra-submission duplicates** — Detects duplicate `(product_id, branch_id, period_start, period_end)` tuples within the same submission.
8. `RPT-VAL-008` (Warning): **Cross-submission overlap** — Checks if an active `SalesReportObservation` already covers the same entity and period.
9. `RPT-VAL-009` (Info): **Stock balance consistency** — Compares `opening_stock + received` against `available_stock`.
10. `RPT-VAL-010` (Info): **Revenue plausibility** — Flags rows with recorded revenue when `sold_qty == 0`.

### Review Status Assignment

- `ready` — All validations pass with zero issues. Eligible for one-click confirmation.
- `pending_review` — Contains warnings, info notices, or originated from vision/OCR. Eligible for confirmation after user inspection.
- `needs_correction` — Contains one or more error-level issues (e.g., unresolved product, invalid branch). Blocked from confirmation until corrected.

### SSE Progress Streaming (Photo Ingestion)

When processing photos or when `stream=true`, the endpoint returns a `text/event-stream` with structured progress events:

1. `report_status` (`step: "uploading" | "extracting" | "validating" | "staging" | "complete" | "failed"`)
2. `extraction_progress` (`message: "..."`)
3. `validation_result` (`total`, `ready`, `pending_review`, `needs_correction`, `errors`)
4. `report_complete` (`submission_id`, `total_rows`, `accepted_rows`, `rejected_rows`)
5. `report_error` (`error_code`, `message`)

Terminal event: `data: [DONE]\n\n`.

### Endpoints Reference

| Method | Path | Auth / Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/businesses/{b_id}/sales_report_submissions/process` | Member | Process spreadsheet or photo input. |
| `POST` | `/api/v1/businesses/{b_id}/sales_report_submissions/batch_form` | Member | Batch manual form submission (up to 500 rows). |
| `POST` | `/api/v1/businesses/{b_id}/sales_report_submissions/{s_id}/confirm` | Owner / Admin / Manager | Confirms staging rows into observations. |
| `GET` | `/api/v1/businesses/{b_id}/sales_report_submissions` | Member | List submissions with pagination and status filter. |
| `GET` | `/api/v1/businesses/{b_id}/sales_report_submissions/{s_id}` | Member | Get submission details and processing summary. |
| `PATCH` | `/api/v1/businesses/{b_id}/sales_report_submissions/{s_id}` | Owner / Admin / Manager | Update submission metadata or review note. |
| `DELETE` | `/api/v1/businesses/{b_id}/sales_report_submissions/{s_id}` | Owner / Admin | Delete submission and cascade delete staging rows. |
| `GET` | `/api/v1/sales_report_submissions/{s_id}/staging_rows` | Member | List staging rows with review status filter. |
| `PATCH` | `/api/v1/sales_report_submissions/{s_id}/staging_rows/bulk` | Member | Bulk update staging rows (all or by ID list, e.g. mark `ready`). |
| `POST` | `/api/v1/sales_report_submissions/{s_id}/staging_rows/bulk` | Member | Alternative method for bulk update. |
| `GET` | `/api/v1/sales_report_submissions/{s_id}/staging_rows/{row_id}` | Member | Get single staging row details. |
| `PATCH` | `/api/v1/sales_report_submissions/{s_id}/staging_rows/{row_id}` | Member | Correct staging row values (e.g. resolve product). |
| `DELETE` | `/api/v1/sales_report_submissions/{s_id}/staging_rows/{row_id}` | Member | Delete individual staging row. |
| `GET` | `/api/v1/businesses/{b_id}/sales_report_observations` | Member | Query confirmed observations (analytics / BI). |
| `GET` | `/api/v1/sales_report_submissions/{s_id}/import_issues` | Member | Query extraction and validation issues. |

### Bulk Staging Row Review & Update

To allow fast operator reviews without editing rows one by one, the API provides a dedicated bulk update endpoint:

`PATCH /api/v1/sales_report_submissions/{submission_id}/staging_rows/bulk` (also accepts `POST`)

**Schema (`SalesReportStagingRowBulkUpdate`):**
- `apply_to_all: bool` — If `true`, applies updates to all staging rows under the submission.
- `row_ids: Optional[list[int]]` — List of specific staging row IDs to update.
- `filter_review_status: Optional[ReviewStatus]` — Optional filter (e.g. only update rows currently `needs_correction` or `pending_review`).
- Target fields to update: `review_status`, `review_notes`, `branch_id`, `product_id`.

**Validation Rules:**
- At least one target selection must be provided (`apply_to_all=True` or a non-empty `row_ids` list); otherwise returns `422 Unprocessable Entity`.
- At least one update field (`review_status`, `review_notes`, `branch_id`, or `product_id`) must be provided.

**Example Request:**
```json
{
  "apply_to_all": true,
  "review_status": "ready",
  "review_notes": "Bulk approved by manager"
}
```

### Master Data Resolution Invariant

During ingestion, the pipeline **NEVER automatically creates new Product or Branch records** in the master tables:
1. If a product cannot be resolved by ID, exact name, case-insensitive name, or alias, `RPT-VAL-001` (Severity: `error`) is emitted, and the row enters staging with `product_id=None` and `review_status="needs_correction"`.
2. If a branch ID is missing, inactive, or belongs to another business, `RPT-VAL-002` (Severity: `error`) is emitted, and the row enters staging with `branch_id=None` and `review_status="needs_correction"`.
3. During confirmation (`/confirm`), rows lacking `product_id` or `branch_id` are strictly rejected and blocked from observation conversion until the operator creates the master entity or alias and updates the staging row.

---

## 23. Dynamic Profiling & LLM Semantic Mapping

To eliminate fragile column name assumptions and rigid spreadsheet templates, Gyros implements dynamic schema mapping powered by the AMD Token Factory LLM.

### Architecture

```
Spreadsheet Bytes (.xlsx / .csv)
         │
         ▼
input_profiler.py
   ├── profile_excel() / profile_csv()
   ├── Extracts raw headers, samples first 5 rows, infers column types
   ├── Detects merged cells and multi-level headers
   └── Formats compact structural prompt (~500 tokens)
         │
         ▼
semantic_mapper.py
   ├── map_columns_with_llm(profile, business_context)
   ├── Injects business product catalog and canonical schema
   ├── Calls AMD Token Factory (chat_completion with json_object)
   ├── Scores per-column confidence (0.0 to 1.0) and reasoning
   └── Deterministic fallback to static COLUMN_MAPPING on error
         │
         ▼
spreadsheet_parser.py
   └── normalize_header_from_mapping() maps raw columns to canonical fields
         │
         ▼
Staging Rows (extraction_confidence_json)
   └── Full audit trail: model used, per-column confidence, warnings
```

### Canonical Field Schema

The semantic mapper targets a fixed canonical dictionary (`CANONICAL_FIELDS`):
- Identification: `raw_product_name`, `product_id`, `branch_id`
- Period: `period_start`, `period_end`, `granularity`
- Stock: `prepared_qty`, `opening_stock_qty`, `received_qty`, `available_stock_qty`, `leftover_qty`
- Sales & Loss: `sold_qty`, `spoiled_qty`, `damaged_qty`, `staff_meals_qty`, `donated_qty`, `other_disposition_qty`
- Revenue: `recorded_revenue`
- Ignored: `_skip` (non-sales metadata, row numbers, arbitrary notes)

### Deterministic Fallback Strategy

1. **Graceful Fallback:** If `SEMANTIC_MAPPING_ENABLED=False`, `AMD_API_KEY` is not configured, or the LLM request times out/fails, the parser automatically falls back to the static `COLUMN_MAPPING` dictionary.
2. **Confidence Thresholding:** Columns mapped below `SEMANTIC_MAPPING_CONFIDENCE_THRESHOLD` (default: `0.7`) emit `ERR-RPT-021` warning issues on staging rows for human operator review.
3. **Auditability:** Every staging row persists the mapping metadata (`mapping_method`, `model`, `column_confidences`, `warnings`) inside `extraction_confidence_json`.

---

## 24. Multi-Sheet Workbook Processing

When users upload an Excel workbook (`.xlsx`), the import pipeline automatically processes all relevant worksheets instead of only the active sheet.

### Workflow & Architecture

1. **Independent Per-Sheet Profiling (`input_profiler.py`):**
   - `profile_excel_workbook(file_bytes)` inspects every sheet independently.
   - Extracts sheet name, headers, sample rows, merged cells, and inferred data types.
   - Sheets with no headers or zero data rows are automatically collected in `skipped_sheets`.

2. **Semantic Role Classification (`semantic_mapper.py`):**
   - `classify_sheet_roles(profiles, biz_context)` sends structural summaries of all sheets to the AMD Token Factory LLM in a single consolidated prompt.
   - Sheets are classified into:
     - `sales`: Transactions, daily branch status, order quantities, sold quantities, leftover stocks, or revenue.
     - `reference`: Product masters, price lists, branch directories (retained to enrich business matching context).
     - `instructional`: Template guides, notes, legends (safely skipped).
     - `expenses`: Costs, petty cash, purchase invoices (unsupported for sales observation, skipped).
     - `ambiguous`: Unrecognized layouts or non-standard structures (flagged for review with `ERR-RPT-023`).
   - If the LLM is unavailable or disabled, `build_fallback_sheet_classifications` provides deterministic keyword-based heuristics.

3. **Per-Sheet Column Mapping & Parsing (`spreadsheet_parser.py`):**
   - Each sheet classified as `sales` receives its own semantic mapping (or fallback) based on its distinct columns.
   - `parse_excel_workbook(file_bytes, sheet_mappings)` parses each sales sheet independently.
   - Handles repeated header rows (e.g. from page breaks) and intermediate blank rows cleanly.
   - Attaches `source_sheet_name` and relative `source_row_number` to each row for precise auditing.

4. **Cross-Sheet Duplicate Prevention (`sales_report_processing_service.py`):**
   - `_deduplicate_cross_sheet(raw_rows)` checks a composite key: `(raw_product, branch, period_start, period_end)`.
   - If a duplicate record appears in a subsequent sheet, it is omitted from staging and flagged with `ERR-RPT-022` warning issue (`RPT_CROSS_SHEET_DUPLICATE`) with the source sheet and row reference.

5. **Staging & Review Auditability:**
   - Every staging row stores `source_sheet_name` in the database and API responses.
   - `ProcessingSummary` returns `sheets_processed`, `sheets_skipped`, and `sheets_ambiguous`.
   - Ambiguous sheets produce actionable warning issues without failing the rest of the valid sales sheets.

---

## 25. Demand Forecasting Service

The Demand Forecasting Service generates predictive time-series forecasts and backtesting evaluations for inventory and sales planning, based on historical confirmed observations (`SalesReportObservation`).

### Architecture & Components

```
Client / Agent
      │
      ▼
forecasting_routes.py (/api/v1/businesses/{business_id}/forecasting)
      │
      ▼
forecasting_handler.py (Request unpacking & standardized response format)
      │
      ▼
forecasting_service.py (Business checks, historical queries, persistence)
      │
      ▼
forecasting_engine.py (Pure computational algorithms: SMA, EMA, Holt-Winters, Backtesting)
      │
      ▼
Database (MySQL / SQLite)
   ├── forecast_runs (Run metadata, parameters, model used, evaluation metrics)
   └── forecast_results (Per-period predicted points with confidence intervals)
```

| Component | File | Responsibility |
|---|---|---|
| Engine | `app/services/forecasting_engine.py` | Statistical forecasting algorithms (SMA, EMA, Holt-Winters), backtesting, and error metrics (MAE, WAPE, Bias). |
| Service | `app/services/forecasting_service.py` | Multi-tenant observation retrieval, data sufficiency validation, execution orchestration, and DB persistence. |
| Handler | `app/handlers/forecasting_handler.py` | HTTP-layer handlers building standard response envelopes. |
| Routes | `app/routes/forecasting_routes.py` | FastAPI router mounted under `/api/v1/businesses/{business_id}/forecasting` (and `/api/v1/forecasting`). |
| Models | `app/models/forecast_run.py`, `app/models/forecast_result.py` | SQLAlchemy ORM models for runs and period results. |
| Schemas | `app/models/schemas/forecasting.py` | Pydantic schemas: `ForecastRequest`, `ForecastEvaluateRequest`, `ForecastRunResponse`, `DataSufficiencyResponse`. |

### Forecasting Models

1. **Simple Moving Average (SMA):**
   - Computes rolling arithmetic mean over recent observation periods.
   - Suitable for stable, low-volatility products.
2. **Exponential Moving Average (EMA):**
   - Applies exponential weighting factor (`alpha`), giving more weight to recent observations.
   - Best for fast-moving items with short-term trend shifts.
3. **Holt-Winters Exponential Smoothing:**
   - Triple exponential smoothing with level (`alpha`), trend (`beta`), and seasonal (`gamma`) smoothing parameters.
   - Supports additive and multiplicative seasonality patterns for cyclical product demand.
4. **Heuristic Fallback:**
   - If historical observations are sparse or insufficient for higher-order models, gracefully falls back to simple mean or zero baselines without crashing.

### Historical Data Sufficiency (`/sufficiency`)

Before running a forecast, clients can inspect data sufficiency:
- **Daily granularity:** Requires at least 14 historical observations.
- **Weekly granularity:** Requires at least 8 historical observations.
- **Monthly granularity:** Requires at least 6 historical observations.
- Returns `is_sufficient: bool`, `observation_count: int`, and `recommended_model: str`.

### Backtesting & Evaluation (`/evaluate`)

Backtesting splits historical observations into training and test sets in chronological order:
- **MAE (Mean Absolute Error):** Average magnitude of forecast errors in raw units.
- **WAPE (Weighted Absolute Percentage Error):** Normalized percentage error across all evaluated periods.
- **Bias Percentage:** Measures systematic over-forecasting or under-forecasting tendencies.
- Returns actual vs. predicted values for each backtested time point.

### Endpoints Reference

| Method | Path | Auth / Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/businesses/{b_id}/forecasting/predict` | Owner / Admin / Manager | Generate and persist a demand forecast run and result points. |
| `POST` | `/api/v1/businesses/{b_id}/forecasting/evaluate` | Owner / Admin / Manager | Run historical backtesting and return MAE, WAPE, and bias metrics. |
| `GET` | `/api/v1/businesses/{b_id}/forecasting/sufficiency` | Member | Check if sufficient observation history exists for forecasting. |
| `GET` | `/api/v1/businesses/{b_id}/forecasting/runs` | Member | List past forecast runs with pagination and status filters. |
| `GET` | `/api/v1/businesses/{b_id}/forecasting/runs/{run_id}` | Member | Retrieve a specific forecast run with all period predicted points. |

