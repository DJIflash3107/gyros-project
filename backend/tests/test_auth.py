def test_register_success(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Alice Bob",
            "email": "alice@example.com",
            "password": "Password123!",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert "user" in body["data"]
    assert body["data"]["user"]["email"] == "alice@example.com"
    assert "password_hash" not in body["data"]["user"]
    assert body["message"]["success"] == "User registered successfully"
    assert body["error"] == {}


def test_register_duplicate_email(client, auth_user):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Duplicate User",
            "email": "testuser@example.com",
            "password": "Password123!",
        },
    )
    assert response.status_code == 409
    body = response.json()
    assert "email" in body["error"]
    assert "already exists" in body["error"]["email"]


def test_login_success(client, auth_user):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "testuser@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "token" in body["data"]
    assert "access_token" in body["data"]["token"]
    assert body["data"]["token"]["token_type"] == "bearer"
    assert "password_hash" not in body["data"]["user"]


def test_login_invalid_password(client, auth_user):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "testuser@example.com",
            "password": "WrongPassword123!",
        },
    )
    assert response.status_code == 401
    body = response.json()
    assert body["message"]["error"] == "Authentication failed"
    assert "authentication" in body["error"]


def test_me_endpoint_success(client, auth_user):
    response = client.get("/api/v1/auth/me", headers=auth_user["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["user"]["email"] == "testuser@example.com"
    assert "password_hash" not in body["data"]["user"]


def test_me_endpoint_missing_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    body = response.json()
    assert body["message"]["error"] == "Authentication failed"
    assert "authentication" in body["error"]


def test_me_endpoint_invalid_token(client):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.fake.token"})
    assert response.status_code == 401
    body = response.json()
    assert body["message"]["error"] == "Authentication failed"
