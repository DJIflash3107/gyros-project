from datetime import date, timedelta
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.branch import Branch
from app.models.product import Product
from app.models.business_membership import BusinessMembership
from app.models.sales_report_submission import SalesReportSubmission
from app.models.sales_report_observation import SalesReportObservation
from app.models.forecast_run import ForecastRun
from app.models.forecast_result import ForecastResult
from app.agent.tools import execute_tool_by_name


def _setup_forecasting_data(client, auth_headers):
    """Sets up a test business, branch, and product via the API."""
    biz_resp = client.post("/api/v1/businesses", json={"name": "Forecasting Cafe"}, headers=auth_headers)
    assert biz_resp.status_code == 201
    biz_id = biz_resp.json()["data"]["business"]["id"]

    branch_resp = client.post(f"/api/v1/businesses/{biz_id}/branches", json={"name": "Downtown"}, headers=auth_headers)
    assert branch_resp.status_code == 201
    branch_id = branch_resp.json()["data"]["branch"]["id"]

    prod_resp = client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Chicken Gyros", "base_unit": "portion"},
        headers=auth_headers,
    )
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["data"]["product"]["id"]

    return biz_id, branch_id, prod_id


def _insert_observations(
    db: Session,
    biz_id: int,
    user_id: int,
    branch_id: int,
    prod_id: int,
    quantities: list[float],
    start_date: date = date(2026, 1, 1),
    granularity: str = "daily",
):
    """Creates a submission and corresponding observations directly in the test database."""
    coverage_end = start_date + timedelta(days=len(quantities) - 1)
    submission = SalesReportSubmission(
        business_id=biz_id,
        submitted_by_user_id=user_id,
        branch_id=branch_id,
        input_method="manual",
        report_period_type="daily",
        coverage_start=start_date,
        coverage_end=coverage_end,
        status="confirmed",
    )
    db.add(submission)
    db.flush()

    for i, qty in enumerate(quantities):
        obs_date = start_date + timedelta(days=i)
        obs = SalesReportObservation(
            business_id=biz_id,
            branch_id=branch_id,
            product_id=prod_id,
            source_submission_id=submission.id,
            period_start=obs_date,
            period_end=obs_date,
            granularity=granularity,
            sold_qty=Decimal(f"{qty:.3f}"),
            record_status="active",
        )
        db.add(obs)
    db.commit()


def test_predict_success(client, auth_user, db_session):
    """End-to-end forecast generation with sufficient daily observations (>=14)."""
    headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, branch_id, prod_id = _setup_forecasting_data(client, headers)

    # Insert 20 days of sales (15.0 per day)
    _insert_observations(db_session, biz_id, user_id, branch_id, prod_id, [15.0] * 20)

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/forecasting/predict",
        json={"branch_id": branch_id, "product_id": prod_id, "horizon_days": 7, "window_size": 7},
        headers=headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["message"]["success"] == "Forecast generated successfully"

    run = res_data["data"]["forecast_run"]
    assert run["is_reliable"] is True
    assert run["method"] == "moving_average"
    assert run["observations_used"] == 20
    assert len(run["predictions"]) == 7
    for pt in run["predictions"]:
        assert Decimal(pt["predicted_qty"]) == Decimal("15.000")

    # Verify persistence in database
    db_run = db_session.query(ForecastRun).filter(ForecastRun.id == run["id"]).first()
    assert db_run is not None
    assert len(db_run.predictions) == 7


def test_predict_insufficient_data(client, auth_user, db_session):
    """Fewer than 14 daily observations returns is_reliable=False with clear note and empty predictions."""
    headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, branch_id, prod_id = _setup_forecasting_data(client, headers)

    # Insert only 6 observations
    _insert_observations(db_session, biz_id, user_id, branch_id, prod_id, [10.0] * 6)

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/forecasting/predict",
        json={"branch_id": branch_id, "product_id": prod_id, "horizon_days": 7, "window_size": 7},
        headers=headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert "reliability warning" in res_data["message"]["success"]

    run = res_data["data"]["forecast_run"]
    assert run["is_reliable"] is False
    assert run["method"] == "none"
    assert "Insufficient daily observations" in run["reliability_note"]
    assert len(run["predictions"]) == 0


def test_predict_unauthenticated(client, auth_user):
    """Calling predict without authorization token returns 401."""
    resp = client.post(
        "/api/v1/businesses/1/forecasting/predict",
        json={"branch_id": 1, "product_id": 1},
    )
    assert resp.status_code == 401


def test_predict_unauthorized_role(client, auth_user, second_user, db_session):
    """Member with viewer-only role receives 403 on forecast generation."""
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id = _setup_forecasting_data(client, headers)

    # Add second user as 'viewer'
    sec_user_id = second_user["user"]["id"]
    membership = BusinessMembership(business_id=biz_id, user_id=sec_user_id, role="viewer")
    db_session.add(membership)
    db_session.commit()

    sec_headers = second_user["headers"]
    resp = client.post(
        f"/api/v1/businesses/{biz_id}/forecasting/predict",
        json={"branch_id": branch_id, "product_id": prod_id},
        headers=sec_headers,
    )
    assert resp.status_code == 403


def test_predict_nonexistent_branch(client, auth_user):
    """Referencing nonexistent branch returns 404 with error code."""
    headers = auth_user["headers"]
    biz_id, _, prod_id = _setup_forecasting_data(client, headers)

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/forecasting/predict",
        json={"branch_id": 99999, "product_id": prod_id},
        headers=headers,
    )
    assert resp.status_code == 404
    body = resp.json()
    assert "branch_id" in body["error"] or "branch" in body["message"]["error"].lower()


def test_predict_nonexistent_product(client, auth_user):
    """Referencing nonexistent product returns 404 with error code."""
    headers = auth_user["headers"]
    biz_id, branch_id, _ = _setup_forecasting_data(client, headers)

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/forecasting/predict",
        json={"branch_id": branch_id, "product_id": 99999},
        headers=headers,
    )
    assert resp.status_code == 404
    body = resp.json()
    assert "product_id" in body["error"] or "product" in body["message"]["error"].lower()


def test_evaluate_success(client, auth_user, db_session):
    """Backtesting evaluation computes MAE, WAPE, and forecast bias."""
    headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, branch_id, prod_id = _setup_forecasting_data(client, headers)

    # Insert 21 days: 14 training days of 10.0 + 7 test days of 12.0
    values = [10.0] * 14 + [12.0] * 7
    _insert_observations(db_session, biz_id, user_id, branch_id, prod_id, values)

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/forecasting/evaluate",
        json={"branch_id": branch_id, "product_id": prod_id, "window_size": 7, "test_days": 7},
        headers=headers,
    )
    assert resp.status_code == 200
    ev = resp.json()["data"]["evaluation"]

    assert ev["is_reliable"] is True
    assert ev["observations_used"] == 14
    assert ev["test_days"] == 7
    # Training SMA is 10.0, test actuals are 12.0 -> error = 10 - 12 = -2
    # MAE = 2.0000, Bias = -2.0000, WAPE = (7*2)/(7*12) = 14/84 = 0.1667
    assert Decimal(ev["mae"]) == Decimal("2.0000")
    assert Decimal(ev["forecast_bias"]) == Decimal("-2.0000")
    assert Decimal(ev["wape"]) == Decimal("0.1667")
    assert len(ev["actuals_vs_predicted"]) == 7


def test_evaluate_zero_demand(client, auth_user, db_session):
    """All zeros in historical and test observations produces MAE=0 and null WAPE."""
    headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, branch_id, prod_id = _setup_forecasting_data(client, headers)

    _insert_observations(db_session, biz_id, user_id, branch_id, prod_id, [0.0] * 20)

    resp = client.post(
        f"/api/v1/businesses/{biz_id}/forecasting/evaluate",
        json={"branch_id": branch_id, "product_id": prod_id, "window_size": 7, "test_days": 5},
        headers=headers,
    )
    assert resp.status_code == 200
    ev = resp.json()["data"]["evaluation"]
    assert Decimal(ev["mae"]) == Decimal("0.0000")
    assert ev["wape"] is None
    assert Decimal(ev["forecast_bias"]) == Decimal("0.0000")


def test_sufficiency_endpoint(client, auth_user, db_session):
    """Sufficiency endpoint accurately reflects observation counts and capability flags."""
    headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, branch_id, prod_id = _setup_forecasting_data(client, headers)

    # 1. Zero observations
    resp0 = client.get(
        f"/api/v1/businesses/{biz_id}/forecasting/sufficiency?branch_id={branch_id}&product_id={prod_id}",
        headers=headers,
    )
    assert resp0.status_code == 200
    s0 = resp0.json()["data"]["sufficiency"]
    assert s0["daily_observations"] == 0
    assert s0["supports_baseline"] is False
    assert s0["supports_weekday"] is False

    # 2. Add 14 observations
    _insert_observations(db_session, biz_id, user_id, branch_id, prod_id, [10.0] * 14)
    resp14 = client.get(
        f"/api/v1/businesses/{biz_id}/forecasting/sufficiency?branch_id={branch_id}&product_id={prod_id}",
        headers=headers,
    )
    assert resp14.status_code == 200
    s14 = resp14.json()["data"]["sufficiency"]
    assert s14["daily_observations"] == 14
    assert s14["supports_baseline"] is True
    assert s14["supports_weekday"] is False


def test_list_runs_paginated(client, auth_user, db_session):
    """Listing forecast runs supports pagination metadata."""
    headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, branch_id, prod_id = _setup_forecasting_data(client, headers)

    _insert_observations(db_session, biz_id, user_id, branch_id, prod_id, [10.0] * 15)

    # Generate 3 runs
    for _ in range(3):
        client.post(
            f"/api/v1/businesses/{biz_id}/forecasting/predict",
            json={"branch_id": branch_id, "product_id": prod_id, "horizon_days": 3},
            headers=headers,
        )

    # Request page 1 with page_size 2
    resp = client.get(
        f"/api/v1/businesses/{biz_id}/forecasting/runs?page=1&page_size=2",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]["forecast_runs"]) == 2
    assert body["data"]["pagination"]["total"] == 3
    assert body["data"]["pagination"]["total_pages"] == 2


def test_get_run_with_results(client, auth_user, db_session):
    """Fetching a run by ID includes its forecast predictions."""
    headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, branch_id, prod_id = _setup_forecasting_data(client, headers)

    _insert_observations(db_session, biz_id, user_id, branch_id, prod_id, [20.0] * 15)

    post_resp = client.post(
        f"/api/v1/businesses/{biz_id}/forecasting/predict",
        json={"branch_id": branch_id, "product_id": prod_id, "horizon_days": 5},
        headers=headers,
    )
    run_id = post_resp.json()["data"]["forecast_run"]["id"]

    get_resp = client.get(
        f"/api/v1/businesses/{biz_id}/forecasting/runs/{run_id}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    run_data = get_resp.json()["data"]["forecast_run"]
    assert run_data["id"] == run_id
    assert len(run_data["predictions"]) == 5


def test_aggregate_granularity_rejected(client, auth_user, db_session):
    """Weekly/monthly observations are never fabricated into daily forecasts."""
    headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, branch_id, prod_id = _setup_forecasting_data(client, headers)

    # Insert 4 weekly observations only
    _insert_observations(
        db_session,
        biz_id,
        user_id,
        branch_id,
        prod_id,
        [100.0, 120.0, 110.0, 130.0],
        granularity="weekly",
    )

    suff_resp = client.get(
        f"/api/v1/businesses/{biz_id}/forecasting/sufficiency?branch_id={branch_id}&product_id={prod_id}",
        headers=headers,
    )
    assert suff_resp.status_code == 200
    suff = suff_resp.json()["data"]["sufficiency"]
    assert suff["total_observations"] == 4
    assert suff["daily_observations"] == 0
    assert suff["supports_baseline"] is False
    assert "non-daily" in suff["message"]


def test_direct_forecasting_endpoints(client, auth_user, db_session):
    """Direct endpoints under /api/v1/forecasting/ work with business_id in payload/query."""
    headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, branch_id, prod_id = _setup_forecasting_data(client, headers)

    _insert_observations(db_session, biz_id, user_id, branch_id, prod_id, [25.0] * 16)

    # Direct predict
    pred_resp = client.post(
        "/api/v1/forecasting/predict",
        json={"business_id": biz_id, "branch_id": branch_id, "product_id": prod_id, "horizon_days": 4},
        headers=headers,
    )
    assert pred_resp.status_code == 200
    assert pred_resp.json()["data"]["forecast_run"]["is_reliable"] is True

    # Direct evaluate
    eval_resp = client.post(
        "/api/v1/forecasting/evaluate",
        json={"business_id": biz_id, "branch_id": branch_id, "product_id": prod_id, "test_days": 2},
        headers=headers,
    )
    assert eval_resp.status_code == 200

    # Direct sufficiency
    suff_resp = client.get(
        f"/api/v1/forecasting/sufficiency?business_id={biz_id}&branch_id={branch_id}&product_id={prod_id}",
        headers=headers,
    )
    assert suff_resp.status_code == 200


def test_agent_invoke_forecasting_with_data(client, auth_user, db_session):
    """The agent tool invoke_forecasting executes real calculations when given branch and product."""
    headers = auth_user["headers"]
    user_id = auth_user["user"]["id"]
    biz_id, branch_id, prod_id = _setup_forecasting_data(client, headers)

    _insert_observations(db_session, biz_id, user_id, branch_id, prod_id, [30.0] * 15)

    tool_res = execute_tool_by_name(
        "invoke_forecasting",
        {"branch_id": branch_id, "product_id": prod_id, "horizon_days": 5},
        db_session,
        biz_id,
    )
    assert tool_res["data"]["status"] == "success"
    assert tool_res["data"]["is_reliable"] is True
    assert len(tool_res["data"]["predictions"]) == 5
    assert Decimal(tool_res["data"]["predictions"][0]["predicted_qty"]) == Decimal("30.000")
