from datetime import date
from decimal import Decimal
from unittest.mock import patch
import pytest

from app.models.business import Business
from app.models.branch import Branch
from app.models.product import Product
from app.models.expense import Expense
from app.models.sales_report_submission import SalesReportSubmission
from app.models.sales_report_observation import SalesReportObservation
from app.models.user import User

from app.agent.tools import (
    execute_business_summary,
    execute_sales_analytics,
    execute_expense_summary,
    execute_product_catalog,
    execute_invoke_forecasting,
    execute_invoke_action_center,
    execute_invoke_promotion_planner,
    execute_invoke_artifact_service,
    execute_tool_by_name,
    get_agent_tools,
)


@pytest.fixture
def sample_business_data(db_session):
    """Fixture that seeds sample business, branches, products, sales observations, and expenses."""
    user = User(
        email="owner@example.com",
        password_hash="hashedpassword",
        full_name="Owner",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    biz = Business(name="Acme Foods", currency="USD", timezone="UTC")
    db_session.add(biz)
    db_session.flush()

    branch1 = Branch(business_id=biz.id, name="Downtown Branch", branch_code="DT-01", is_active=True)
    branch2 = Branch(business_id=biz.id, name="Uptown Branch", branch_code="UT-02", is_active=True)
    db_session.add_all([branch1, branch2])
    db_session.flush()

    prod1 = Product(business_id=biz.id, name="Shawarma", category="Food", base_unit="portion", is_active=True)
    prod2 = Product(business_id=biz.id, name="Falafel", category="Food", base_unit="portion", is_active=True)
    prod3 = Product(business_id=biz.id, name="Lemonade", category="Beverage", base_unit="glass", is_active=True)
    db_session.add_all([prod1, prod2, prod3])
    db_session.flush()

    sub = SalesReportSubmission(
        business_id=biz.id,
        submitted_by_user_id=user.id,
        branch_id=branch1.id,
        input_method="manual",
        report_period_type="daily",
        coverage_start=date(2026, 10, 1),
        coverage_end=date(2026, 10, 1),
        status="completed",
    )
    db_session.add(sub)
    db_session.flush()

    obs1 = SalesReportObservation(
        business_id=biz.id,
        branch_id=branch1.id,
        product_id=prod1.id,
        source_submission_id=sub.id,
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 1),
        granularity="daily",
        sold_qty=Decimal("45.0"),
        recorded_revenue=Decimal("450.00"),
        record_status="active",
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    obs2 = SalesReportObservation(
        business_id=biz.id,
        branch_id=branch1.id,
        product_id=prod2.id,
        source_submission_id=sub.id,
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 1),
        granularity="daily",
        sold_qty=Decimal("30.0"),
        recorded_revenue=Decimal("150.00"),
        record_status="active",
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db_session.add_all([obs1, obs2])

    exp1 = Expense(
        business_id=biz.id,
        branch_id=branch1.id,
        expense_date=date(2026, 10, 1),
        category="Utilities",
        amount=Decimal("120.00"),
        currency="USD",
        created_by_user_id=user.id,
    )
    exp2 = Expense(
        business_id=biz.id,
        branch_id=branch1.id,
        expense_date=date(2026, 10, 2),
        category="Ingredients",
        amount=Decimal("300.00"),
        currency="USD",
        created_by_user_id=user.id,
    )
    db_session.add_all([exp1, exp2])
    db_session.commit()

    return {
        "user": user,
        "business": biz,
        "branches": [branch1, branch2],
        "products": [prod1, prod2, prod3],
        "observations": [obs1, obs2],
        "expenses": [exp1, exp2],
    }


def test_business_summary_returns_data(db_session, sample_business_data):
    """business_summary tool returns business name, branch count, and data fields."""
    biz_id = sample_business_data["business"].id
    result = execute_business_summary(db_session, biz_id)

    assert "Acme Foods" in result["summary"]
    assert result["data"] is not None
    assert result["data"]["business_name"] == "Acme Foods"
    assert result["data"]["branch_count"] == 2
    assert len(result["data"]["branches"]) == 2


def test_sales_analytics_returns_aggregates(db_session, sample_business_data):
    """sales_analytics tool returns aggregated revenue and top products."""
    biz_id = sample_business_data["business"].id
    result = execute_sales_analytics(db_session, biz_id)

    assert result["data"] is not None
    assert result["data"]["total_revenue"] == 600.00
    assert result["data"]["total_sold_qty"] == 75.0
    assert result["data"]["observations_count"] == 2
    assert len(result["data"]["top_products"]) == 2
    # Shawarma (45 sold) should be top product
    top = result["data"]["top_products"][0]
    assert top["sold_qty"] == 45.0


def test_expense_summary_returns_breakdown(db_session, sample_business_data):
    """expense_summary tool returns total expenses and breakdown by category."""
    biz_id = sample_business_data["business"].id
    result = execute_expense_summary(db_session, biz_id)

    assert result["data"] is not None
    assert result["data"]["total_expenses"] == 420.00
    assert result["data"]["expense_count"] == 2
    assert result["data"]["by_category"]["Utilities"] == 120.00
    assert result["data"]["by_category"]["Ingredients"] == 300.00


def test_product_catalog_returns_products(db_session, sample_business_data):
    """product_catalog tool returns product count, list, and categories."""
    biz_id = sample_business_data["business"].id
    result = execute_product_catalog(db_session, biz_id)

    assert result["data"] is not None
    assert result["data"]["total_products"] == 3
    assert set(result["data"]["categories"]) == {"Food", "Beverage"}
    product_names = [p["name"] for p in result["data"]["products"]]
    assert "Shawarma" in product_names
    assert "Lemonade" in product_names


def test_stub_tools_return_unavailable(db_session):
    """Stub tools gracefully return not available status without throwing errors."""
    f_res = execute_invoke_forecasting(1, metric="revenue")
    assert f_res["data"]["status"] == "not_available"
    assert "not yet available" in f_res["summary"]

    a_res = execute_invoke_action_center(1, action="optimize_costs")
    assert a_res["data"]["status"] == "not_available"

    p_res = execute_invoke_promotion_planner(1, params={"discount": 10})
    assert p_res["data"]["status"] == "not_available"

    art_res = execute_invoke_artifact_service(1, artifact_type="pdf_report")
    assert art_res["data"]["status"] == "not_available"


def test_tools_never_write(db_session, sample_business_data):
    """Agent tool executions must NEVER insert, update, or delete records."""
    biz_id = sample_business_data["business"].id

    initial_businesses = db_session.query(Business).count()
    initial_branches = db_session.query(Branch).count()
    initial_products = db_session.query(Product).count()
    initial_observations = db_session.query(SalesReportObservation).count()
    initial_expenses = db_session.query(Expense).count()

    # Execute all tools
    execute_tool_by_name("business_summary", {}, db_session, biz_id)
    execute_tool_by_name("sales_analytics", {"period": "2026-10"}, db_session, biz_id)
    execute_tool_by_name("expense_summary", {"category": "Utilities"}, db_session, biz_id)
    execute_tool_by_name("product_catalog", {"category": "Food"}, db_session, biz_id)
    execute_tool_by_name("invoke_forecasting", {"metric": "revenue"}, db_session, biz_id)
    execute_tool_by_name("invoke_action_center", {"action": "check"}, db_session, biz_id)
    execute_tool_by_name("invoke_promotion_planner", {}, db_session, biz_id)
    execute_tool_by_name("invoke_artifact_service", {}, db_session, biz_id)

    # Verify counts remain completely unchanged
    assert db_session.query(Business).count() == initial_businesses
    assert db_session.query(Branch).count() == initial_branches
    assert db_session.query(Product).count() == initial_products
    assert db_session.query(SalesReportObservation).count() == initial_observations
    assert db_session.query(Expense).count() == initial_expenses


def test_tools_filter_by_business_id(db_session, sample_business_data):
    """Tools strictly isolate data and only return data for the requested business."""
    biz1_id = sample_business_data["business"].id

    # Create Business 2 with its own product
    biz2 = Business(name="Second Business", currency="USD", timezone="UTC")
    db_session.add(biz2)
    db_session.flush()

    prod_biz2 = Product(business_id=biz2.id, name="Biz2 Exclusive Item", category="Other", base_unit="unit")
    db_session.add(prod_biz2)
    db_session.commit()

    # Query Business 1 catalog
    res_b1 = execute_product_catalog(db_session, biz1_id)
    b1_names = [p["name"] for p in res_b1["data"]["products"]]
    assert "Biz2 Exclusive Item" not in b1_names
    assert "Shawarma" in b1_names

    # Query Business 2 catalog
    res_b2 = execute_product_catalog(db_session, biz2.id)
    b2_names = [p["name"] for p in res_b2["data"]["products"]]
    assert "Biz2 Exclusive Item" in b2_names
    assert "Shawarma" not in b2_names


def test_tool_error_is_sanitized(db_session):
    """Database exceptions during tool execution are sanitized without leaking SQL."""
    with patch("app.services.business_service.get_business", side_effect=Exception("SELECT * FROM secret_table error at 0xdeadbeef")):
        res = execute_business_summary(db_session, 1)
        assert res["data"] is None
        assert "SELECT" not in str(res)
        assert "secret_table" not in str(res)
        assert "Failed" in res["summary"] or "Unable" in res["error"]
