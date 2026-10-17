import traceback
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.configs.settings import settings
from app.helpers.logging import setup_logging, logger, error_code_var
from app.helpers.error_codes import generate_error_code
from app.helpers.exceptions import AppException
from app.helpers.response import error_response, success_response
from app.middlewares.request_context import RequestContextMiddleware

# Import routers
from app.routes import (
    auth_router,
    business_router,
    user_router,
    business_membership_router,
    branch_router,
    product_router,
    product_alias_router,
    sales_report_submission_router,
    sales_report_staging_row_router,
    sales_report_observation_router,
    import_issue_router,
    expense_router,
    product_cost_history_router,
    product_price_history_router,
    ai_router,
    agent_router,
    forecasting_router,
    direct_forecasting_router,
    business_action_router,
    direct_business_action_router,
)

from contextlib import asynccontextmanager
from app.configs.amd_client import close_amd_client

# Initialize structured logging
setup_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_amd_client()


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.APP_DEBUG,
    lifespan=lifespan,
)

# Middleware
app.add_middleware(RequestContextMiddleware)


# Exception Handlers
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    if exc.error_code:
        error_code_var.set(exc.error_code)
    logger.warning(f"{exc.message} - Errors: {exc.errors}")
    return error_response(
        message=exc.message,
        errors=exc.errors,
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors_dict = {}
    for err in exc.errors():
        loc = err.get("loc", [])
        field = str(loc[-1]) if loc else "request"
        msg = err.get("msg", "Invalid value")
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
        errors_dict[field] = msg

    error_code_var.set("ERR-42200")
    logger.warning(f"Request validation failed: {errors_dict}")
    return error_response(
        message="Request validation failed",
        errors=errors_dict,
        status_code=422,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    msg = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    return error_response(
        message=msg,
        errors={"http": msg},
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    error_code = generate_error_code()
    error_code_var.set(error_code)
    # Log unexpected exception with full stack trace and traceable error code
    logger.error(f"Cannot process request: {str(exc)}\n{traceback.format_exc()}")
    return error_response(
        message=f"{error_code}: An internal error occurred",
        errors={"server": "An internal error occurred"},
        status_code=500,
    )


# Health check / Welcome endpoint
@app.get("/")
def read_root():
    return success_response(
        message="Gyros Project API is running",
        data={"app": settings.APP_NAME, "env": settings.APP_ENV},
    )


# Include all routers
app.include_router(auth_router)
app.include_router(business_router)
app.include_router(user_router)
app.include_router(business_membership_router)
app.include_router(branch_router)
app.include_router(product_router)
app.include_router(product_alias_router)
app.include_router(sales_report_submission_router)
app.include_router(sales_report_staging_row_router)
app.include_router(sales_report_observation_router)
app.include_router(import_issue_router)
app.include_router(expense_router)
app.include_router(product_cost_history_router)
app.include_router(product_price_history_router)
app.include_router(ai_router)
app.include_router(agent_router)
app.include_router(forecasting_router)
app.include_router(direct_forecasting_router)
app.include_router(business_action_router)
app.include_router(direct_business_action_router)
