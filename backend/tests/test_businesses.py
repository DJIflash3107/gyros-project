def test_business_crud_flow(client, auth_user):
    headers = auth_user["headers"]

    # 1. Create Business
    create_resp = client.post(
        "/api/v1/businesses",
        json={
            "name": "Kebab Paradise",
            "currency": "IDR",
            "timezone": "Asia/Jakarta",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    biz = create_resp.json()["data"]["business"]
    biz_id = biz["id"]
    assert biz["name"] == "Kebab Paradise"
    assert biz["currency"] == "IDR"

    # 2. List Businesses (Creator should see it)
    list_resp = client.get("/api/v1/businesses", headers=headers)
    assert list_resp.status_code == 200
    list_data = list_resp.json()["data"]
    assert len(list_data["businesses"]) >= 1
    assert list_data["pagination"]["total"] >= 1

    # 3. Get Business
    get_resp = client.get(f"/api/v1/businesses/{biz_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["business"]["id"] == biz_id

    # 4. Update Business
    patch_resp = client.patch(
        f"/api/v1/businesses/{biz_id}",
        json={"name": "Kebab Paradise Updated"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["business"]["name"] == "Kebab Paradise Updated"

    # 5. Delete Business
    del_resp = client.delete(f"/api/v1/businesses/{biz_id}", headers=headers)
    assert del_resp.status_code == 200

    # 6. Verify Deleted: non-member or not found returns 403 or 404
    get_again = client.get(f"/api/v1/businesses/{biz_id}", headers=headers)
    assert get_again.status_code in (403, 404)

    # Verify not present in user's business list
    list_after = client.get("/api/v1/businesses", headers=headers)
    biz_ids = [b["id"] for b in list_after.json()["data"]["businesses"]]
    assert biz_id not in biz_ids
