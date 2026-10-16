import pytest


def _setup_submission_with_staging_rows(client, headers):
    # Setup business
    biz_resp = client.post("/api/v1/businesses", json={"name": "Bulk Staging Biz"}, headers=headers)
    biz_id = biz_resp.json()["data"]["business"]["id"]

    branch_resp = client.post(
        f"/api/v1/businesses/{biz_id}/branches",
        json={"name": "Main Branch"},
        headers=headers,
    )
    branch_id = branch_resp.json()["data"]["branch"]["id"]

    prod_resp = client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Doner Kebab", "base_unit": "portion"},
        headers=headers,
    )
    prod_id = prod_resp.json()["data"]["product"]["id"]

    sub_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions",
        json={
            "branch_id": branch_id,
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-03",
            "source_file_name": "oct_sales.xlsx",
        },
        headers=headers,
    )
    sub_id = sub_resp.json()["data"]["submission"]["id"]

    row_ids = []
    statuses = ["pending_review", "pending_review", "needs_correction"]
    for i, status in enumerate(statuses, start=1):
        r = client.post(
            f"/api/v1/sales_report_submissions/{sub_id}/staging_rows",
            json={
                "source_row_number": i,
                "raw_payload_json": {"row": i},
                "raw_product_name": "Doner Kebab",
                "branch_id": branch_id,
                "product_id": prod_id,
                "period_start": f"2026-10-0{i}",
                "period_end": f"2026-10-0{i}",
                "granularity": "daily",
                "sold_qty": "10.000",
                "recorded_revenue": "100000.00",
                "review_status": status,
            },
            headers=headers,
        )
        assert r.status_code == 201
        row_ids.append(r.json()["data"]["staging_row"]["id"])

    return biz_id, sub_id, row_ids


def test_bulk_update_apply_to_all(client, auth_user):
    headers = auth_user["headers"]
    _, sub_id, row_ids = _setup_submission_with_staging_rows(client, headers)

    resp = client.patch(
        f"/api/v1/sales_report_submissions/{sub_id}/staging_rows/bulk",
        json={
            "apply_to_all": True,
            "review_status": "ready",
            "review_notes": "Bulk approved by manager",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["updated_count"] == 3
    for row in data["staging_rows"]:
        assert row["review_status"] == "ready"
        assert row["review_notes"] == "Bulk approved by manager"

    # Verify listing reflects changes
    list_resp = client.get(
        f"/api/v1/sales_report_submissions/{sub_id}/staging_rows?review_status=ready",
        headers=headers,
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]["staging_rows"]) == 3


def test_bulk_update_specific_row_ids(client, auth_user):
    headers = auth_user["headers"]
    _, sub_id, row_ids = _setup_submission_with_staging_rows(client, headers)

    target_ids = [row_ids[0], row_ids[1]]
    resp = client.patch(
        f"/api/v1/sales_report_submissions/{sub_id}/staging_rows/bulk",
        json={
            "row_ids": target_ids,
            "review_status": "ready",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["updated_count"] == 2
    updated_ids = [r["id"] for r in data["staging_rows"]]
    assert set(updated_ids) == set(target_ids)

    # Third row should remain needs_correction
    row3_resp = client.get(
        f"/api/v1/sales_report_submissions/{sub_id}/staging_rows/{row_ids[2]}",
        headers=headers,
    )
    assert row3_resp.status_code == 200
    assert row3_resp.json()["data"]["staging_row"]["review_status"] == "needs_correction"


def test_bulk_update_filter_by_status(client, auth_user):
    headers = auth_user["headers"]
    _, sub_id, row_ids = _setup_submission_with_staging_rows(client, headers)

    # Only update rows that are currently "needs_correction"
    resp = client.patch(
        f"/api/v1/sales_report_submissions/{sub_id}/staging_rows/bulk",
        json={
            "apply_to_all": True,
            "filter_review_status": "needs_correction",
            "review_status": "rejected",
            "review_notes": "Rejected due to bad data",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["updated_count"] == 1
    assert data["staging_rows"][0]["id"] == row_ids[2]
    assert data["staging_rows"][0]["review_status"] == "rejected"

    # Pending review rows should remain unchanged
    pending_resp = client.get(
        f"/api/v1/sales_report_submissions/{sub_id}/staging_rows?review_status=pending_review",
        headers=headers,
    )
    assert len(pending_resp.json()["data"]["staging_rows"]) == 2


def test_bulk_update_via_post(client, auth_user):
    headers = auth_user["headers"]
    _, sub_id, row_ids = _setup_submission_with_staging_rows(client, headers)

    resp = client.post(
        f"/api/v1/sales_report_submissions/{sub_id}/staging_rows/bulk",
        json={
            "apply_to_all": True,
            "review_status": "ready",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["updated_count"] == 3


def test_bulk_update_validation_errors(client, auth_user):
    headers = auth_user["headers"]
    _, sub_id, _ = _setup_submission_with_staging_rows(client, headers)

    # Missing both row_ids and apply_to_all
    resp1 = client.patch(
        f"/api/v1/sales_report_submissions/{sub_id}/staging_rows/bulk",
        json={"review_status": "ready"},
        headers=headers,
    )
    assert resp1.status_code == 422

    # Missing fields to update
    resp2 = client.patch(
        f"/api/v1/sales_report_submissions/{sub_id}/staging_rows/bulk",
        json={"apply_to_all": True},
        headers=headers,
    )
    assert resp2.status_code == 422

    # Non-existent submission
    resp3 = client.patch(
        "/api/v1/sales_report_submissions/999999/staging_rows/bulk",
        json={"apply_to_all": True, "review_status": "ready"},
        headers=headers,
    )
    assert resp3.status_code == 404
