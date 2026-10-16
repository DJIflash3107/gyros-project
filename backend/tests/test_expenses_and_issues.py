def test_expenses_and_import_issues(client, auth_user):
    headers = auth_user["headers"]

    # Setup Business & Branch
    biz_resp = client.post("/api/v1/businesses", json={"name": "Expense Biz"}, headers=headers)
    biz_id = biz_resp.json()["data"]["business"]["id"]

    branch_resp = client.post(
        f"/api/v1/businesses/{biz_id}/branches",
        json={"name": "Downtown Branch"},
        headers=headers,
    )
    branch_id = branch_resp.json()["data"]["branch"]["id"]

    # 1. Expense Creation
    exp_resp = client.post(
        f"/api/v1/businesses/{biz_id}/expenses",
        json={
            "branch_id": branch_id,
            "expense_date": "2026-10-15",
            "category": "Utilities",
            "description": "Electricity bill",
            "amount": "1250000.00",
            "currency": "IDR",
        },
        headers=headers,
    )
    assert exp_resp.status_code == 201
    expense = exp_resp.json()["data"]["expense"]
    expense_id = expense["id"]
    assert float(expense["amount"]) == 1250000.0

    # 2. List Expenses
    list_exp = client.get(f"/api/v1/businesses/{biz_id}/expenses", headers=headers)
    assert list_exp.status_code == 200
    assert len(list_exp.json()["data"]["expenses"]) == 1

    # 3. Setup Submission for Import Issue test
    sub_resp = client.post(
        f"/api/v1/businesses/{biz_id}/sales_report_submissions",
        json={
            "input_method": "spreadsheet",
            "report_period_type": "daily",
            "coverage_start": "2026-10-01",
            "coverage_end": "2026-10-01",
        },
        headers=headers,
    )
    sub_id = sub_resp.json()["data"]["submission"]["id"]

    # 4. Create Import Issue
    issue_resp = client.post(
        f"/api/v1/sales_report_submissions/{sub_id}/import_issues",
        json={
            "source_row_number": 4,
            "field_name": "recorded_revenue",
            "issue_code": "INVALID_NUMBER_FORMAT",
            "severity": "warning",
            "message": "Cannot parse 'Rp 50,000' as decimal",
            "raw_value": "Rp 50,000",
            "resolution_status": "open",
        },
        headers=headers,
    )
    assert issue_resp.status_code == 201
    issue = issue_resp.json()["data"]["issue"]
    issue_id = issue["id"]
    assert issue["resolution_status"] == "open"

    # 5. Resolve Import Issue
    resolve_resp = client.patch(
        f"/api/v1/sales_report_submissions/{sub_id}/import_issues/{issue_id}",
        json={"resolution_status": "resolved"},
        headers=headers,
    )
    assert resolve_resp.status_code == 200
    resolved_issue = resolve_resp.json()["data"]["issue"]
    assert resolved_issue["resolution_status"] == "resolved"
    assert resolved_issue["resolved_by_user_id"] is not None
    assert resolved_issue["resolved_at"] is not None
