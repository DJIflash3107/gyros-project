import io
import openpyxl
import pytest
from decimal import Decimal
from app.configs.settings import settings


@pytest.fixture(autouse=True)
def disable_semantic_mapping_in_tests(monkeypatch):
    monkeypatch.setattr(settings, "SEMANTIC_MAPPING_ENABLED", False)


def _create_test_xlsx(headers: list, rows: list) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _setup_test_data(client, headers):
    biz_resp = client.post("/api/v1/businesses", json={"name": "Auto Sync Test Biz"}, headers=headers)
    assert biz_resp.status_code == 201
    biz_id = biz_resp.json()["data"]["business"]["id"]

    branch_resp = client.post(f"/api/v1/businesses/{biz_id}/branches", json={"name": "Main Branch"}, headers=headers)
    assert branch_resp.status_code == 201
    branch_id = branch_resp.json()["data"]["branch"]["id"]

    prod_resp = client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Beef Gyros", "base_unit": "portion"},
        headers=headers,
    )
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["data"]["product"]["id"]

    return biz_id, branch_id, prod_id


def test_auto_sync_price_and_cost_from_spreadsheet_import(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id = _setup_test_data(client, headers)

    # Spreadsheet with Indonesian column headers 'Harga Jual' and 'HPP'
    xlsx_bytes = _create_test_xlsx(
        headers=[
            "Product", "Branch ID", "Period Start", "Period End", "Granularity",
            "Sold Qty", "Recorded Revenue", "Harga Jual", "HPP",
        ],
        rows=[
            ["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 20, 1000000, 50000, 25000],
        ],
    )

    # 1. Process Spreadsheet
    proc_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("sales.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert proc_resp.status_code == 201
    sub_id = proc_resp.json()["data"]["submission"]["id"]

    # 2. Verify Staging Row contains parsed unit_price and unit_cost
    rows_resp = client.get(f"/api/v1/sales_report_submissions/{sub_id}/staging_rows", headers=headers)
    assert rows_resp.status_code == 200
    staging_rows = rows_resp.json()["data"]["staging_rows"]
    assert len(staging_rows) == 1
    assert float(staging_rows[0]["unit_price"]) == 50000.0
    assert float(staging_rows[0]["unit_cost"]) == 25000.0

    # 3. Confirm Submission
    confirm_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/{sub_id}/confirm",
        headers=headers,
    )
    assert confirm_resp.status_code == 200

    # 4. Verify ProductPriceHistory record auto-generated
    price_resp = client.get(f"/api/v1/businesses/{biz_id}/product_price_history?product_id={prod_id}", headers=headers)
    assert price_resp.status_code == 200
    prices = price_resp.json()["data"]["price_histories"]
    assert len(prices) == 1
    assert float(prices[0]["selling_price"]) == 50000.0
    assert prices[0]["effective_from"] == "2026-10-01"
    assert prices[0]["effective_to"] is None
    assert prices[0]["source_submission_id"] == sub_id

    # 5. Verify ProductCostHistory record auto-generated
    cost_resp = client.get(f"/api/v1/businesses/{biz_id}/product_cost_history?product_id={prod_id}", headers=headers)
    assert cost_resp.status_code == 200
    costs = cost_resp.json()["data"]["cost_histories"]
    assert len(costs) == 1
    assert float(costs[0]["unit_cost"]) == 25000.0
    assert costs[0]["effective_from"] == "2026-10-01"
    assert costs[0]["effective_to"] is None
    assert costs[0]["source_submission_id"] == sub_id


def test_auto_derive_unit_price_fallback_when_column_absent(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id = _setup_test_data(client, headers)

    # Spreadsheet WITHOUT price or cost columns (revenue=1500000, qty=25 -> derived price=60000)
    xlsx_bytes = _create_test_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue"],
        rows=[
            ["Beef Gyros", branch_id, "2026-10-05", "2026-10-05", "daily", 25, 1500000],
        ],
    )

    proc_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-05",
            "coverage_end": "2026-10-05",
            "branch_id": branch_id,
        },
        files={"file": ("sales.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert proc_resp.status_code == 201
    sub_id = proc_resp.json()["data"]["submission"]["id"]

    # Check Staging Row has derived unit_price and None for unit_cost
    rows_resp = client.get(f"/api/v1/sales_report_submissions/{sub_id}/staging_rows", headers=headers)
    staging_rows = rows_resp.json()["data"]["staging_rows"]
    assert len(staging_rows) == 1
    assert float(staging_rows[0]["unit_price"]) == 60000.0
    assert staging_rows[0]["unit_cost"] is None

    # Confirm submission
    confirm_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/{sub_id}/confirm",
        headers=headers,
    )
    assert confirm_resp.status_code == 200

    # Verify price history was created with derived price
    price_resp = client.get(f"/api/v1/businesses/{biz_id}/product_price_history?product_id={prod_id}", headers=headers)
    prices = price_resp.json()["data"]["price_histories"]
    assert len(prices) == 1
    assert float(prices[0]["selling_price"]) == 60000.0

    # Cost history is skipped cleanly without error
    cost_resp = client.get(f"/api/v1/businesses/{biz_id}/product_cost_history?product_id={prod_id}", headers=headers)
    costs = cost_resp.json()["data"]["cost_histories"]
    assert len(costs) == 0


def test_price_change_closes_previous_price_history(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id = _setup_test_data(client, headers)

    # Submission 1: Price 50000 on 2026-10-01
    xlsx1 = _create_test_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue", "price"],
        rows=[["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 10, 500000, 50000]],
    )
    resp1 = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={"input_method": "spreadsheet", "report_period_type": "daily", "coverage_start": "2026-10-01", "coverage_end": "2026-10-01", "branch_id": branch_id},
        files={"file": ("sales1.xlsx", xlsx1, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    sub1_id = resp1.json()["data"]["submission"]["id"]
    client.post(f"/api/v1/businesses/{biz_id}/sales_report_submissions/{sub1_id}/confirm", headers=headers)

    # Submission 2: Price changed to 55000 on 2026-10-10
    xlsx2 = _create_test_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue", "price"],
        rows=[["Beef Gyros", branch_id, "2026-10-10", "2026-10-10", "daily", 10, 550000, 55000]],
    )
    resp2 = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={"input_method": "spreadsheet", "report_period_type": "daily", "coverage_start": "2026-10-10", "coverage_end": "2026-10-10", "branch_id": branch_id},
        files={"file": ("sales2.xlsx", xlsx2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    sub2_id = resp2.json()["data"]["submission"]["id"]
    client.post(f"/api/v1/businesses/{biz_id}/sales_report_submissions/{sub2_id}/confirm", headers=headers)

    # Verify both records: previous closed at 2026-10-09, new open from 2026-10-10
    price_resp = client.get(f"/api/v1/businesses/{biz_id}/product_price_history?product_id={prod_id}", headers=headers)
    prices = price_resp.json()["data"]["price_histories"]
    assert len(prices) == 2

    # Ordered desc by effective_from
    latest = prices[0]
    older = prices[1]

    assert float(latest["selling_price"]) == 55000.0
    assert latest["effective_from"] == "2026-10-10"
    assert latest["effective_to"] is None

    assert float(older["selling_price"]) == 50000.0
    assert older["effective_from"] == "2026-10-01"
    assert older["effective_to"] == "2026-10-09"


def test_consecutive_days_and_idempotency(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id, prod_id = _setup_test_data(client, headers)

    # Sub 1: Day 1 (2026-10-01) with price 50000
    xlsx1 = _create_test_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue", "price"],
        rows=[["Beef Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 10, 500000, 50000]],
    )
    sub1_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={"input_method": "spreadsheet", "report_period_type": "daily", "coverage_start": "2026-10-01", "coverage_end": "2026-10-01", "branch_id": branch_id},
        files={"file": ("s1.xlsx", xlsx1, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    sub1_id = sub1_resp.json()["data"]["submission"]["id"]
    client.post(f"/api/v1/businesses/{biz_id}/sales_report_submissions/{sub1_id}/confirm", headers=headers)

    # Sub 2: Day 2 (2026-10-02) with SAME price 50000 (Idempotent - should not create duplicate open row)
    xlsx2 = _create_test_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty", "Recorded Revenue", "price"],
        rows=[["Beef Gyros", branch_id, "2026-10-02", "2026-10-02", "daily", 15, 750000, 50000]],
    )
    sub2_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={"input_method": "spreadsheet", "report_period_type": "daily", "coverage_start": "2026-10-02", "coverage_end": "2026-10-02", "branch_id": branch_id},
        files={"file": ("s2.xlsx", xlsx2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    sub2_id = sub2_resp.json()["data"]["submission"]["id"]
    client.post(f"/api/v1/businesses/{biz_id}/sales_report_submissions/{sub2_id}/confirm", headers=headers)

    price_resp = client.get(f"/api/v1/businesses/{biz_id}/product_price_history?product_id={prod_id}", headers=headers)
    prices = price_resp.json()["data"]["price_histories"]
    # Still 1 price record because price never changed!
    assert len(prices) == 1
    assert float(prices[0]["selling_price"]) == 50000.0
