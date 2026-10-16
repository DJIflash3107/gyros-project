def test_cost_and_price_history_overlap_prevention(client, auth_user):
    headers = auth_user["headers"]

    # Setup Business & Product
    biz_resp = client.post("/api/v1/businesses", json={"name": "History Test Biz"}, headers=headers)
    biz_id = biz_resp.json()["data"]["business"]["id"]

    prod_resp = client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={"name": "Lamb Gyros", "base_unit": "portion"},
        headers=headers,
    )
    prod_id = prod_resp.json()["data"]["product"]["id"]

    # 1. Invalid date range on Cost History: effective_to <= effective_from fails (422)
    invalid_cost = client.post(
        f"/api/v1/businesses/{biz_id}/product_cost_history",
        json={
            "product_id": prod_id,
            "effective_from": "2026-10-01",
            "effective_to": "2026-09-01",
            "unit_cost": "25000.00",
            "cost_unit": "portion",
        },
        headers=headers,
    )
    assert invalid_cost.status_code == 422

    # 2. Create Initial Cost History
    cost_resp = client.post(
        f"/api/v1/businesses/{biz_id}/product_cost_history",
        json={
            "product_id": prod_id,
            "effective_from": "2026-01-01",
            "effective_to": "2026-06-30",
            "unit_cost": "25000.00",
            "cost_unit": "portion",
        },
        headers=headers,
    )
    assert cost_resp.status_code == 201
    cost_id = cost_resp.json()["data"]["cost_history"]["id"]

    # 3. Overlapping Cost Period fails (409)
    overlap_cost = client.post(
        f"/api/v1/businesses/{biz_id}/product_cost_history",
        json={
            "product_id": prod_id,
            "effective_from": "2026-06-01",  # Overlaps Jan - Jun 30
            "effective_to": "2026-12-31",
            "unit_cost": "28000.00",
            "cost_unit": "portion",
        },
        headers=headers,
    )
    assert overlap_cost.status_code == 409
    assert "overlap" in overlap_cost.json()["message"]["error"].lower()

    # 4. Non-overlapping Cost Period succeeds (201)
    valid_cost2 = client.post(
        f"/api/v1/businesses/{biz_id}/product_cost_history",
        json={
            "product_id": prod_id,
            "effective_from": "2026-07-01",
            "unit_cost": "28000.00",
            "cost_unit": "portion",
        },
        headers=headers,
    )
    assert valid_cost2.status_code == 201

    # 5. Price History: Create Initial Price
    price_resp = client.post(
        f"/api/v1/businesses/{biz_id}/product_price_history",
        json={
            "product_id": prod_id,
            "effective_from": "2026-01-01",
            "effective_to": "2026-06-30",
            "selling_price": "45000.00",
            "price_unit": "portion",
        },
        headers=headers,
    )
    assert price_resp.status_code == 201

    # 6. Overlapping Price Period fails (409)
    overlap_price = client.post(
        f"/api/v1/businesses/{biz_id}/product_price_history",
        json={
            "product_id": prod_id,
            "effective_from": "2026-03-01",
            "effective_to": "2026-08-31",
            "selling_price": "50000.00",
            "price_unit": "portion",
        },
        headers=headers,
    )
    assert overlap_price.status_code == 409
