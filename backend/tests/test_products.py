def test_product_and_alias_crud(client, auth_user):
    headers = auth_user["headers"]

    # Setup Business
    biz_resp = client.post(
        "/api/v1/businesses",
        json={"name": "Product Test Biz"},
        headers=headers,
    )
    biz_id = biz_resp.json()["data"]["business"]["id"]

    # 1. Create Product
    prod_resp = client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={
            "name": "Chicken Gyros",
            "sku": "GYR-CHK-01",
            "category": "Main Course",
            "base_unit": "portion",
            "is_active": True,
        },
        headers=headers,
    )
    assert prod_resp.status_code == 201
    prod = prod_resp.json()["data"]["product"]
    prod_id = prod["id"]
    assert prod["name"] == "Chicken Gyros"
    assert prod["sku"] == "GYR-CHK-01"

    # 2. Duplicate SKU in same business fails (409)
    dup_sku = client.post(
        f"/api/v1/businesses/{biz_id}/products",
        json={
            "name": "Chicken Gyros Special",
            "sku": "GYR-CHK-01",
            "base_unit": "portion",
        },
        headers=headers,
    )
    assert dup_sku.status_code == 409

    # 3. Create Product Alias
    alias_resp = client.post(
        f"/api/v1/businesses/{biz_id}/product_aliases",
        json={
            "product_id": prod_id,
            "alias_name": "Gyros Ayam",
        },
        headers=headers,
    )
    assert alias_resp.status_code == 201
    alias = alias_resp.json()["data"]["alias"]
    assert alias["normalized_alias"] == "gyros ayam"
    alias_id = alias["id"]

    # 4. Duplicate normalized alias in same business fails (409)
    dup_alias = client.post(
        f"/api/v1/businesses/{biz_id}/product_aliases",
        json={
            "product_id": prod_id,
            "alias_name": "GYROS AYAM",
        },
        headers=headers,
    )
    assert dup_alias.status_code == 409

    # 5. List and Get Aliases
    list_alias = client.get(f"/api/v1/businesses/{biz_id}/product_aliases", headers=headers)
    assert list_alias.status_code == 200
    assert len(list_alias.json()["data"]["aliases"]) == 1

    # 6. Delete Alias & Product
    del_alias = client.delete(f"/api/v1/businesses/{biz_id}/product_aliases/{alias_id}", headers=headers)
    assert del_alias.status_code == 200

    del_prod = client.delete(f"/api/v1/businesses/{biz_id}/products/{prod_id}", headers=headers)
    assert del_prod.status_code == 200
