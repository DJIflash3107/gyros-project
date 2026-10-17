from datetime import date, timedelta
from decimal import Decimal
import json
from unittest.mock import patch, AsyncMock
import pytest
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.branch import Branch
from app.models.product import Product
from app.models.business_membership import BusinessMembership
from app.models.sales_report_submission import SalesReportSubmission
from app.models.sales_report_observation import SalesReportObservation
from app.models.expense import Expense
from app.models.forecast_run import ForecastRun
from app.models.forecast_result import ForecastResult
from app.models.business_action import BusinessAction
from app.agent.tools import execute_tool_by_name
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.exceptions import AIServiceException


@pytest.fixture(autouse=True)
def mock_action_narrative_ai():
    """Mock LLM calls in integration tests so tests are fast, deterministic, and offline."""
    async def _mock_completion(messages, **kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "title": "Optimized AI Action Title",
                            "rationale": "AI rationale based strictly on measured supporting data.",
                            "recommended_steps": [
                                "Conduct immediate operational audit",
                                "Adjust supply batch quantities",
                                "Review KPIs weekly",
                            ],
                            "risks": ["Potential transition friction in kitchen workflow"],
                            "success_metrics": ["Achieve 15% reduction in target metric within 14 days"],
                            "limitations": "Constrained by available submission logs.",
                        })
                    }
                }
            ]
        }

    with patch("app.services.action_narrative_generator.chat_completion", side_effect=_mock_completion) as mock_ai:
        yield mock_ai


def _setup_test_environment(client, auth_headers):
    """Sets up a business, 2 branches, 3 products, and returns their IDs."""
    biz_resp = client.post(
        "/api/v1/businesses", json={"name": "Action Center Biz"}, headers=auth_headers
    )
    assert biz_resp.status_code == 201
    biz_id = biz_resp.json()["data"]["business"]["id"]

    branch_resp1 = client.post(
        f"/api/v1/businesses/{biz_id}/branches", json={"name": "Central"}, headers=auth_headers
    )
    branch_id1 = branch_resp1.json()["data"]["branch"]["id"]

    branch_resp2 = client.post(
        f"/api/v1/businesses/{biz_id}/branches", json={"name": "Westside"}, headers=auth_headers
    )
    branch_id2 = branch_resp2.json()["data"]["branch"]["id"]

    p_resp1 = client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Lamb Wrap", "category": "Food", "base_unit": "portion"},
        headers=auth_headers,
    )
    prod_id1 = p_resp1.json()["data"]["product"]["id"]

    p_resp2 = client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Greek Salad", "category": "Food", "base_unit": "portion"},
        headers=auth_headers,
    )
    prod_id2 = p_resp2.json()["data"]["product"]["id"]

    p_resp3 = client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Baklava", "category": "Dessert", "base_unit": "portion"},
        headers=auth_headers,
    )
    prod_id3 = p_resp3.json()["data"]["product"]["id"]

    return biz_id, branch_id1, branch_id2, prod_id1, prod_id2, prod_id3


def _populate_business_data(
    db: Session,
    biz_id: int,
    user_id: int,
    branch_id1: int,
    branch_id2: int,
    prod_id1: int,
    prod_id2: int,
    prod_id3: int,
):
    """Populates observations, expenses, and forecast runs."""
    today = date.today()

    # 1. Submission
    sub = SalesReportSubmission(
        business_id=biz_id,
        submitted_by_user_id=user_id,
        branch_id=branch_id1,
        input_method="manual",
        report_period_type="daily",
        coverage_start=today - timedelta(days=20),
        coverage_end=today,
        status="confirmed",
    )
    db.add(sub)
    db.flush()

    # 2. Observations
    # Product 1 at Branch 1: High Spoilage (INV-001)
    for i in range(15):
        obs_date = today - timedelta(days=i)
        db.add(
            SalesReportObservation(
                business_id=biz_id,
                source_submission_id=sub.id,
                branch_id=branch_id1,
                product_id=prod_id1,
                period_start=obs_date,
                period_end=obs_date,
                granularity="daily",
                sold_qty=Decimal("10"),
                spoiled_qty=Decimal("8"),  # Spoilage rate = 8 / 18 = 44.4% > 30% -> critical
                damaged_qty=Decimal("0"),
                leftover_qty=Decimal("0"),
                recorded_revenue=Decimal("300000"),
                record_status="active",
                created_by_user_id=user_id,
            )
        )

    # Product 2 at Branch 1: Excess Leftover (INV-002)
    for i in range(10):
        obs_date = today - timedelta(days=i)
        db.add(
            SalesReportObservation(
                business_id=biz_id,
                source_submission_id=sub.id,
                branch_id=branch_id1,
                product_id=prod_id2,
                period_start=obs_date,
                period_end=obs_date,
                granularity="daily",
                sold_qty=Decimal("5"),
                spoiled_qty=Decimal("0"),
                damaged_qty=Decimal("0"),
                leftover_qty=Decimal("15"),  # 15 > 2 * 5, 15 > 10
                recorded_revenue=Decimal("100000"),
                record_status="active",
                created_by_user_id=user_id,
            )
        )

    # Product 3 at Branch 1: Zero Sales (SAL-001)
    for i in range(16):
        obs_date = today - timedelta(days=i)
        db.add(
            SalesReportObservation(
                business_id=biz_id,
                source_submission_id=sub.id,
                branch_id=branch_id1,
                product_id=prod_id3,
                period_start=obs_date,
                period_end=obs_date,
                granularity="daily",
                sold_qty=Decimal("0"),
                spoiled_qty=Decimal("0"),
                damaged_qty=Decimal("0"),
                leftover_qty=Decimal("0"),
                recorded_revenue=Decimal("0"),
                record_status="active",
                created_by_user_id=user_id,
            )
        )

    # 3. Expenses: Surging ingredients (EXP-001) & Concentration (EXP-002)
    # Current period
    db.add(
        Expense(
            business_id=biz_id,
            branch_id=branch_id1,
            expense_date=today - timedelta(days=5),
            category="Meat & Poultry",
            amount=Decimal("2500000"),
            currency="IDR",
            created_by_user_id=user_id,
        )
    )
    # Prior period
    db.add(
        Expense(
            business_id=biz_id,
            branch_id=branch_id1,
            expense_date=today - timedelta(days=35),
            category="Meat & Poultry",
            amount=Decimal("1200000"),  # +108% surge
            currency="IDR",
            created_by_user_id=user_id,
        )
    )

    # 4. Forecast Run (FC-001: Demand surge on Product 1)
    fc_run = ForecastRun(
        business_id=biz_id,
        branch_id=branch_id1,
        product_id=prod_id1,
        method="moving_average",
        horizon_days=7,
        window_size=7,
        training_start=today - timedelta(days=14),
        training_end=today,
        observations_used=14,
        is_reliable=True,
        mae=Decimal("1.2"),
        wape=Decimal("0.08"),
        forecast_bias=Decimal("0.1"),
        created_by_user_id=user_id,
    )
    db.add(fc_run)
    db.flush()

    for d in range(1, 8):
        db.add(
            ForecastResult(
                forecast_run_id=fc_run.id,
                forecast_date=today + timedelta(days=d),
                predicted_qty=Decimal("25.0"),  # 7 * 25 = 175 predicted vs recent ~70 -> +150% surge
                weekday=d,
            )
        )

    db.commit()


# -------------------------------------------------------------
# Tests
# -------------------------------------------------------------

def test_generate_actions_persisted(client, auth_user, db_session):
    auth_headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, b1, b2, p1, p2, p3 = _setup_test_environment(client, auth_headers)
    _populate_business_data(db_session, biz_id, user_id, b1, b2, p1, p2, p3)

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/business-actions/generate",
        json={"lookback_days": 30, "persist": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "success" in body["message"]
    data = body["data"]

    assert data["generated_count"] > 0
    assert data["persisted_count"] == data["generated_count"]
    assert len(data["actions"]) == data["generated_count"]
    assert "observations_analyzed" in data["data_summary"]

    first_action = data["actions"][0]
    assert "id" in first_action
    assert "title" in first_action
    assert first_action["title"] == "Optimized AI Action Title"
    assert "rule_label" in first_action
    assert first_action["rule_label"] != ""
    assert first_action["ai_generated"] is True
    assert "urgency" in first_action
    assert "expected_impact" in first_action
    assert "priority_score" in first_action
    assert "evidence_quality" in first_action
    assert "rationale" in first_action
    assert "supporting_data" in first_action
    assert "recommended_steps" in first_action
    assert "risks" in first_action
    assert "success_metrics" in first_action
    assert "limitations" in first_action
    assert first_action["status"] == "open"

    # Verify DB columns
    db_action = db_session.query(BusinessAction).filter(BusinessAction.id == first_action["id"]).first()
    assert db_action is not None
    assert db_action.rule_label == first_action["rule_label"]
    assert db_action.ai_generated is True


def test_generate_actions_ai_failure_propagates_error(client, auth_user, db_session):
    auth_headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, b1, b2, p1, p2, p3 = _setup_test_environment(client, auth_headers)
    _populate_business_data(db_session, biz_id, user_id, b1, b2, p1, p2, p3)

    with patch(
        "app.services.action_narrative_generator.chat_completion",
        side_effect=AIServiceException(status_code=502, message="AI gateway unavailable"),
    ):
        resp = client.post(
            f"/api/v1/businesses/{biz_id}/business-actions/generate",
            json={"lookback_days": 30, "persist": True},
            headers=auth_headers,
        )
        assert resp.status_code == 502
        body = resp.json()
        assert "error" in body or "message" in body


def test_generate_actions_ephemeral(client, auth_user, db_session):
    auth_headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, b1, b2, p1, p2, p3 = _setup_test_environment(client, auth_headers)
    _populate_business_data(db_session, biz_id, user_id, b1, b2, p1, p2, p3)

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/business-actions/generate",
        json={"lookback_days": 30, "persist": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["generated_count"] > 0
    assert data["persisted_count"] == 0

    # Verify nothing was saved to DB
    count_in_db = db_session.query(BusinessAction).filter(BusinessAction.business_id == biz_id).count()
    assert count_in_db == 0


def test_deduplication_on_regenerate(client, auth_user, db_session):
    auth_headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, b1, b2, p1, p2, p3 = _setup_test_environment(client, auth_headers)
    _populate_business_data(db_session, biz_id, user_id, b1, b2, p1, p2, p3)

    resp1 = client.post(
        f"/api/v1/businesses/{biz_id}/business-actions/generate",
        json={"lookback_days": 30, "persist": True},
        headers=auth_headers,
    )
    count1 = resp1.json()["data"]["persisted_count"]
    db_count1 = db_session.query(BusinessAction).filter(BusinessAction.business_id == biz_id).count()
    assert count1 == db_count1

    # Regenerate again
    resp2 = client.post(
        f"/api/v1/businesses/{biz_id}/business-actions/generate",
        json={"lookback_days": 30, "persist": True},
        headers=auth_headers,
    )
    count2 = resp2.json()["data"]["persisted_count"]
    db_count2 = db_session.query(BusinessAction).filter(BusinessAction.business_id == biz_id).count()
    # Deduplication ensures rows are updated, not duplicated
    assert db_count2 == db_count1


def test_list_and_filter_actions(client, auth_user, db_session):
    auth_headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, b1, b2, p1, p2, p3 = _setup_test_environment(client, auth_headers)
    _populate_business_data(db_session, biz_id, user_id, b1, b2, p1, p2, p3)

    # Generate first
    client.post(
        f"/api/v1/businesses/{biz_id}/business-actions/generate",
        json={"lookback_days": 30, "persist": True},
        headers=auth_headers,
    )

    # 1. Basic list
    list_resp = client.get(
        f"/api/v1/businesses/{biz_id}/business-actions",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert "pagination" in body["data"]
    assert body["data"]["pagination"]["page"] == 1
    assert len(body["data"]["actions"]) > 0

    # 2. Filter by category=inventory
    cat_resp = client.get(
        f"/api/v1/businesses/{biz_id}/business-actions?category=inventory",
        headers=auth_headers,
    )
    assert cat_resp.status_code == 200
    for item in cat_resp.json()["data"]["actions"]:
        assert item["category"] == "inventory"

    # 3. Filter by urgency=critical
    urg_resp = client.get(
        f"/api/v1/businesses/{biz_id}/business-actions?urgency=critical",
        headers=auth_headers,
    )
    assert urg_resp.status_code == 200
    for item in urg_resp.json()["data"]["actions"]:
        assert item["urgency"] == "critical"

    # 4. Filter by status=open
    st_resp = client.get(
        f"/api/v1/businesses/{biz_id}/business-actions?status=open",
        headers=auth_headers,
    )
    assert st_resp.status_code == 200
    for item in st_resp.json()["data"]["actions"]:
        assert item["status"] == "open"

    # 5. Filter by min_priority
    prio_resp = client.get(
        f"/api/v1/businesses/{biz_id}/business-actions?min_priority=70.0",
        headers=auth_headers,
    )
    assert prio_resp.status_code == 200
    for item in prio_resp.json()["data"]["actions"]:
        assert float(item["priority_score"]) >= 70.0


def test_get_action_detail_and_not_found(client, auth_user, db_session):
    auth_headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, b1, b2, p1, p2, p3 = _setup_test_environment(client, auth_headers)
    _populate_business_data(db_session, biz_id, user_id, b1, b2, p1, p2, p3)

    gen_resp = client.post(
        f"/api/v1/businesses/{biz_id}/business-actions/generate",
        json={"persist": True},
        headers=auth_headers,
    )
    action_id = gen_resp.json()["data"]["actions"][0]["id"]

    # Valid get
    get_resp = client.get(
        f"/api/v1/businesses/{biz_id}/business-actions/{action_id}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["action"]["id"] == action_id

    # Not found
    not_found_resp = client.get(
        f"/api/v1/businesses/{biz_id}/business-actions/99999",
        headers=auth_headers,
    )
    assert not_found_resp.status_code == 404
    assert "action_id" in not_found_resp.json()["error"] or "action" in not_found_resp.json()["message"]["error"].lower()


def test_status_transitions_lifecycle(client, auth_user, db_session):
    auth_headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, b1, b2, p1, p2, p3 = _setup_test_environment(client, auth_headers)
    _populate_business_data(db_session, biz_id, user_id, b1, b2, p1, p2, p3)

    gen_resp = client.post(
        f"/api/v1/businesses/{biz_id}/business-actions/generate",
        json={"persist": True},
        headers=auth_headers,
    )
    action_id = gen_resp.json()["data"]["actions"][0]["id"]

    # 1. open -> in_progress (valid)
    p1_resp = client.patch(
        f"/api/v1/businesses/{biz_id}/business-actions/{action_id}/status",
        json={"status": "in_progress"},
        headers=auth_headers,
    )
    assert p1_resp.status_code == 200
    assert p1_resp.json()["data"]["action"]["status"] == "in_progress"

    # 2. in_progress -> implemented (valid)
    p2_resp = client.patch(
        f"/api/v1/businesses/{biz_id}/business-actions/{action_id}/status",
        json={"status": "implemented"},
        headers=auth_headers,
    )
    assert p2_resp.status_code == 200
    assert p2_resp.json()["data"]["action"]["status"] == "implemented"

    # 3. implemented -> archived (valid)
    p3_resp = client.patch(
        f"/api/v1/businesses/{biz_id}/business-actions/{action_id}/status",
        json={"status": "archived"},
        headers=auth_headers,
    )
    assert p3_resp.status_code == 200
    assert p3_resp.json()["data"]["action"]["status"] == "archived"

    # 4. archived -> in_progress (invalid terminal transition)
    err_resp = client.patch(
        f"/api/v1/businesses/{biz_id}/business-actions/{action_id}/status",
        json={"status": "in_progress"},
        headers=auth_headers,
    )
    assert err_resp.status_code == 400
    assert "status" in err_resp.json()["error"] or "transition" in err_resp.json()["message"]["error"].lower()


def test_dismiss_action_requires_reason(client, auth_user, db_session):
    auth_headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, b1, b2, p1, p2, p3 = _setup_test_environment(client, auth_headers)
    _populate_business_data(db_session, biz_id, user_id, b1, b2, p1, p2, p3)

    gen_resp = client.post(
        f"/api/v1/businesses/{biz_id}/business-actions/generate",
        json={"persist": True},
        headers=auth_headers,
    )
    action_id = gen_resp.json()["data"]["actions"][0]["id"]

    # Attempt dismiss without reason -> 400
    fail_resp = client.patch(
        f"/api/v1/businesses/{biz_id}/business-actions/{action_id}/status",
        json={"status": "dismissed"},
        headers=auth_headers,
    )
    assert fail_resp.status_code == 400
    assert "dismissed_reason" in fail_resp.json()["error"] or "reason" in fail_resp.json()["message"]["error"].lower()

    # Dismiss with reason -> 200
    ok_resp = client.patch(
        f"/api/v1/businesses/{biz_id}/business-actions/{action_id}/status",
        json={"status": "dismissed", "dismissed_reason": "Kitchen manager already addressed this."},
        headers=auth_headers,
    )
    assert ok_resp.status_code == 200
    assert ok_resp.json()["data"]["action"]["status"] == "dismissed"
    assert ok_resp.json()["data"]["action"]["dismissed_reason"] == "Kitchen manager already addressed this."


def test_direct_endpoints(client, auth_user, db_session):
    auth_headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, b1, b2, p1, p2, p3 = _setup_test_environment(client, auth_headers)
    _populate_business_data(db_session, biz_id, user_id, b1, b2, p1, p2, p3)

    # Direct generate
    gen_resp = client.post(
        "/api/v1/business-actions/generate",
        json={"business_id": biz_id, "persist": True},
        headers=auth_headers,
    )
    assert gen_resp.status_code == 200
    action_id = gen_resp.json()["data"]["actions"][0]["id"]

    # Direct list
    list_resp = client.get(
        f"/api/v1/business-actions?business_id={biz_id}",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200

    # Direct get
    get_resp = client.get(
        f"/api/v1/business-actions/{action_id}?business_id={biz_id}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 200

    # Direct status update
    upd_resp = client.patch(
        f"/api/v1/business-actions/{action_id}/status?business_id={biz_id}",
        json={"status": "in_progress"},
        headers=auth_headers,
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["data"]["action"]["status"] == "in_progress"


def test_business_scoped_authorization(client, auth_user, second_user, db_session):
    auth_headers1 = auth_user["headers"]
    auth_headers2 = second_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, b1, b2, p1, p2, p3 = _setup_test_environment(client, auth_headers1)
    _populate_business_data(db_session, biz_id, user_id, b1, b2, p1, p2, p3)

    # Second user is NOT a member of biz_id -> 403 Forbidden
    resp = client.get(
        f"/api/v1/businesses/{biz_id}/business-actions",
        headers=auth_headers2,
    )
    assert resp.status_code == 403


def test_role_based_permissions(client, auth_user, second_user, db_session):
    auth_headers1 = auth_user["headers"]
    auth_headers2 = second_user["headers"]
    user_id1 = auth_user["user"]["id"]
    user_id2 = second_user["user"]["id"]
    biz_id, b1, b2, p1, p2, p3 = _setup_test_environment(client, auth_headers1)
    _populate_business_data(db_session, biz_id, user_id1, b1, b2, p1, p2, p3)

    # Add second user as 'staff' (read-only for recommendations)
    db_session.add(
        BusinessMembership(
            business_id=biz_id,
            user_id=user_id2,
            role="staff",
        )
    )
    db_session.commit()

    # Generate first using owner
    gen_resp = client.post(
        f"/api/v1/businesses/{biz_id}/business-actions/generate",
        json={"persist": True},
        headers=auth_headers1,
    )
    action_id = gen_resp.json()["data"]["actions"][0]["id"]

    # Staff can view/list
    view_resp = client.get(
        f"/api/v1/businesses/{biz_id}/business-actions",
        headers=auth_headers2,
    )
    assert view_resp.status_code == 200

    # Staff CANNOT generate -> 403
    staff_gen = client.post(
        f"/api/v1/businesses/{biz_id}/business-actions/generate",
        json={"persist": True},
        headers=auth_headers2,
    )
    assert staff_gen.status_code == 403

    # Staff CANNOT update status -> 403
    staff_upd = client.patch(
        f"/api/v1/businesses/{biz_id}/business-actions/{action_id}/status",
        json={"status": "in_progress"},
        headers=auth_headers2,
    )
    assert staff_upd.status_code == 403


def test_empty_business_data(client, auth_user):
    auth_headers = auth_user["headers"]
    # New empty business
    biz_resp = client.post(
        "/api/v1/businesses", json={"name": "Empty Business"}, headers=auth_headers
    )
    biz_id = biz_resp.json()["data"]["business"]["id"]

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/business-actions/generate",
        json={"persist": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["generated_count"] == 0
    assert data["persisted_count"] == 0
    assert data["actions"] == []


def test_agent_tool_invoke_action_center(client, auth_user, db_session):
    auth_headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, b1, b2, p1, p2, p3 = _setup_test_environment(client, auth_headers)
    _populate_business_data(db_session, biz_id, user_id, b1, b2, p1, p2, p3)

    tool_result = execute_tool_by_name(
        "invoke_action_center",
        {"lookback_days": 30},
        db=db_session,
        business_id=biz_id,
    )
    assert "error" not in tool_result or tool_result.get("error") is None
    assert "top_recommendations" in tool_result["data"]
    assert tool_result["data"]["status"] == "success"
    assert tool_result["data"]["generated_count"] > 0
