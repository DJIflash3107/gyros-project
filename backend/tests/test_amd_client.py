import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
import pytest
from app.configs.amd_client import AMDTokenFactoryClient
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.exceptions import (
    AIConfigException,
    AIRateLimitException,
    AIServiceException,
    AuthenticationException,
    AuthorizationException,
    ValidationException,
)


@pytest.mark.asyncio
async def test_client_missing_api_key_raises_config_exception():
    client = AMDTokenFactoryClient(api_key="")
    with pytest.raises(AIConfigException) as exc_info:
        await client.list_models()
    assert "not configured" in exc_info.value.message
    assert exc_info.value.error_code == ErrorCodeRegistry.AI_NOT_CONFIGURED


@pytest.mark.asyncio
async def test_client_auth_header():
    client = AMDTokenFactoryClient(api_key="rc-1234567890abcdef1234567890abcdef1234567890abcdef")
    headers = client._build_auth_headers()
    assert headers["Authorization"] == "Bearer rc-1234567890abcdef1234567890abcdef1234567890abcdef"


@pytest.mark.asyncio
async def test_parse_gateway_error_format():
    client = AMDTokenFactoryClient(api_key="rc-test")
    raw_error = {
        "error": {
            "message": "Requested model DeepSeek-V3 not supported",
            "type": "invalid_request_error",
            "code": "model_not_found",
        }
    }
    mock_resp = httpx.Response(
        status_code=400,
        content=json.dumps(raw_error).encode(),
        headers={"content-type": "application/json"},
    )
    with pytest.raises(ValidationException) as exc_info:
        client._handle_response_error(mock_resp)
    assert "Requested model DeepSeek-V3 not supported" in exc_info.value.message
    assert exc_info.value.error_code == ErrorCodeRegistry.AI_BAD_REQUEST


@pytest.mark.asyncio
async def test_parse_platform_error_format():
    client = AMDTokenFactoryClient(api_key="rc-test")
    raw_error = {
        "detail": {
            "error": {
                "message": "Account review pending",
                "code": "account_not_verified",
            }
        }
    }
    mock_resp = httpx.Response(
        status_code=403,
        content=json.dumps(raw_error).encode(),
        headers={"content-type": "application/json"},
    )
    with pytest.raises(AuthorizationException) as exc_info:
        client._handle_response_error(mock_resp)
    assert "Account review pending" in exc_info.value.message
    assert exc_info.value.error_code == ErrorCodeRegistry.AI_FORBIDDEN


@pytest.mark.asyncio
async def test_rate_limit_exception_with_retry_after():
    client = AMDTokenFactoryClient(api_key="rc-test")
    mock_resp = httpx.Response(
        status_code=429,
        content=b'{"error": {"message": "Rate limit exceeded. Slow down."}}',
        headers={"content-type": "application/json", "Retry-After": "60"},
    )
    with pytest.raises(AIRateLimitException) as exc_info:
        client._handle_response_error(mock_resp)
    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == 60
    assert exc_info.value.error_code == ErrorCodeRegistry.AI_RATE_LIMITED


@pytest.mark.asyncio
async def test_status_401_maps_to_auth_exception():
    client = AMDTokenFactoryClient(api_key="rc-invalid")
    mock_resp = httpx.Response(
        status_code=401,
        content=b'{"error": {"message": "Invalid API key"}}',
        headers={"content-type": "application/json"},
    )
    with pytest.raises(AuthenticationException) as exc_info:
        client._handle_response_error(mock_resp)
    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == ErrorCodeRegistry.AI_AUTH_FAILED


@pytest.mark.asyncio
async def test_retry_on_429_then_succeed():
    client = AMDTokenFactoryClient(api_key="rc-test", max_retries=2)
    resp_429 = httpx.Response(
        status_code=429,
        content=b'{"error": {"message": "Rate limited"}}',
        headers={"content-type": "application/json", "Retry-After": "0.01"},
    )
    resp_200 = httpx.Response(
        status_code=200,
        content=b'{"object": "list", "data": [{"id": "DeepSeek-V4-Flash"}]}',
        headers={"content-type": "application/json"},
    )

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(side_effect=[resp_429, resp_200])
    mock_http.is_closed = False

    with patch.object(client, "_get_http_client", return_value=mock_http):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            res = await client.list_models()
            assert res["data"][0]["id"] == "DeepSeek-V4-Flash"
            assert mock_http.request.call_count == 2
            mock_sleep.assert_called_once()


@pytest.mark.asyncio
async def test_no_retry_on_400():
    client = AMDTokenFactoryClient(api_key="rc-test", max_retries=3)
    resp_400 = httpx.Response(
        status_code=400,
        content=b'{"error": {"message": "Bad request"}}',
        headers={"content-type": "application/json"},
    )

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=resp_400)
    mock_http.is_closed = False

    with patch.object(client, "_get_http_client", return_value=mock_http):
        with pytest.raises(ValidationException):
            await client.list_models()
        # Should NOT retry 400
        assert mock_http.request.call_count == 1


@pytest.mark.asyncio
async def test_connection_error_raises_service_exception():
    client = AMDTokenFactoryClient(api_key="rc-test", max_retries=1)

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_http.is_closed = False

    with patch.object(client, "_get_http_client", return_value=mock_http):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(AIServiceException) as exc_info:
                await client.list_models()
            assert exc_info.value.error_code == ErrorCodeRegistry.AI_CONNECTION_ERROR
            assert "Failed to connect" in exc_info.value.message


@pytest.mark.asyncio
async def test_chat_completion_payload_structure():
    client = AMDTokenFactoryClient(api_key="rc-test", default_model="DeepSeek-V4-Flash")
    resp_200 = httpx.Response(
        status_code=200,
        content=b'{"id": "chat-123", "choices": [{"message": {"role": "assistant", "content": "Hello!"}}]}',
        headers={"content-type": "application/json"},
    )

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=resp_200)
    mock_http.is_closed = False

    with patch.object(client, "_get_http_client", return_value=mock_http):
        result = await client.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            temperature=0.7,
            max_tokens=100,
        )
        assert result["id"] == "chat-123"
        call_kwargs = mock_http.request.call_args.kwargs
        json_body = call_kwargs["json"]
        assert json_body["model"] == "DeepSeek-V4-Flash"
        assert json_body["temperature"] == 0.7
        assert json_body["max_tokens"] == 100
        assert json_body["stream"] is False
