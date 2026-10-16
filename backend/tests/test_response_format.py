def test_standard_envelope_success(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "message" in body
    assert "error" in body
    assert "data" in body
    assert body["message"] == {"success": "Gyros Project API is running"}
    assert body["error"] == {}
    assert "app" in body["data"]


def test_standard_envelope_validation_error(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "short"},
    )
    assert response.status_code == 422
    body = response.json()
    assert "message" in body
    assert "error" in body
    assert "data" in body
    assert body["message"] == {"error": "Request validation failed"}
    assert "email" in body["error"]
    assert "password" in body["error"]
    assert body["data"] == {}


def test_standard_envelope_404_not_found(client, auth_user):
    # Try fetching a non-existent business
    # First create a business to have valid membership
    create_resp = client.post(
        "/api/v1/businesses",
        json={"name": "Temp Biz", "currency": "IDR", "timezone": "Asia/Jakarta"},
        headers=auth_user["headers"],
    )
    assert create_resp.status_code == 201
    biz_id = create_resp.json()["data"]["business"]["id"]

    response = client.get(
        f"/api/v1/businesses/{biz_id}/branches/99999",
        headers=auth_user["headers"],
    )
    assert response.status_code == 404
    body = response.json()
    assert "message" in body
    assert "error" in body
    assert "data" in body
    assert body["message"]["error"] == "Branch not found"
    assert "branch" in body["error"]
    assert body["data"] == {}
