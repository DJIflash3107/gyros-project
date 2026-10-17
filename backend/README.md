# Gyros Project — Backend API

A production-grade REST API backend built with **FastAPI**, **SQLAlchemy 2.0**, and **Pydantic v2**, featuring multi-tenant business data management (businesses, branches, products, sales reporting, expenses), native AI integration via **AMD Radeon Cloud Token Factory**, an agentic **Business Operations Agent** built with **LangGraph**, a multi-sheet **Sales Report Processing & LLM Semantic Mapping** engine, a predictive **Demand Forecasting Service**, an intelligent **Business Action Center**, and an **AI-Assisted Promotion Planner**.

---

## Features

- **Multi-Tenant Architecture**: Strict tenancy isolation and role-based access control (`owner`, `admin`, `manager`, `member`, `viewer`).
- **Standardized Response Envelope**: Uniform JSON response shape across all standard endpoints:
  - `{ "message": { "success": "..." }, "error": {}, "data": { ... } }`
- **Traceable Error Handling**: Centralized exception handling with unique traceable error codes (e.g. `ERR-40001`, `ERR-AI-429`, `ERR-AGT-408`, `ERR-RPT-001`, `ERR-RPT-021`, `ERR-FOR-001`, `ERR-BAC-001`, `ERR-PRO-001`) and correlated `request_id` context in every log record.
- **AI-Assisted Promotion Planner**:
  - Deterministic financial evaluation engine calculating discount prices, estimated contribution, unit margins, and volume scenarios (conservative, base, aggressive) using backend math—strictly no LLM arithmetic.
  - Enforces configurable financial constraints, including minimum acceptable margin thresholds and budget caps.
  - Generates structured proposals: product-specific discounts, bundled offerings, and time-limited promotional campaigns.
  - Explicit disclosures of missing cost/price data, assumptions, operational risks, and financial validation status (`financially_validated: true/false`).
  - Dynamic AI-generated narratives providing promotional copy, operational considerations, terms & conditions, and risks & mitigations.
  - Full lifecycle tracking (`draft`, `scheduled`, `active`, `completed`, `cancelled`) with database persistence or ephemeral evaluation (`persist=false`).
  - Native integration with the Business Operations Agent via the `invoke_promotion_planner` tool.
- **Business Action Center**:
  - Deterministic recommendation engine analyzing operational data across 4 domains: Inventory (spoilage, leftover, damage), Sales (zero-sales dead items, high-volume revenue drivers), Demand Forecasting (demand surges, demand drops, model unreliability), and Expenses (category surges, cost concentration).
  - Explicit scoring formula based on urgency, expected impact, priority score (10–99), and deterministic modifiers (cross-validation between inventory and forecasting, systemic multi-issue branches).
  - **Dynamic AI-Generated Narratives**: Refactored to dynamically generate 6 narrative fields (`title`, `rationale`, `recommended_steps`, `risks`, `success_metrics`, `limitations`) via LLM in fluent, professional English with strictly no silent fallbacks.
  - **Action Status Lifecycle**: Supports tracking recommendations through `open`, `in_progress`, `implemented`, `dismissed` (with reason), and `archived`.
  - **Deduplication & Ephemeral Mode**: Deduplicates existing open actions on re-generation, or runs in preview/ephemeral mode (`persist=false`) without database writes.
  - Native integration with the Business Operations Agent via the `invoke_action_center` tool.
- **Sales Report Processing & Staging Workflow**:
  - Multi-channel ingestion supporting **Spreadsheets** (`.xlsx`, `.xls`, `.csv`), **Batch Manual Forms** (up to 500 rows), and **Sales-record Photos / Receipts** (vision OCR).
  - **Multi-Photo Ingestion**: Ingest multiple receipt/sales photos in a single request (up to 10 images via `files`), preserving `source_image_index` and `source_image_name` on staging rows, merged into a unified submission. Full backward compatibility with single `file`.
  - **Auto-Sync Product Price & Cost History**: Confirmed submissions automatically generate or update `ProductPriceHistory` and `ProductCostHistory` records from parsed Excel headers (`Harga Jual`, `HPP`, `price`, `cost`, etc.) and photo OCR. Includes an intelligent derived price fallback (`recorded_revenue / sold_qty`), overlap protection, safe closing of previous records without violating check constraints, and idempotency.
  - **Auto-Create Missing Products & Branches (Draft Workflow)**: Automatically creates missing products or branches as `draft` entities (`status="draft"`, `is_active=False`) during ingestion, tagging staging rows as `pending_review` with warnings (`RPT-VAL-011`, `RPT-VAL-012`). Requires explicit operator review and activation (`/activate`) before submission confirmation.
  - **Orphan Draft Cleanup**: Confirmation automatically cleans up and deletes unreferenced draft products or branches auto-created during the submission.
  - **Multi-Sheet Workbook Processing**: Inspects every worksheet independently in an uploaded `.xlsx`, using LLM sheet role classification (`sales`, `reference`, `instructional`, `ambiguous`), per-sheet column mapping, and cross-sheet duplicate detection.
  - **Staging-Only Invariant**: Extracted data is always persisted to staging rows (`SalesReportStagingRow`) and is **never** auto-confirmed.
  - **Bulk Staging Row Review & Update**: Dedicated `PATCH`/`POST` `/staging_rows/bulk` endpoint to mark multiple or all rows as `ready`, set review notes, or update branch/product links in one call.
  - **Explicit Confirmation**: Safe transition from staging rows into immutable confirmed observations (`SalesReportObservation`) via authenticated `POST .../{submission_id}/confirm`.
  - **Centralized Validation Engine**: 12 automated business integrity checks including product alias resolution, branch validation, date range coverage, non-negative bounds, intra-batch duplicate detection, cross-submission observation overlap protection, and draft activation warnings.
  - **SHA-256 Deduplication**: File hashing blocks accidental re-upload of active submissions.
  - **Real-Time Progress Streaming**: SSE streaming for photo extraction and long-running validation tasks (`report_status`, `extraction_progress`, `validation_result`, `report_complete`, `report_error`).
- **Dynamic Profiling & LLM Semantic Mapping**:
  - Layout-agnostic spreadsheet parsing powered by AMD Token Factory LLMs.
  - Automatic inspection of sheet names, raw headers, sample rows, inferred data types, and merged cells.
  - Semantic mapping of arbitrary English, Indonesian, or colloquial column titles into a unified canonical schema (`CANONICAL_FIELDS`).
  - Per-column confidence scoring and reasoning with automatic warning issues (`ERR-RPT-021`) for low-confidence fields.
  - **Deterministic Fallback**: Automatically falls back to a static mapping dictionary if LLM services are offline or disabled.
- **Demand Forecasting Service**:
  - Time-series statistical and predictive modeling algorithms: Simple Moving Average (SMA), Exponential Moving Average (EMA), and Holt-Winters Exponential Smoothing (with additive/multiplicative trend and seasonality).
  - **Historical Data Sufficiency**: Inspects observation history (`/sufficiency`) against required thresholds before generating forecasts.
  - **Predictive Backtesting Evaluation**: Evaluates model performance (`/evaluate`) against historical actuals with Mean Absolute Error (MAE), Weighted Absolute Percentage Error (WAPE), and Bias percentage.
  - **Persistent Runs**: Tracks forecast run metadata, model parameters, and per-period predicted points with confidence intervals (`/runs`).
- **Business Operations Agent (LangGraph)**:
  - Real-time conversational AI assistant powered by a LangGraph `StateGraph` workflow.
  - Genuine token-by-token and lifecycle streaming over Server-Sent Events (SSE) via `POST /api/v1/agent/businesses/{business_id}/chat`.
  - 7 structured SSE event types: `agent_status`, `tool_start`, `tool_result`, `message_delta`, `approval_required`, `agent_error`, `agent_complete`.
  - Operational tools: `business_summary`, `sales_analytics`, `expense_summary`, `product_catalog`, `invoke_forecasting`, `invoke_action_center`, `invoke_promotion_planner`, plus stub for `invoke_artifact_service`.
  - Security guardrails: zero database writes, strict cross-tenant filtering by `business_id`, chain-of-thought `<think>` block sanitization, and request timeouts.
- **AMD Token Factory AI Integration**:
  - Runtime model discovery (`GET /api/v1/ai/models`) with capability flags (streaming, vision, reasoning, tool calling).
  - Operational health & quota check (`GET /api/v1/ai/health`).
  - Chat completions & real-time SSE streaming (`POST /api/v1/ai/chat/completions`).
  - Exponential backoff with jitter on rate limits (`429`) and gateway saturation (`502`/`503`).
  - Graceful degradation: server boots normally without API credentials.
  - Zero placeholder output policy: errors are raised explicitly and traceably.
- **Database Migrations**: Managed schema versions using **Alembic**.
- **Automated Testing**: 218 unit and integration tests executing against isolated in-memory SQLite (no external MySQL server required for CI/testing).

---

## Tech Stack

| Component | Technology |
|---|---|
| **Framework** | [FastAPI](https://fastapi.tiangolo.com/) (0.115+) |
| **Validation & Settings** | [Pydantic v2](https://docs.pydantic.dev/) + `pydantic-settings` |
| **ORM & Database** | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) + [PyMySQL](https://pymysql.readthedocs.io/) |
| **Database Migrations** | [Alembic](https://alembic.sqlalchemy.org/) |
| **Authentication** | [PyJWT](https://pyjwt.readthedocs.io/) (HS256) + [bcrypt](https://pypi.org/project/bcrypt/) |
| **Agent & Workflow Graph** | [LangGraph](https://langchain-ai.github.io/langgraph/) (0.4+) + [LangChain Core](https://python.langchain.com/) + [LangChain OpenAI](https://github.com/langchain-ai/langchain) |
| **LLM Gateway / Provider** | [AMD Token Factory](https://developer.amd.com.cn/) (OpenAI-compatible, chat & vision) |
| **Spreadsheet Ingestion** | [openpyxl](https://openpyxl.readthedocs.io/) (3.1+ for Excel `.xlsx`) + `csv` stdlib |
| **HTTP Client / Streaming** | [HTTPX](https://www.python-httpx.org/) (Async client with connection pooling) |
| **Testing** | [pytest](https://docs.pytest.org/) + `pytest-asyncio` |

---

## Project Structure

```
backend/
├── app/
│   ├── agent/                # Business Operations Agent (LangGraph)
│   │   ├── graph.py          # StateGraph workflow, nodes, conditional edges
│   │   ├── prompts.py        # System prompt guardrails & response sanitizer
│   │   ├── state.py          # AgentState TypedDict definition
│   │   └── tools.py          # 8 read-only operational tools & LangChain bindings
│   ├── configs/              # Settings, database connection, security, AMD HTTP client
│   │   ├── amd_client.py     # AMD Token Factory client (retries, backoff, streaming)
│   │   ├── database.py       # Engine, Base, SessionLocal, get_db()
│   │   ├── security.py       # Password hashing & JWT token helpers
│   │   └── settings.py       # Pydantic Settings class (reads from .env)
│   ├── handlers/             # HTTP-layer request unpackers & response formatters
│   │   ├── agent_handler.py                  # Agent SSE streaming chat handler
│   │   ├── ai_handler.py                     # AI discovery & completion handlers
│   │   ├── business_action_handler.py        # Business action recommendation & status handlers
│   │   ├── promotion_handler.py              # Promotion generation, list, detail, status & eval handlers
│   │   ├── sales_report_submission_handler.py # Process, batch form, confirm & CRUD handlers
│   │   ├── sales_report_staging_row_handler.py# Staging row review & status updates (including bulk)
│   │   ├── sales_report_observation_handler.py# Confirmed sales observation queries
│   │   ├── forecasting_handler.py            # Forecasting predict, evaluate, and sufficiency handlers
│   │   ├── import_issue_handler.py           # Import validation issue queries
│   │   ├── product_alias_handler.py          # Product alias management
│   │   └── <entity>_handler.py
│   ├── helpers/              # Logging, exceptions, error codes, response builders
│   ├── middlewares/          # RequestContextMiddleware & auth dependency guards
│   ├── models/               # SQLAlchemy ORM models & Pydantic schemas
│   │   ├── business_action.py           # Persisted recommendations and lifecycle status
│   │   ├── promotion_plan.py            # Promotion proposals, financial metrics & lifecycle status
│   │   ├── sales_report_submission.py   # Ingestion submissions
│   │   ├── sales_report_staging_row.py  # Staging rows (never auto-finalized, unit_price, unit_cost)
│   │   ├── sales_report_observation.py  # Confirmed observations
│   │   ├── forecast_run.py              # Forecast runs metadata & error metrics
│   │   ├── forecast_result.py           # Forecast period points & confidence intervals
│   │   ├── import_issue.py              # Staging validation & extraction issues
│   │   ├── product_alias.py             # Alias mappings
│   │   └── schemas/          # Input/output schemas (BaseModel)
│   │       ├── agent.py                  # SSE event & chat request schemas
│   │       ├── ai.py                     # AI provider schemas
│   │       ├── business_action.py        # GenerateActionsRequest, UpdateActionStatus, Response
│   │       ├── promotion.py              # GeneratePromotionRequest, PromotionPlanResponse, Evaluate
│   │       ├── sales_report_processing.py # Batch form, process response & SSE schemas
│   │       ├── sales_report_submission.py # Submissions schemas
│   │       ├── sales_report_staging_row.py# Staging schemas (Create/Update/BulkUpdate/Response)
│   │       ├── sales_report_observation.py# Observation schemas
│   │       ├── forecasting.py            # ForecastRequest, ForecastEvaluateRequest, ForecastRunResponse
│   │       └── <entity>.py
│   ├── routes/               # FastAPI APIRouter endpoints mounted under /api/v1/
│   │   ├── agent_routes.py               # Agent chat endpoint
│   │   ├── ai_routes.py                  # AI discovery & completion endpoints
│   │   ├── business_action_routes.py     # Business Action Center routes (/generate, status, filters)
│   │   ├── promotion_routes.py           # AI-Assisted Promotion Planner routes (/generate, plans, eval)
│   │   ├── sales_report_submission_routes.py # /process, /batch_form, /{id}/confirm, CRUD
│   │   ├── sales_report_staging_row_routes.py# Staging rows CRUD and /bulk update
│   │   ├── sales_report_observation_routes.py
│   │   ├── forecasting_routes.py         # Demand forecasting routes (/predict, /evaluate, /sufficiency, /runs)
│   │   ├── import_issue_routes.py
│   │   ├── product_alias_routes.py
│   │   └── <entity>_routes.py
│   ├── services/             # Business logic and external service interactions
│   │   ├── action_narrative_generator.py     # Dynamic AI narrative generation (English prompts, JSON schema)
│   │   ├── agent_service.py                  # LangGraph astream_events orchestration
│   │   ├── ai_service.py                     # AMD AI service orchestration
│   │   ├── business_action_engine.py         # Deterministic multi-domain recommendation engine (10 rules)
│   │   ├── business_action_service.py        # BAC orchestration, deduplication, persistence & ephemeral mode
│   │   ├── promotion_engine.py               # Pure deterministic promotion math, scenarios & constraints
│   │   ├── promotion_narrative_generator.py  # AI promotion copy, operational notes & risk generation
│   │   ├── promotion_service.py              # Promotion planner orchestration, evaluation & persistence
│   │   ├── sales_report_processing_service.py # Ingestion orchestrator (spreadsheet/photo/form)
│   │   ├── input_profiler.py                 # Spreadsheet structural profiler (multi-sheet support)
│   │   ├── semantic_mapper.py                # LLM-based column mapper & sheet role classifier
│   │   ├── spreadsheet_parser.py             # Excel/CSV parser with dynamic mapping
│   │   ├── photo_extractor.py                # AMD VLM extraction with SSE progress streaming
│   │   ├── validation_engine.py              # 12-step centralized validation & alias resolution
│   │   ├── sales_report_submission_service.py # Submissions CRUD, confirmation & auto price/cost sync
│   │   ├── sales_report_staging_row_service.py# Staging row persistence & bulk updates
│   │   ├── forecasting_engine.py             # Statistical forecasting engine (SMA, EMA, Holt-Winters, Backtesting)
│   │   ├── forecasting_service.py            # Forecasting orchestration, validation & DB persistence
│   │   └── <entity>_service.py
│   └── main.py               # FastAPI application entry point & lifespan management
├── alembic/                  # Database migration scripts & environment
├── tests/                    # Pytest test suite (in-memory SQLite)
│   ├── test_action_narrative_generator.py # AI narrative generator unit tests & error propagation
│   ├── test_agent_*.py                   # Agent auth, graph, streaming, and tool suites
│   ├── test_ai_endpoints.py              # Tests for /api/v1/ai routes
│   ├── test_amd_client.py                # Tests for AMDTokenFactoryClient
│   ├── test_auto_price_cost_history.py   # Auto-sync price & cost history from spreadsheet/photo imports
│   ├── test_business_action_engine.py    # Deterministic rule engine, scoring, and modifier tests
│   ├── test_business_actions.py          # BAC endpoints, persistence, lifecycle, and agent tool tests
│   ├── test_promotion_engine.py          # Pure deterministic promotion math & scenario tests
│   ├── test_promotion_planner.py         # Promotion endpoints, lifecycle, evaluation & agent tool tests
│   ├── test_sales_report_processing.py   # Multi-channel ingestion, validation, and confirmation
│   ├── test_multi_sheet_processing.py    # Multi-sheet Excel workbook ingestion tests
│   ├── test_sales_report_staging_row_bulk.py # Staging row bulk update tests
│   ├── test_semantic_mapping.py          # Profiler, LLM semantic mapper, and fallback tests
│   ├── test_forecasting_engine.py        # Statistical forecasting engine tests
│   ├── test_forecasting_endpoints.py     # Forecasting endpoints tests (predict, evaluate, sufficiency)
│   ├── test_sales_submissions.py         # Submissions CRUD and review lifecycle
│   └── test_*.py                         # Feature-grouped test files
├── .env.example              # Environment variables template
├── alembic.ini               # Alembic configuration
└── requirements.txt          # Python dependencies
```

---

## Getting Started

### 1. Prerequisites

- **Python**: Version 3.11 or higher
- **MySQL**: (For local/production deployment) or SQLite (for automated testing)
- Optional: `uv` package manager

### 2. Environment Setup

Create and activate a virtual environment:

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Configuration

Copy the example environment configuration:

```bash
cp .env.example .env
```

Edit `.env` to configure your settings:

```dotenv
# Database Configuration
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/gyros_db?charset=utf8mb4

# JWT Authentication
JWT_SECRET_KEY=change-this-to-a-secure-random-secret-key-at-least-32-chars
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Application Configuration
APP_NAME=GyrosProject
APP_ENV=development
APP_DEBUG=true
LOG_LEVEL=INFO

# AMD Token Factory Configuration
AMD_API_BASE_URL=https://developer.amd.com.cn/radeon/api/v1
AMD_API_KEY=rc-...               # Your redeemed team key
AMD_DEFAULT_MODEL=DeepSeek-V4-Flash
AMD_REQUEST_TIMEOUT=600          # 10 minutes per AMD documentation
AMD_STREAM_CHUNK_TIMEOUT=600     # Maximum gap between streaming tokens
AMD_MAX_RETRIES=3                # Retries on 429/502/503

# Agent Configuration (LangGraph)
AGENT_MAX_TURNS=10               # Max tool round-trips per conversation turn
AGENT_REQUEST_TIMEOUT=120        # Total agent request timeout in seconds
AGENT_MAX_TOKENS=4096            # Max tokens for agent LLM responses
AGENT_TEMPERATURE=0.3            # Conservative temperature for business ops

# Vision Configuration (Photo Extraction)
VISION_MODEL_OVERRIDE=""         # Specific vision model override (empty = auto-discover)
VISION_MAX_IMAGE_SIZE_MB=5       # Max photo upload size
VISION_EXTRACTION_TEMPERATURE=0.1 # Low temperature for accurate OCR

# Semantic Mapping Configuration (Dynamic Column Profiling)
SEMANTIC_MAPPING_ENABLED=true    # Toggle LLM dynamic mapping
SEMANTIC_MAPPING_MODEL=""        # Model for column mapping (empty = AMD_DEFAULT_MODEL)
SEMANTIC_MAPPING_TEMPERATURE=0.0 # Deterministic schema mapping
SEMANTIC_MAPPING_CONFIDENCE_THRESHOLD=0.7 # Minimum confidence score threshold
```

> **Note:** If `AMD_API_KEY` is not provided, the application will boot and run normal CRUD, spreadsheet parsing (via static fallback), and manual form processing without issue. Calls to AI-specific endpoints will return a standardized `503 Service Unavailable` (`ERR-AI-501`).

### 4. Database Migrations

Apply pending database migrations:

```bash
alembic upgrade head
```

To create a new migration after editing ORM models:

```bash
alembic revision --autogenerate -m "describe_change"
```

### 5. Running the Application

Using `fastapi` CLI:

```bash
fastapi dev app/main.py
```

Or using `uvicorn`:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Once running, interactive documentation is available at:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## API Overview

All API routes are prefixed with `/api/v1`.

### Authentication & Users
- `POST /api/v1/auth/register` — Register a new user
- `POST /api/v1/auth/login` — Login and receive access token
- `GET /api/v1/users/me` — Retrieve authenticated user profile

### Multi-Tenant Core
- `POST /api/v1/businesses` — Create a new business organization
- `GET /api/v1/businesses` — List accessible businesses
- `POST /api/v1/businesses/{id}/memberships` — Manage business members and roles
- `GET /api/v1/businesses/{id}/branches` — Manage branches (supports `?status=active|draft|all`)
- `POST /api/v1/businesses/{id}/branches/{branch_id}/activate` — Activate auto-created draft branch with required info
- `GET /api/v1/businesses/{id}/products` — Product catalog and SKU management (supports `?status=active|draft|all`)
- `POST /api/v1/businesses/{id}/products/{product_id}/activate` — Activate auto-created draft product with required info
- `GET /api/v1/businesses/{id}/product_aliases` — Multi-channel alias mappings
- `GET /api/v1/businesses/{id}/product_cost_history` — Cost history tracking
- `GET /api/v1/businesses/{id}/product_price_history` — Price history tracking
- `GET /api/v1/businesses/{id}/expenses` — Expense ledger tracking

### Sales Report Ingestion, Staging & Confirmation
- `POST /api/v1/businesses/{business_id}/sales_report_submissions/process` — Ingest spreadsheet (`.xlsx`, `.xls`, `.csv`) or photos (supports single `file` or multi-photo `files` up to 10 images) with LLM dynamic semantic mapping, multi-sheet inspection, draft master data auto-creation, and validation.
- `POST /api/v1/businesses/{business_id}/sales_report_submissions/batch_form` — Batch manual form submission (up to 500 rows).
- `POST /api/v1/businesses/{business_id}/sales_report_submissions/{submission_id}/confirm` — Atomically confirm reviewed staging rows into immutable `SalesReportObservation` records (guards against unactivated draft entities; cleans up orphan drafts).
- `GET /api/v1/businesses/{business_id}/sales_report_submissions` — List submissions with pagination and status filters (`pending`, `processing`, `reviewed`, `confirmed`, `rejected`).
- `GET /api/v1/businesses/{business_id}/sales_report_submissions/{submission_id}` — Get submission details and summary counters.
- `GET /api/v1/sales_report_submissions/{submission_id}/staging_rows` — Query staging rows by review status (`ready`, `pending_review`, `needs_correction`).
- `PATCH /api/v1/sales_report_submissions/{submission_id}/staging_rows/bulk` — Bulk update staging rows (all or by ID list, e.g. mark `ready` or update notes).
- `POST /api/v1/sales_report_submissions/{submission_id}/staging_rows/bulk` — Alternative method for bulk update.
- `PATCH /api/v1/sales_report_submissions/{submission_id}/staging_rows/{row_id}` — Correct individual staging row values (e.g. resolve unmapped product).
- `GET /api/v1/businesses/{business_id}/sales_report_observations` — Query confirmed sales observations for analytics and reporting.
- `GET /api/v1/sales_report_submissions/{submission_id}/import_issues` — Query extraction and validation issues.

### Demand Forecasting
- `POST /api/v1/businesses/{business_id}/forecasting/predict` — Generate and persist product demand forecasts (SMA, EMA, Holt-Winters).
- `POST /api/v1/businesses/{business_id}/forecasting/evaluate` — Run time-ordered backtesting and calculate error metrics (MAE, WAPE, Bias).
- `GET /api/v1/businesses/{business_id}/forecasting/sufficiency` — Check if sufficient historical observation data exists for forecasting.
- `GET /api/v1/businesses/{business_id}/forecasting/runs` — List historical forecast runs with pagination and status filters.
- `GET /api/v1/businesses/{business_id}/forecasting/runs/{run_id}` — Get a specific forecast run with predicted period points and prediction intervals.

### AI-Assisted Promotion Planner
- `POST /api/v1/businesses/{business_id}/promotions/generate` — Generate structured promotion proposals (discounts, bundles, flash sales) with deterministic financial calculations (contribution margins, conservative/base/aggressive scenarios), financial constraint validation, and dynamic AI-generated marketing copy and operational notes (`persist: true|false`).
- `GET /api/v1/businesses/{business_id}/promotions/plans` — List promotion plans with filtering (`status`, `promotion_type`, `financially_validated`, `product_id`) and pagination.
- `GET /api/v1/businesses/{business_id}/promotions/plans/{plan_id}` — Retrieve detailed promotion plan proposal, including product breakdown, financial metrics, scenarios, and AI narratives.
- `PATCH /api/v1/businesses/{business_id}/promotions/plans/{plan_id}/status` — Update plan status (`draft`, `scheduled`, `active`, `completed`, `cancelled`).
- `POST /api/v1/businesses/{business_id}/promotions/plans/{plan_id}/evaluate` — Re-evaluate an existing plan's financial viability against updated product price and cost history.
- Direct endpoints: `/api/v1/promotions/generate`, `/api/v1/promotions/plans`, `/api/v1/promotions/plans/{plan_id}`, `/api/v1/promotions/plans/{plan_id}/status`, and `/api/v1/promotions/plans/{plan_id}/evaluate` for top-level access.

### Business Action Center
- `POST /api/v1/businesses/{business_id}/business-actions/generate` — Generate and rank operational recommendations. Evaluates deterministic rules across Inventory, Sales, Forecasting, and Expenses, enriches candidates with LLM dynamic narratives, and deduplicates or returns ephemerally (`persist: false`).
- `GET /api/v1/businesses/{business_id}/business-actions` — List recommendations with filtering (`status`, `category`, `urgency`, `evidence_quality`, `branch_id`, `product_id`, `min_priority`) and pagination.
- `GET /api/v1/businesses/{business_id}/business-actions/{action_id}` — Retrieve detailed action candidate with AI rationale, recommended steps, risks, success metrics, limitations, and supporting data.
- `PATCH /api/v1/businesses/{business_id}/business-actions/{action_id}/status` — Update action status (`in_progress`, `implemented`, `dismissed` with reason, `archived`).
- Direct endpoints: `/api/v1/business-actions/generate`, `/api/v1/business-actions/`, `/api/v1/business-actions/{action_id}`, and `/api/v1/business-actions/{action_id}/status` for top-level access.

### Business Operations Agent (LangGraph)
- `POST /api/v1/agent/businesses/{business_id}/chat` — Conversational business operations assistant streaming real-time Server-Sent Events (SSE). Requires JWT authentication and business membership.
  - Stream events: `agent_status`, `tool_start`, `tool_result`, `message_delta`, `approval_required`, `agent_error`, `agent_complete`, ending with `[DONE]`.

### AI Endpoints (AMD Token Factory)
- `GET /api/v1/ai/models` — Runtime discovery of available models with capability flags
- `GET /api/v1/ai/health` — Check AI provider connectivity, latency, quota, and rate limits
- `POST /api/v1/ai/chat/completions` — Chat completions with optional real-time token streaming (`stream: true`)

---

## Testing

The backend includes a comprehensive test suite (**218 test cases**) utilizing an isolated in-memory SQLite database:

```bash
# Run all tests
pytest -v

# Run AI-Assisted Promotion Planner tests (Deterministic Engine, Scenarios, Constraints & Endpoints)
pytest tests/test_promotion_engine.py tests/test_promotion_planner.py -v

# Run Auto-Sync Price & Cost History tests
pytest tests/test_auto_price_cost_history.py -v

# Run Business Action Center tests (Deterministic Engine, AI Narrative Generator & Endpoints)
pytest tests/test_business_action_engine.py tests/test_action_narrative_generator.py tests/test_business_actions.py -v

# Run Sales Report Processing, Draft Master Data, Multi-Photo, Multi-Sheet, Bulk Staging, and Semantic Mapping tests
pytest tests/test_sales_report_processing.py tests/test_validation_engine_draft.py tests/test_draft_activate.py tests/test_multi_photo_processing.py tests/test_multi_sheet_processing.py tests/test_sales_report_staging_row_bulk.py tests/test_semantic_mapping.py tests/test_sales_submissions.py -v

# Run Demand Forecasting tests (Engine & Endpoints)
pytest tests/test_forecasting_engine.py tests/test_forecasting_endpoints.py -v

# Run Business Operations Agent tests
pytest tests/test_agent_auth.py tests/test_agent_tools.py tests/test_agent_graph.py tests/test_agent_streaming.py -v

# Run AI / AMD Token Factory tests
pytest tests/test_amd_client.py tests/test_ai_endpoints.py -v

# Run authentication and authorization tests
pytest tests/test_auth.py tests/test_authorization.py -v
```

---

## Developer Guidelines

For detailed architecture guidelines, coding patterns, response envelope standards, and adding new entities, refer to:
- [`AGENTS.md`](./AGENTS.md) — The authoritative guide for human and AI developers working on this codebase.

