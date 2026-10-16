# Gyros Project — Backend API

A production-grade REST API backend built with **FastAPI**, **SQLAlchemy 2.0**, and **Pydantic v2**, featuring multi-tenant business data management (businesses, branches, products, sales reporting, expenses), native AI integration via **AMD Radeon Cloud Token Factory**, and an agentic **Business Operations Agent** built with **LangGraph**.

---

## Features

- **Multi-Tenant Architecture**: Strict tenancy isolation and role-based access control (`owner`, `admin`, `manager`, `member`, `viewer`).
- **Standardized Response Envelope**: Uniform JSON response shape across all standard endpoints:
  - `{ "message": { "success": "..." }, "error": {}, "data": { ... } }`
- **Traceable Error Handling**: Centralized exception handling with unique traceable error codes (e.g. `ERR-40001`, `ERR-AI-429`, `ERR-AGT-408`) and correlated `request_id` context in every log record.
- **Business Operations Agent (LangGraph)**:
  - Real-time conversational AI assistant powered by a LangGraph `StateGraph` workflow.
  - Genuine token-by-token and lifecycle streaming over Server-Sent Events (SSE) via `POST /api/v1/agent/businesses/{business_id}/chat`.
  - 7 structured SSE event types: `agent_status`, `tool_start`, `tool_result`, `message_delta`, `approval_required`, `agent_error`, `agent_complete`.
  - 8 read-only operational tools: `business_summary`, `sales_analytics`, `expense_summary`, `product_catalog`, plus stubs for `invoke_forecasting`, `invoke_action_center`, `invoke_promotion_planner`, and `invoke_artifact_service`.
  - Security guardrails: zero database writes, strict cross-tenant filtering by `business_id`, chain-of-thought `<think>` block sanitization, and request timeouts.
- **AMD Token Factory AI Integration**:
  - Runtime model discovery (`GET /api/v1/ai/models`) with capability flags (streaming, vision, reasoning, tool calling).
  - Operational health & quota check (`GET /api/v1/ai/health`).
  - Chat completions & real-time SSE streaming (`POST /api/v1/ai/chat/completions`).
  - Exponential backoff with jitter on rate limits (`429`) and gateway saturation (`502`/`503`).
  - Graceful degradation: server boots normally without API credentials.
  - Zero placeholder output policy: errors are raised explicitly and traceably.
- **Database Migrations**: Managed schema versions using **Alembic**.
- **Automated Testing**: 62 unit and integration tests executing against isolated in-memory SQLite (no external MySQL server required for CI/testing).

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
| **LLM Gateway / Provider** | [AMD Token Factory](https://developer.amd.com.cn/) (OpenAI-compatible) |
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
│   │   ├── agent_handler.py  # Agent SSE streaming chat handler
│   │   ├── ai_handler.py     # AI discovery & completion handlers
│   │   └── <entity>_handler.py
│   ├── helpers/              # Logging, exceptions, error codes, response builders
│   ├── middlewares/          # RequestContextMiddleware & auth dependency guards
│   ├── models/               # SQLAlchemy ORM models & Pydantic schemas
│   │   └── schemas/          # Input/output schemas (BaseModel)
│   │       ├── agent.py      # SSE event & chat request schemas
│   │       ├── ai.py         # AI provider schemas
│   │       └── <entity>.py
│   ├── routes/               # FastAPI APIRouter endpoints mounted under /api/v1/
│   │   ├── agent_routes.py   # Agent chat endpoint
│   │   ├── ai_routes.py      # AI discovery & completion endpoints
│   │   └── <entity>_routes.py
│   ├── services/             # Business logic and external service interactions
│   │   ├── agent_service.py  # LangGraph astream_events orchestration
│   │   ├── ai_service.py     # AMD AI service orchestration
│   │   └── <entity>_service.py
│   └── main.py               # FastAPI application entry point & lifespan management
├── alembic/                  # Database migration scripts & environment
├── tests/                    # Pytest test suite (in-memory SQLite)
│   ├── test_agent_auth.py    # Agent auth & cross-tenant isolation tests
│   ├── test_agent_graph.py   # LangGraph state & graph unit tests
│   ├── test_agent_streaming.py # SSE streaming, deltas, timeouts, disconnects
│   ├── test_agent_tools.py   # Read-only tools, zero writes, tenant filter tests
│   ├── test_ai_endpoints.py  # Tests for /api/v1/ai routes
│   ├── test_amd_client.py    # Tests for AMDTokenFactoryClient
│   └── test_*.py             # Feature-grouped test files
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
```

> **Note:** If `AMD_API_KEY` is not provided, the application will boot and run normal CRUD operations without issue. Calls to AI endpoints will return a standardized `503 Service Unavailable` (`ERR-AI-501`).

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
- `GET /api/v1/businesses/{id}/branches` — Manage physical/logical branches
- `GET /api/v1/businesses/{id}/products` — Product catalog and SKU management
- `GET /api/v1/businesses/{id}/product-aliases` — Multi-channel alias mappings
- `GET /api/v1/businesses/{id}/product-cost-history` — Cost history tracking
- `GET /api/v1/businesses/{id}/product-price-history` — Price history tracking

### Operations & Reporting
- `POST /api/v1/businesses/{id}/sales-reports/submissions` — Upload and submit sales report batches
- `GET /api/v1/businesses/{id}/sales-reports/staging-rows` — Staging row processing & reconciliation
- `GET /api/v1/businesses/{id}/sales-reports/observations` — Extracted report observations
- `GET /api/v1/businesses/{id}/expenses` — Expense ledger tracking
- `GET /api/v1/businesses/{id}/import-issues` — Reconciliation error & anomaly issues

### Business Operations Agent (LangGraph)
- `POST /api/v1/agent/businesses/{business_id}/chat` — Conversational business operations assistant streaming real-time Server-Sent Events (SSE). Requires JWT authentication and business membership.
  - Stream events: `agent_status`, `tool_start`, `tool_result`, `message_delta`, `approval_required`, `agent_error`, `agent_complete`, ending with `[DONE]`.

### AI Endpoints (AMD Token Factory)
- `GET /api/v1/ai/models` — Runtime discovery of available models with capability flags
- `GET /api/v1/ai/health` — Check AI provider connectivity, latency, quota, and rate limits
- `POST /api/v1/ai/chat/completions` — Chat completions with optional real-time token streaming (`stream: true`)

---

## Testing

The backend includes a comprehensive test suite (62 test cases) utilizing an isolated in-memory SQLite database:

```bash
# Run all tests
pytest -v

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
- [`AGENTS.md`](./AGENTS.md) — The comprehensive guide for human and AI developers working on this codebase.
