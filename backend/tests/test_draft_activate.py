import io
import openpyxl
import pytest

from app.configs.settings import settings
from app.models.product import Product
from app.models.branch import Branch
from app.models.sales_report_submission import SalesReportSubmission
from app.models.sales_report_staging_row import SalesReportStagingRow


@pytest.fixture(autouse=True)
def disable_semantic_mapping(monkeypatch):
    monkeypatch.setattr(settings, "SEMANTIC_MAPPING_ENABLED", False)


def _setup_biz_and_branch(client, headers):
    biz_resp = client.post("/api/v1/businesses", json={"name": "Activate Test Biz"}, headers=headers)
    biz_id = biz_resp.json()["data"]["business"]["id"]

    branch_resp = client.post(
        f"/api/v1/businesses/{biz_id}/branches",
        json={"name": "Main Branch", "branch_code": "MB-01"},
        headers=headers,
    )
    branch_id = branch_resp.json()["data"]["branch"]["id"]
    return biz_id, branch_id


def _create_xlsx(headers, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales"
    ws.append(headers)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_draft_product_activation_and_staging_row_update(client, auth_user):
    headers = auth_user["headers"]
    biz_id, branch_id = _setup_biz_and_branch(client, headers)

    # 1. Upload spreadsheet with unknown product "Lamb Wrap"
    xlsx_bytes = _create_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty"],
        rows=[["Lamb Wrap", branch_id, "2026-10-01", "2026-10-01", "daily", 8]],
    )

    proc_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("report.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert proc_resp.status_code == 201
    proc_data = proc_resp.json()["data"]
    sub_id = proc_data["submission"]["id"]
    draft_products = proc_data["summary"]["auto_created_products"]
    assert len(draft_products) == 1
    draft_pid = draft_products[0]["id"]
    assert draft_products[0]["name"] == "Lamb Wrap"
    assert draft_products[0]["status"] == "draft"

    # 2. Verify default product list excludes draft
    prod_list = client.get(f"/api/v1/businesses/{biz_id}/products", headers=headers)
    assert prod_list.status_code == 200
    assert len(prod_list.json()["data"]["products"]) == 0

    # 3. Verify ?status=draft lists the draft
    draft_list = client.get(f"/api/v1/businesses/{biz_id}/products?status=draft", headers=headers)
    assert draft_list.status_code == 200
    assert len(draft_list.json()["data"]["products"]) == 1
    assert draft_list.json()["data"]["products"][0]["id"] == draft_pid

    # 4. Attempt to confirm submission while product is still draft -> should FAIL (422)
    conf_fail = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/{sub_id}/confirm",
        headers=headers,
    )
    assert conf_fail.status_code == 422
    assert "Draft products must be activated" in conf_fail.json()["error"]["products"]

    # 5. Activate the draft product
    act_resp = client.post(
        f"/api/v1/businesses/{biz_id}/products/{draft_pid}/activate",
        json={
            "base_unit": "portion",
            "sku": "LMB-001",
            "category": "Wraps",
            "name": "Lamb Wrap Supreme",  # rename
        },
        headers=headers,
    )
    assert act_resp.status_code == 200
    activated_prod = act_resp.json()["data"]["product"]
    assert activated_prod["status"] == "active"
    assert activated_prod["is_active"] is True
    assert activated_prod["name"] == "Lamb Wrap Supreme"
    assert activated_prod["sku"] == "LMB-001"

    # 6. Verify activating again fails (no longer draft)
    act_again = client.post(
        f"/api/v1/businesses/{biz_id}/products/{draft_pid}/activate",
        json={"base_unit": "portion"},
        headers=headers,
    )
    assert act_again.status_code == 422

    # 7. Confirm submission now SUCCEEDS
    conf_ok = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/{sub_id}/confirm",
        headers=headers,
    )
    assert conf_ok.status_code == 200
    assert conf_ok.json()["data"]["submission"]["status"] == "confirmed"


def test_draft_branch_activation_and_filtering(client, auth_user):
    headers = auth_user["headers"]
    biz_resp = client.post("/api/v1/businesses", json={"name": "Branch Activate Biz"}, headers=headers)
    biz_id = biz_resp.json()["data"]["business"]["id"]

    # 1. Upload with unknown branch name
    xlsx_bytes = _create_xlsx(
        headers=["Product", "Branch Name", "Period Start", "Period End", "Granularity", "Sold Qty"],
        rows=[["Any Product", "Draft Branch Bandung", "2026-10-01", "2026-10-01", "daily", 5]],
    )

    proc_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
        },
        files={"file": ("branch_report.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert proc_resp.status_code == 201
    draft_branches = proc_resp.json()["data"]["summary"]["auto_created_branches"]
    assert len(draft_branches) == 1
    draft_bid = draft_branches[0]["id"]
    assert draft_branches[0]["name"] == "Draft Branch Bandung"

    # 2. Default branch list excludes draft
    b_list = client.get(f"/api/v1/businesses/{biz_id}/branches", headers=headers)
    assert b_list.status_code == 200
    assert len(b_list.json()["data"]["branches"]) == 0

    # 3. Filter ?status=draft lists the draft branch
    b_draft_list = client.get(f"/api/v1/businesses/{biz_id}/branches?status=draft", headers=headers)
    assert b_draft_list.status_code == 200
    assert len(b_draft_list.json()["data"]["branches"]) == 1

    # 4. Activate branch
    act_resp = client.post(
        f"/api/v1/businesses/{biz_id}/branches/{draft_bid}/activate",
        json={
            "branch_code": "BDG-01",
            "address": "Jl. Braga No. 10",
        },
        headers=headers,
    )
    assert act_resp.status_code == 200
    activated_b = act_resp.json()["data"]["branch"]
    assert activated_b["status"] == "active"
    assert activated_b["is_active"] is True
    assert activated_b["branch_code"] == "BDG-01"


def test_orphan_draft_cleanup_on_confirm(client, auth_user, db_session):
    headers = auth_user["headers"]
    biz_id, branch_id = _setup_biz_and_branch(client, headers)

    # Pre-create a known active product
    client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Real Gyros", "base_unit": "portion", "sku": "REAL-1"},
        headers=headers,
    )
    real_prod = db_session.query(Product).filter(Product.name == "Real Gyros").first()

    # Create a draft product manually in DB to simulate an unreferenced draft
    orphan_draft = Product(
        business_id=biz_id,
        name="Unused Draft Item",
        base_unit="pcs",
        is_active=False,
        status="draft",
        auto_created_from="Unused Draft Item",
    )
    db_session.add(orphan_draft)
    db_session.commit()
    orphan_id = orphan_draft.id

    # Create and confirm a submission that only references the Real Gyros
    xlsx_bytes = _create_xlsx(
        headers=["Product", "Branch ID", "Period Start", "Period End", "Granularity", "Sold Qty"],
        rows=[["Real Gyros", branch_id, "2026-10-01", "2026-10-01", "daily", 10]],
    )

    proc_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/process",
        data={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
            "branch_id": branch_id,
        },
        files={"file": ("real_report.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert proc_resp.status_code == 201
    sub_id = proc_resp.json()["data"]["submission"]["id"]

    # Confirm submission
    conf_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/{sub_id}/confirm",
        headers=headers,
    )
    assert conf_resp.status_code == 200

    # Orphan draft should now be DELETED by cleanup
    cleaned_product = db_session.query(Product).filter(Product.id == orphan_id).first()
    assert cleaned_product is None
