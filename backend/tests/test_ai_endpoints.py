from unittest.mock import AsyncMock, patch
import pytest
from app.configs.settings import settings
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.exceptions import (
    AIRateLimitException,
    AIServiceException,
    ValidationException,
)
from app.models.schemas.ai import AIModelInfo


def test_ai_health_unconfigured(client):
    """When API key is empty/not configured, health check returns unconfigured status."""
    with patch.object(settings, "AMD_API_KEY", ""):
        with patch("app.configs.amd_client.settings.AMD_API_KEY", ""):
            with patch("app.services.ai_service.settings.AMD_API_KEY", ""):
                resp = client.get("/api/v1/ai/health")
                assert resp.status_code == 200
                data = resp.json()
                assert "data" in data
                assert data["data"]["health"]["status"] == "unconfigured"
                assert data["data"]["health"]["key_configured"] is False



def test_ai_health_healthy(client):
    """When API key is set and endpoint responds, health check returns healthy status."""
    mock_models = [
        AIModelInfo(id="DeepSeek-V4-Flash", supports_streaming=True, supports_tools=True)
    ]
    with patch("app.services.ai_service.list_models", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = mock_models
        with patch.object(settings, "AMD_API_KEY", "rc-mock-key"):
            with patch("app.services.ai_service.get_amd_client") as mock_get_client:
                mock_ai_client = AsyncMock()
                mock_ai_client.api_key = "rc-mock-key"
                mock_ai_client.base_url = "https://developer.amd.com.cn/radeon/api/v1"
                mock_ai_client.default_model = "DeepSeek-V4-Flash"
                mock_ai_client.get_usage.return_value = {
                    "total_quota": 1000,
                    "remaining": 950,
                    "rpm_limit": 30,
                }
                mock_get_client.return_value = mock_ai_client

                resp = client.get("/api/v1/ai/health")
                assert resp.status_code == 200
                data = resp.json()
                health = data["data"]["health"]
                assert health["status"] == "healthy"
                assert health["key_configured"] is True
                assert health["models_count"] == 1
                assert health["usage"]["remaining"] == 950


def test_ai_models_success(client):
    """Test GET /api/v1/ai/models returns standardized success format."""
    mock_models = [
        AIModelInfo(
            id="DeepSeek-V4-Flash",
            object="model",
            owned_by="DeepSeek",
            context_length=1048576,
            supports_streaming=True,
            supports_tools=True,
            supports_vision=False,
            supports_reasoning=True,
        ),
        AIModelInfo(
            id="MiMo-V2.6-Flash",
            object="model",
            owned_by="Xiaomi",
            context_length=1048576,
            supports_streaming=True,
            supports_tools=True,
            supports_vision=True,
            supports_reasoning=True,
        ),
    ]
    with patch("app.services.ai_service.list_models", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = mock_models
        resp = client.get("/api/v1/ai/models")
        assert resp.status_code == 200
        body = resp.json()
        assert "message" in body
        assert "success" in body["message"]
        assert body["error"] == {}
        assert len(body["data"]["models"]) == 2
        assert body["data"]["total"] == 2
        assert body["data"]["models"][0]["id"] == "DeepSeek-V4-Flash"
        assert body["data"]["models"][1]["supports_vision"] is True


def test_ai_models_unconfigured_error(client):
    """When API key is not configured, GET /api/v1/ai/models returns standardized 503 error."""
    with patch.object(settings, "AMD_API_KEY", ""):
        with patch("app.configs.amd_client.settings.AMD_API_KEY", ""):
            resp = client.get("/api/v1/ai/models")
            assert resp.status_code == 503
            body = resp.json()
            assert "error" in body["message"]
            assert "not configured" in body["message"]["error"]
            assert "ai" in body["error"]


def test_ai_chat_completions_success(client):
    """Test POST /api/v1/ai/chat/completions non-streaming success."""
    mock_response = {
        "id": "chatcmpl-test-123",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Gyros Project assistant online.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 6,
            "total_tokens": 18,
        },
    }
    with patch("app.services.ai_service.chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_response
        resp = client.post(
            "/api/v1/ai/chat/completions",
            json={
                "model": "DeepSeek-V4-Flash",
                "messages": [{"role": "user", "content": "Hello!"}],
                "stream": False,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"]["success"] == "Chat completion generated successfully"
        assert body["data"]["completion"]["id"] == "chatcmpl-test-123"


def test_ai_chat_completions_rate_limited(client):
    """Test rate limit produces 429 standardized error response without placeholder output."""
    with patch(
        "app.services.ai_service.chat_completion",
        new_callable=AsyncMock,
        side_effect=AIRateLimitException(
            message="Rate limit exceeded. Please slow down.",
            retry_after=60,
        ),
    ):
        resp = client.post(
            "/api/v1/ai/chat/completions",
            json={
                "messages": [{"role": "user", "content": "Hello!"}],
            },
        )
        assert resp.status_code == 429
        body = resp.json()
        assert "error" in body["message"]
        assert "Rate limit exceeded" in body["message"]["error"]
        assert body["error"]["retry_after"] == 60
        # Ensure never returning placeholder content
        assert "completion" not in body.get("data", {})


def test_ai_chat_completions_validation_failure(client):
    """Empty messages should fail Pydantic validation with 422."""
    resp = client.post(
        "/api/v1/ai/chat/completions",
        json={"messages": []},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["message"]["error"] == "Request validation failed"
    assert "messages" in body["error"]
