from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import jwt
import pytest

from app.configs.settings import settings
from app.models.schemas.agent import AgentSSEEvent


def test_no_token_returns_401(client):
    """Missing Authorization header returns 401."""
    resp = client.post(
        "/api/v1/agent/businesses/1/chat",
        json={"message": "Hello agent"},
    )
    assert resp.status_code == 401
    assert "Missing authorization token" in resp.json()["error"]["authentication"]


def test_invalid_token_returns_401(client):
    """Malformed or invalid JWT returns 401."""
    resp = client.post(
        "/api/v1/agent/businesses/1/chat",
        json={"message": "Hello agent"},
        headers={"Authorization": "Bearer not.a.valid.jwt.token"},
    )
    assert resp.status_code == 401


def test_expired_token_returns_401(client):
    """Expired JWT returns 401."""
    expired_payload = {
        "sub": "1",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    expired_token = jwt.encode(
        expired_payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    resp = client.post(
        "/api/v1/agent/businesses/1/chat",
        json={"message": "Hello agent"},
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401


def test_non_member_returns_403(client, auth_user, second_user):
    """Valid authenticated user who is not a member of the business returns 403."""
    # User 1 creates business
    biz_resp = client.post(
        "/api/v1/businesses",
        json={"name": "Owner Business"},
        headers=auth_user["headers"],
    )
    assert biz_resp.status_code == 201
    biz_id = biz_resp.json()["data"]["business"]["id"]

    # User 2 tries to chat with User 1's business agent
    resp = client.post(
        f"/api/v1/agent/businesses/{biz_id}/chat",
        json={"message": "Show me your finances"},
        headers=second_user["headers"],
    )
    assert resp.status_code == 403
    assert "not a member" in resp.json()["error"]["authorization"]


def test_member_can_access(client, auth_user):
    """Valid member can access the agent chat endpoint and starts receiving stream."""
    biz_resp = client.post(
        "/api/v1/businesses",
        json={"name": "Member Business"},
        headers=auth_user["headers"],
    )
    assert biz_resp.status_code == 201
    biz_id = biz_resp.json()["data"]["business"]["id"]

    async def mock_stream(*args, **kwargs):
        yield AgentSSEEvent.create_status("routing", "Analyzing request...")
        yield AgentSSEEvent.create_complete(tools_used=[], duration_ms=50.0)

    with patch("app.services.agent_service.stream_agent_chat", side_effect=mock_stream):
        resp = client.post(
            f"/api/v1/agent/businesses/{biz_id}/chat",
            json={"message": "Hello agent"},
            headers=auth_user["headers"],
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        lines = [line.strip() for line in resp.text.split("\n") if line.strip()]
        assert any("agent_status" in line for line in lines)
        assert any("[DONE]" in line for line in lines)


def test_cross_business_isolation(client, auth_user, second_user):
    """Strict tenant isolation prevents users from accessing another business's agent."""
    # Business A created by user 1
    biz_a = client.post(
        "/api/v1/businesses",
        json={"name": "Business A"},
        headers=auth_user["headers"],
    ).json()["data"]["business"]["id"]

    # Business B created by user 2
    biz_b = client.post(
        "/api/v1/businesses",
        json={"name": "Business B"},
        headers=second_user["headers"],
    ).json()["data"]["business"]["id"]

    # User 1 tries to access Business B -> 403
    resp_a_to_b = client.post(
        f"/api/v1/agent/businesses/{biz_b}/chat",
        json={"message": "What is Business B's data?"},
        headers=auth_user["headers"],
    )
    assert resp_a_to_b.status_code == 403

    # User 2 tries to access Business A -> 403
    resp_b_to_a = client.post(
        f"/api/v1/agent/businesses/{biz_a}/chat",
        json={"message": "What is Business A's data?"},
        headers=second_user["headers"],
    )
    assert resp_b_to_a.status_code == 403
