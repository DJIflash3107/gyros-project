def test_branch_crud_and_uniqueness(client, auth_user):
    headers = auth_user["headers"]

    # Setup Business
    biz_resp = client.post(
        "/api/v1/businesses",
        json={"name": "Branch Test Biz"},
        headers=headers,
    )
    biz_id = biz_resp.json()["data"]["business"]["id"]

    # 1. Create Branch
    create_resp = client.post(
        f"/api/v1/businesses/{biz_id}/branches",
        json={
            "name": "Central Branch",
            "branch_code": "BR-001",
            "address": "123 Main Street",
            "is_active": True,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    branch = create_resp.json()["data"]["branch"]
    branch_id = branch["id"]
    assert branch["name"] == "Central Branch"
    assert branch["branch_code"] == "BR-001"

    # 2. Duplicate Name in same business should fail (409)
    dup_resp = client.post(
        f"/api/v1/businesses/{biz_id}/branches",
        json={"name": "Central Branch"},
        headers=headers,
    )
    assert dup_resp.status_code == 409
    assert "already exists" in dup_resp.json()["error"]["name"]

    # 3. List Branches
    list_resp = client.get(f"/api/v1/businesses/{biz_id}/branches", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]["branches"]) == 1

    # 4. Update Branch
    patch_resp = client.patch(
        f"/api/v1/businesses/{biz_id}/branches/{branch_id}",
        json={"address": "456 Main Street"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["branch"]["address"] == "456 Main Street"

    # 5. Delete Branch
    del_resp = client.delete(f"/api/v1/businesses/{biz_id}/branches/{branch_id}", headers=headers)
    assert del_resp.status_code == 200
