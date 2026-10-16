def test_sales_report_submission_and_confirmation(client, auth_user):
    headers = auth_user["headers"]

    # 1. Setup Business, Branch, Product
    biz_resp = client.post("/api/v1/businesses", json={"name": "Sales Test Biz"}, headers=headers)
    biz_id = biz_resp.json()["data"]["business"]["id"]

    branch_resp = client.post(
        f"/api/v1/businesses/{biz_id}/branches",
        json={"name": "Branch Alpha"},
        headers=headers,
    )
    branch_id = branch_resp.json()["data"]["branch"]["id"]

    prod_resp = client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Beef Gyros", "base_unit": "portion"},
        headers=headers,
    )
    prod_id = prod_resp.json()["data"]["product"]["id"]

    # 2. Date validation: coverage_end < coverage_start must fail with 422
    invalid_dates_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions",
        json={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-15",
            "coverage_end": "2026-10-10",
        },
        headers=headers,
    )
    assert invalid_dates_resp.status_code == 422

    # 3. Create Valid Submission
    sub_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions",
        json={
            "branch_id": branch_id,
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-07",
            "source_file_name": "sales_oct_w1.xlsx",
        },
        headers=headers,
    )
    assert sub_resp.status_code == 201
    sub_id = sub_resp.json()["data"]["submission"]["id"]

    # 4. Add Staging Row
    row_resp = client.post(
        f"/api/v1/sales_report_submissions/{sub_id}/staging_rows",
        json={
            "source_row_number": 1,
            "raw_payload_json": {"item": "Beef Gyros", "qty": 50, "revenue": 2500000},
            "raw_product_name": "Beef Gyros",
            "branch_id": branch_id,
            "product_id": prod_id,
            "period_start": "2026-10-01",
            "period_end": "2026-10-07",
            "granularity": "weekly",
            "sold_qty": "50.000",
            "recorded_revenue": "2500000.00",
            "review_status": "ready",
        },
        headers=headers,
    )
    assert row_resp.status_code == 201
    row_id = row_resp.json()["data"]["staging_row"]["id"]

    # 5. Confirm Submission
    confirm_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions/{sub_id}/confirm",
        headers=headers,
    )
    assert confirm_resp.status_code == 200
    sub_confirmed = confirm_resp.json()["data"]["submission"]
    assert sub_confirmed["status"] == "confirmed"
    assert sub_confirmed["accepted_rows"] == 1
    assert sub_confirmed["total_rows"] == 1
    assert sub_confirmed["confirmed_at"] is not None

    # 6. Verify Observation is created and queryable
    obs_resp = client.get(
        f"/api/v1/businesses/{biz_id}/sales_report_observations",
        headers=headers,
    )
    assert obs_resp.status_code == 200
    observations = obs_resp.json()["data"]["observations"]
    assert len(observations) == 1
    assert observations[0]["product_id"] == prod_id
    assert float(observations[0]["recorded_revenue"]) == 2500000.0

    # 7. Overlap Detection: attempting to manually create an overlapping observation fails (409)
    overlap_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_observations",
        json={
            "branch_id": branch_id,
            "product_id": prod_id,
            "source_submission_id": sub_id,
            "period_start": "2026-10-05",  # Overlaps 2026-10-01 to 2026-10-07!
            "period_end": "2026-10-12",
            "granularity": "weekly",
            "sold_qty": "30.000",
        },
        headers=headers,
    )
    assert overlap_resp.status_code == 409
    assert "overlap" in overlap_resp.json()["message"]["error"].lower()
