def test_business_membership_authorization_and_isolation(client, auth_user, second_user):
    owner_headers = auth_user["headers"]
    other_headers = second_user["headers"]

    # 1. User 1 creates Business 1
    biz_resp = client.post(
        "/api/v1/businesses",
        json={"name": "Alpha Corp"},
        headers=owner_headers,
    )
    biz_id = biz_resp.json()["data"]["business"]["id"]

    # 2. User 2 (not a member) tries to access Business 1 -> 403 Forbidden
    forbidden_resp = client.get(
        f"/api/v1/businesses/{biz_id}",
        headers=other_headers,
    )
    assert forbidden_resp.status_code == 403
    assert "not a member" in forbidden_resp.json()["error"]["authorization"]

    # 3. User 2 tries to access branches of Business 1 -> 403 Forbidden
    forbidden_branch = client.get(
        f"/api/v1/businesses/{biz_id}/branches",
        headers=other_headers,
    )
    assert forbidden_branch.status_code == 403


def test_business_operations_agent_read_only_access(client, auth_user, second_user):
    """
    Test that Business Operations Agent (viewer/read-only role)
    cannot perform INSERT, UPDATE, or DELETE on operational tables.
    The agent must use read-only data access.
    """
    owner_headers = auth_user["headers"]
    agent_headers = second_user["headers"]
    agent_user_id = second_user["user"]["id"]

    # 1. Owner creates business
    biz_resp = client.post(
        "/api/v1/businesses",
        json={"name": "Operations Enterprise"},
        headers=owner_headers,
    )
    biz_id = biz_resp.json()["data"]["business"]["id"]

    # 2. Owner adds second_user (Business Operations Agent) as "viewer" (read-only)
    member_resp = client.post(
        f"/api/v1/businesses/{biz_id}/memberships",
        json={
            "user_id": agent_user_id,
            "role": "viewer",
        },
        headers=owner_headers,
    )
    assert member_resp.status_code == 201
    assert member_resp.json()["data"]["membership"]["role"] == "viewer"

    # Owner creates an initial branch and product
    branch_resp = client.post(
        f"/api/v1/businesses/{biz_id}/branches",
        json={"name": "HQ Branch"},
        headers=owner_headers,
    )
    branch_id = branch_resp.json()["data"]["branch"]["id"]

    prod_resp = client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Shawarma", "base_unit": "portion"},
        headers=owner_headers,
    )
    prod_id = prod_resp.json()["data"]["product"]["id"]

    # 3. Agent CAN read operational tables (GET succeeds)
    read_branches = client.get(f"/api/v1/businesses/{biz_id}/branches", headers=agent_headers)
    assert read_branches.status_code == 200

    read_products = client.get(f"/api/v1/businesses/{biz_id}/products", headers=agent_headers)
    assert read_products.status_code == 200

    read_expenses = client.get(f"/api/v1/businesses/{biz_id}/expenses", headers=agent_headers)
    assert read_expenses.status_code == 200

    # 4. Agent CANNOT perform INSERT on operational tables (POST returns 403)
    agent_insert_branch = client.post(
        f"/api/v1/businesses/{biz_id}/branches",
        json={"name": "Agent Rogue Branch"},
        headers=agent_headers,
    )
    assert agent_insert_branch.status_code == 403
    assert "does not have sufficient permissions" in agent_insert_branch.json()["error"]["authorization"]

    agent_insert_product = client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Agent Rogue Product", "base_unit": "portion"},
        headers=agent_headers,
    )
    assert agent_insert_product.status_code == 403

    agent_insert_expense = client.post(
        f"/api/v1/businesses/{biz_id}/expenses",
        json={"expense_date": "2026-10-16", "category": "Office", "amount": "50000.00"},
        headers=agent_headers,
    )
    assert agent_insert_expense.status_code == 403

    # 5. Agent CANNOT perform UPDATE on operational tables (PATCH returns 403)
    agent_update_branch = client.patch(
        f"/api/v1/businesses/{biz_id}/branches/{branch_id}",
        json={"name": "Modified Branch"},
        headers=agent_headers,
    )
    assert agent_update_branch.status_code == 403

    agent_update_product = client.patch(
        f"/api/v1/businesses/{biz_id}/products/{prod_id}",
        json={"name": "Modified Product"},
        headers=agent_headers,
    )
    assert agent_update_product.status_code == 403

    # 6. Agent CANNOT perform DELETE on operational tables (DELETE returns 403)
    agent_delete_branch = client.delete(
        f"/api/v1/businesses/{biz_id}/branches/{branch_id}",
        headers=agent_headers,
    )
    assert agent_delete_branch.status_code == 403

    agent_delete_product = client.delete(
        f"/api/v1/businesses/{biz_id}/products/{prod_id}",
        headers=agent_headers,
    )
    assert agent_delete_product.status_code == 403
