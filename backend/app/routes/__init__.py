from app.routes.auth_routes import router as auth_router
from app.routes.business_routes import router as business_router
from app.routes.user_routes import router as user_router
from app.routes.business_membership_routes import router as business_membership_router
from app.routes.branch_routes import router as branch_router
from app.routes.product_routes import router as product_router
from app.routes.product_alias_routes import router as product_alias_router
from app.routes.sales_report_submission_routes import router as sales_report_submission_router
from app.routes.sales_report_staging_row_routes import router as sales_report_staging_row_router
from app.routes.sales_report_observation_routes import router as sales_report_observation_router
from app.routes.import_issue_routes import router as import_issue_router
from app.routes.expense_routes import router as expense_router
from app.routes.product_cost_history_routes import router as product_cost_history_router
from app.routes.product_price_history_routes import router as product_price_history_router
from app.routes.ai_routes import router as ai_router

__all__ = [
    "auth_router",
    "business_router",
    "user_router",
    "business_membership_router",
    "branch_router",
    "product_router",
    "product_alias_router",
    "sales_report_submission_router",
    "sales_report_staging_row_router",
    "sales_report_observation_router",
    "import_issue_router",
    "expense_router",
    "product_cost_history_router",
    "product_price_history_router",
    "ai_router",
]
