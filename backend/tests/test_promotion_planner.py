from datetime import date, timedelta
from decimal import Decimal
import json
from unittest.mock import patch
import pytest
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.branch import Branch
from app.models.product import Product
from app.models.product_price_history import ProductPriceHistory
from app.models.product_cost_history import ProductCostHistory
from app.models.promotion_plan import PromotionPlan
from app.models.business_membership import BusinessMembership
from app.agent.tools import execute_invoke_promotion_planner, execute_tool_by_name
from app.helpers.error_codes import ErrorCodeRegistry


@pytest.fixture(autouse=True)
def mock_promotion_narrative_ai():
    """Mock LLM calls in integration tests so tests are fast, deterministic, and offline."""
    async def _mock_completion(messages, **kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "title": "Weekend Feast Special Promotion",
                            "rationale": "High-margin promotional combo targeting family dining segments.",
                            "recommended_actions": [
                                "Brief front-of-house staff on the combo upsell",
                                "Update digital menu boards and POS pricing",
                                "Prepare kitchen prep stations for higher volume",
                            ],
                            "risks": [
                                "Potential rush-hour kitchen bottleneck",
                                "Minor margin dilution if upsell fails",
                            ],
                        })
                    }
                }
            ]
        }

    with patch("app.services.promotion_narrative_generator.chat_completion", side_effect=_mock_completion) as mock_ai:
        yield mock_ai


def _setup_test_business(client, auth_headers):
    """Create a business, branch, and two products."""
    biz_resp = client.post(
        "/api/v1/businesses", json={"name": "Promo Test Bistro"}, headers=auth_headers
    )
    assert biz_resp.status_code == 201
    biz_id = biz_resp.json()["data"]["business"]["id"]

    branch_resp = client.post(
        f"/api/v1/businesses/{biz_id}/branches", json={"name": "Downtown"}, headers=auth_headers
    )
    branch_id = branch_resp.json()["data"]["branch"]["id"]

    p1 = client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Chicken Gyros", "category": "Mains", "base_unit": "portion"},
        headers=auth_headers,
    )
    prod_id1 = p1.json()["data"]["product"]["id"]

    p2 = client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Iced Lemon Tea", "category": "Beverages", "base_unit": "glass"},
        headers=auth_headers,
    )
    prod_id2 = p2.json()["data"]["product"]["id"]

    return biz_id, branch_id, prod_id1, prod_id2


def _seed_prices_and_costs(db: Session, biz_id: int, prod_id1: int, prod_id2: int, with_p2_cost: bool = True):
    today = date.today()
    p1_price = ProductPriceHistory(
        business_id=biz_id,
        product_id=prod_id1,
        effective_from=today - timedelta(days=10),
        selling_price=Decimal("40000.00"),
        price_unit="portion",
    )
    p1_cost = ProductCostHistory(
        business_id=biz_id,
        product_id=prod_id1,
        effective_from=today - timedelta(days=10),
        unit_cost=Decimal("20000.00"),
        cost_unit="portion",
    )

    p2_price = ProductPriceHistory(
        business_id=biz_id,
        product_id=prod_id2,
        effective_from=today - timedelta(days=10),
        selling_price=Decimal("15000.00"),
        price_unit="glass",
    )

    db.add_all([p1_price, p1_cost, p2_price])
    if with_p2_cost:
        p2_cost = ProductCostHistory(
            business_id=biz_id,
            product_id=prod_id2,
            effective_from=today - timedelta(days=10),
            unit_cost=Decimal("5000.00"),
            cost_unit="glass",
        )
        db.add(p2_cost)
    db.commit()


# ---------------------------------------------------------
# Integration Tests — API Endpoints & Financial Calculations
# ---------------------------------------------------------

def test_generate_plan_with_valid_data(client, auth_user, db_session):
    biz_id, branch_id, prod_id1, prod_id2 = _setup_test_business(client, auth_user["headers"])
    _seed_prices_and_costs(db_session, biz_id, prod_id1, prod_id2, with_p2_cost=True)

    today = date.today()
    payload = {
        "promotion_type": "discount",
        "start_date": str(today + timedelta(days=1)),
        "end_date": str(today + timedelta(days=7)),
        "branch_id": branch_id,
        "items": [
            {
                "product_id": prod_id1,
                "discount_type": "percentage",
                "discount_value": 20.0,
                "expected_qty": 100,
            },
            {
                "product_id": prod_id2,
                "discount_type": "fixed_amount",
                "discount_value": 3000.0,
                "expected_qty": 50,
            },
        ],
        "min_margin_pct": 15.0,
        "persist": True,
    }

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/promotions/generate",
        json=payload,
        headers=auth_user["headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    plan = data["plan"]

    assert plan["business_id"] == biz_id
    assert plan["status"] == "draft"
    assert plan["title"] == "Weekend Feast Special Promotion"
    assert plan["is_financially_validated"] is True
    assert len(plan["items"]) == 2

    # Prod 1: orig 40000 -> 20% off = 32000, cost 20000, margin 12000 (37.5%), contrib = 1200000
    it1 = next(it for it in plan["items"] if it["product_id"] == prod_id1)
    assert Decimal(str(it1["original_price"])) == Decimal("40000.00")
    assert Decimal(str(it1["discounted_price"])) == Decimal("32000.00")
    assert Decimal(str(it1["unit_cost"])) == Decimal("20000.00")
    assert Decimal(str(it1["margin_per_unit"])) == Decimal("12000.00")
    assert Decimal(str(it1["margin_pct"])) == Decimal("37.50")
    assert Decimal(str(it1["estimated_contribution"])) == Decimal("1200000.00")

    # Prod 2: orig 15000 -> 3000 off = 12000, cost 5000, margin 7000 (58.33%), contrib = 350000
    it2 = next(it for it in plan["items"] if it["product_id"] == prod_id2)
    assert Decimal(str(it2["original_price"])) == Decimal("15000.00")
    assert Decimal(str(it2["discounted_price"])) == Decimal("12000.00")
    assert Decimal(str(it2["unit_cost"])) == Decimal("5000.00")
    assert Decimal(str(it2["margin_per_unit"])) == Decimal("7000.00")
    assert Decimal(str(it2["margin_pct"])) == Decimal("58.33")
    assert Decimal(str(it2["estimated_contribution"])) == Decimal("350000.00")

    # Check persistence in DB
    db_plan = db_session.query(PromotionPlan).filter(PromotionPlan.id == plan["id"]).first()
    assert db_plan is not None
    assert db_plan.status == "draft"


def test_generate_plan_missing_cost_data(client, auth_user, db_session):
    biz_id, branch_id, prod_id1, prod_id2 = _setup_test_business(client, auth_user["headers"])
    # Seed prod_id2 WITHOUT cost
    _seed_prices_and_costs(db_session, biz_id, prod_id1, prod_id2, with_p2_cost=False)

    today = date.today()
    payload = {
        "promotion_type": "discount",
        "start_date": str(today + timedelta(days=1)),
        "end_date": str(today + timedelta(days=7)),
        "items": [
            {
                "product_id": prod_id1,
                "discount_type": "percentage",
                "discount_value": 20.0,
                "expected_qty": 50,
            },
            {
                "product_id": prod_id2,
                "discount_type": "percentage",
                "discount_value": 10.0,
                "expected_qty": 50,
            },
        ],
        "persist": True,
    }

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/promotions/generate",
        json=payload,
        headers=auth_user["headers"],
    )
    assert resp.status_code == 200
    plan = resp.json()["data"]["plan"]
    assert plan["is_financially_validated"] is False
    assert len(plan["missing_data"]) >= 1
    assert any("Unit cost for product" in m for m in plan["missing_data"])


def test_generate_plan_persist_false(client, auth_user, db_session):
    biz_id, branch_id, prod_id1, prod_id2 = _setup_test_business(client, auth_user["headers"])
    _seed_prices_and_costs(db_session, biz_id, prod_id1, prod_id2)

    today = date.today()
    payload = {
        "promotion_type": "discount",
        "start_date": str(today + timedelta(days=1)),
        "end_date": str(today + timedelta(days=7)),
        "items": [
            {
                "product_id": prod_id1,
                "discount_type": "percentage",
                "discount_value": 15.0,
            }
        ],
        "persist": False,
    }

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/promotions/generate",
        json=payload,
        headers=auth_user["headers"],
    )
    assert resp.status_code == 200
    plan = resp.json()["data"]["plan"]
    assert plan["id"] == 0

    count = db_session.query(PromotionPlan).filter(PromotionPlan.business_id == biz_id).count()
    assert count == 0


def test_list_plans_pagination_and_filter(client, auth_user, db_session):
    biz_id, branch_id, prod_id1, prod_id2 = _setup_test_business(client, auth_user["headers"])
    _seed_prices_and_costs(db_session, biz_id, prod_id1, prod_id2)

    today = date.today()
    # Generate 3 plans
    for i in range(3):
        client.post(
            f"/api/v1/businesses/{biz_id}/promotions/generate",
            json={
                "promotion_type": "discount" if i < 2 else "bundle",
                "start_date": str(today + timedelta(days=1 + i)),
                "end_date": str(today + timedelta(days=8 + i)),
                "items": [{"product_id": prod_id1, "discount_type": "percentage", "discount_value": 10.0}],
                "persist": True,
            },
            headers=auth_user["headers"],
        )

    # List page 1 with page_size=2
    resp = client.get(
        f"/api/v1/businesses/{biz_id}/promotions?page=1&page_size=2",
        headers=auth_user["headers"],
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert len(res_data["data"]["plans"]) == 2
    assert res_data["data"]["pagination"]["total"] == 3
    assert res_data["data"]["pagination"]["total_pages"] == 2


    # Filter by promotion_type=bundle
    resp_filter = client.get(
        f"/api/v1/businesses/{biz_id}/promotions?promotion_type=bundle",
        headers=auth_user["headers"],
    )
    assert resp_filter.status_code == 200
    assert len(resp_filter.json()["data"]["plans"]) == 1


def test_get_plan_detail_and_isolation(client, auth_user, second_user, db_session):
    biz_id, branch_id, prod_id1, prod_id2 = _setup_test_business(client, auth_user["headers"])
    _seed_prices_and_costs(db_session, biz_id, prod_id1, prod_id2)

    today = date.today()
    gen_resp = client.post(
        f"/api/v1/businesses/{biz_id}/promotions/generate",
        json={
            "promotion_type": "discount",
            "start_date": str(today + timedelta(days=1)),
            "end_date": str(today + timedelta(days=7)),
            "items": [{"product_id": prod_id1, "discount_type": "percentage", "discount_value": 15.0}],
            "persist": True,
        },
        headers=auth_user["headers"],
    )
    plan_id = gen_resp.json()["data"]["plan"]["id"]

    # Detail by owner
    detail_resp = client.get(
        f"/api/v1/businesses/{biz_id}/promotions/{plan_id}",
        headers=auth_user["headers"],
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["data"]["plan"]["id"] == plan_id

    # Create second business for second_user
    biz2_resp = client.post(
        "/api/v1/businesses", json={"name": "Second Biz"}, headers=second_user["headers"]
    )
    biz2_id = biz2_resp.json()["data"]["business"]["id"]

    # Attempt to access plan_id through biz2_id -> 404
    wrong_biz_resp = client.get(
        f"/api/v1/businesses/{biz2_id}/promotions/{plan_id}",
        headers=second_user["headers"],
    )
    assert wrong_biz_resp.status_code == 404


def test_status_transitions(client, auth_user, db_session):
    biz_id, branch_id, prod_id1, prod_id2 = _setup_test_business(client, auth_user["headers"])
    _seed_prices_and_costs(db_session, biz_id, prod_id1, prod_id2)

    today = date.today()
    gen_resp = client.post(
        f"/api/v1/businesses/{biz_id}/promotions/generate",
        json={
            "promotion_type": "discount",
            "start_date": str(today + timedelta(days=1)),
            "end_date": str(today + timedelta(days=7)),
            "items": [{"product_id": prod_id1, "discount_type": "percentage", "discount_value": 15.0}],
            "persist": True,
        },
        headers=auth_user["headers"],
    )
    plan_id = gen_resp.json()["data"]["plan"]["id"]

    # Reject without reason -> 422
    rej_fail = client.patch(
        f"/api/v1/businesses/{biz_id}/promotions/{plan_id}/status",
        json={"status": "rejected"},
        headers=auth_user["headers"],
    )
    assert rej_fail.status_code == 422

    # Reject with reason -> 200
    rej_ok = client.patch(
        f"/api/v1/businesses/{biz_id}/promotions/{plan_id}/status",
        json={"status": "rejected", "rejected_reason": "Margin too thin for current season"},
        headers=auth_user["headers"],
    )
    assert rej_ok.status_code == 200
    assert rej_ok.json()["data"]["plan"]["status"] == "rejected"
    assert rej_ok.json()["data"]["plan"]["rejected_reason"] == "Margin too thin for current season"

    # Reopen rejected -> draft -> 200
    reopen = client.patch(
        f"/api/v1/businesses/{biz_id}/promotions/{plan_id}/status",
        json={"status": "draft"},
        headers=auth_user["headers"],
    )
    assert reopen.status_code == 200
    assert reopen.json()["data"]["plan"]["status"] == "draft"

    # Approve draft -> 200
    appr = client.patch(
        f"/api/v1/businesses/{biz_id}/promotions/{plan_id}/status",
        json={"status": "approved"},
        headers=auth_user["headers"],
    )
    assert appr.status_code == 200
    assert appr.json()["data"]["plan"]["status"] == "approved"
    assert appr.json()["data"]["plan"]["approved_at"] is not None

    # Invalid transition: approved -> draft -> 422
    inv = client.patch(
        f"/api/v1/businesses/{biz_id}/promotions/{plan_id}/status",
        json={"status": "draft"},
        headers=auth_user["headers"],
    )
    assert inv.status_code == 422

    # Archive approved -> 200
    arch = client.patch(
        f"/api/v1/businesses/{biz_id}/promotions/{plan_id}/status",
        json={"status": "archived"},
        headers=auth_user["headers"],
    )
    assert arch.status_code == 200
    assert arch.json()["data"]["plan"]["status"] == "archived"


def test_evaluate_existing_plan(client, auth_user, db_session):
    biz_id, branch_id, prod_id1, prod_id2 = _setup_test_business(client, auth_user["headers"])
    _seed_prices_and_costs(db_session, biz_id, prod_id1, prod_id2)

    today = date.today()
    gen_resp = client.post(
        f"/api/v1/businesses/{biz_id}/promotions/generate",
        json={
            "promotion_type": "discount",
            "start_date": str(today + timedelta(days=1)),
            "end_date": str(today + timedelta(days=7)),
            "items": [
                {
                    "product_id": prod_id1,
                    "discount_type": "percentage",
                    "discount_value": 20.0,
                    "expected_qty": 10,
                }
            ],
            "persist": True,
        },
        headers=auth_user["headers"],
    )
    plan_id = gen_resp.json()["data"]["plan"]["id"]

    # Now add a new lower unit cost
    new_cost = ProductCostHistory(
        business_id=biz_id,
        product_id=prod_id1,
        effective_from=today,
        unit_cost=Decimal("15000.00"),  # reduced from 20000 to 15000
        cost_unit="portion",
    )
    db_session.add(new_cost)
    db_session.commit()

    # Call evaluate endpoint
    eval_resp = client.post(
        f"/api/v1/businesses/{biz_id}/promotions/{plan_id}/evaluate",
        json={},
        headers=auth_user["headers"],
    )
    assert eval_resp.status_code == 200
    eval_plan = eval_resp.json()["data"]["plan"]
    # With selling price 40000, 20% discount = 32000. Unit cost now 15000 -> margin = 17000
    it = eval_plan["items"][0]
    assert Decimal(str(it["unit_cost"])) == Decimal("15000.00")
    assert Decimal(str(it["margin_per_unit"])) == Decimal("17000.00")


def test_direct_router_endpoints(client, auth_user, db_session):
    biz_id, branch_id, prod_id1, prod_id2 = _setup_test_business(client, auth_user["headers"])
    _seed_prices_and_costs(db_session, biz_id, prod_id1, prod_id2)

    today = date.today()
    # POST /api/v1/promotions/generate
    direct_gen = client.post(
        "/api/v1/promotions/generate",
        json={
            "business_id": biz_id,
            "promotion_type": "discount",
            "start_date": str(today + timedelta(days=1)),
            "end_date": str(today + timedelta(days=5)),
            "items": [{"product_id": prod_id1, "discount_type": "percentage", "discount_value": 10.0}],
            "persist": True,
        },
        headers=auth_user["headers"],
    )
    assert direct_gen.status_code == 200
    plan_id = direct_gen.json()["data"]["plan"]["id"]

    # GET /api/v1/promotions?business_id=...
    direct_list = client.get(
        f"/api/v1/promotions?business_id={biz_id}",
        headers=auth_user["headers"],
    )
    assert direct_list.status_code == 200
    assert len(direct_list.json()["data"]["plans"]) >= 1

    # GET /api/v1/promotions/{plan_id}?business_id=...
    direct_get = client.get(
        f"/api/v1/promotions/{plan_id}?business_id={biz_id}",
        headers=auth_user["headers"],
    )
    assert direct_get.status_code == 200


# ---------------------------------------------------------
# Authorization Tests
# ---------------------------------------------------------

def test_role_authorization_and_membership(client, auth_user, second_user, db_session):
    biz_id, branch_id, prod_id1, prod_id2 = _setup_test_business(client, auth_user["headers"])
    _seed_prices_and_costs(db_session, biz_id, prod_id1, prod_id2)

    # Add second_user as viewer in biz_id
    second_user_id = second_user["user"]["id"]
    membership = BusinessMembership(
        business_id=biz_id,
        user_id=second_user_id,
        role="viewer",
    )
    db_session.add(membership)
    db_session.commit()

    today = date.today()
    # Viewer generates -> 403
    viewer_gen = client.post(
        f"/api/v1/businesses/{biz_id}/promotions/generate",
        json={
            "promotion_type": "discount",
            "start_date": str(today + timedelta(days=1)),
            "end_date": str(today + timedelta(days=5)),
            "items": [{"product_id": prod_id1, "discount_type": "percentage", "discount_value": 10.0}],
        },
        headers=second_user["headers"],
    )
    assert viewer_gen.status_code == 403

    # Viewer lists -> 200
    viewer_list = client.get(
        f"/api/v1/businesses/{biz_id}/promotions",
        headers=second_user["headers"],
    )
    assert viewer_list.status_code == 200

    # Unauthenticated -> 401
    unauth = client.get(f"/api/v1/businesses/{biz_id}/promotions")
    assert unauth.status_code == 401


# ---------------------------------------------------------
# Agent Tool Integration Tests
# ---------------------------------------------------------

def test_agent_tool_generate_plan(client, auth_user, db_session):
    biz_id, branch_id, prod_id1, prod_id2 = _setup_test_business(client, auth_user["headers"])
    _seed_prices_and_costs(db_session, biz_id, prod_id1, prod_id2)

    res = execute_invoke_promotion_planner(
        business_id=biz_id,
        db=db_session,
        action="generate",
        promotion_type="discount",
        product_ids=[prod_id1, prod_id2],
        discount_pct=15.0,
        persist=False,
    )
    assert "Generated promotion plan" in res["summary"]
    assert res["data"]["status"] == "success"
    assert res["data"]["plan"]["id"] == 0  # not persisted
    assert len(res["data"]["plan"]["items"]) == 2


def test_agent_tool_missing_db():
    res = execute_invoke_promotion_planner(business_id=1, db=None)
    assert res["data"]["status"] == "not_available"


def test_agent_tool_dispatch_by_name(client, auth_user, db_session):
    biz_id, branch_id, prod_id1, prod_id2 = _setup_test_business(client, auth_user["headers"])
    _seed_prices_and_costs(db_session, biz_id, prod_id1, prod_id2)

    res = execute_tool_by_name(
        "invoke_promotion_planner",
        {"business_id": biz_id, "action": "generate", "product_ids": [prod_id1]},
        business_id=biz_id,
        db=db_session,
    )
    assert res["data"]["status"] == "success"
