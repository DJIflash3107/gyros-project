import asyncio
import json
import random
from typing import Any, AsyncIterator, Dict, List, Optional, Union
import httpx
from app.configs.settings import settings
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.exceptions import (
    AppException,
    AIConfigException,
    AIRateLimitException,
    AIServiceException,
    AuthenticationException,
    AuthorizationException,
    ValidationException,
)
from app.helpers.logging import logger


class AMDTokenFactoryClient:
    """
    Reusable HTTP client for AMD Radeon Cloud Token Factory API.
    Handles authentication, exponential backoff with jitter on 429/502/503,
    error parsing across gateway and platform error formats, streaming, and connection pooling.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[int] = None,
        stream_chunk_timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        self.base_url = (base_url or settings.AMD_API_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.AMD_API_KEY
        self.default_model = default_model or settings.AMD_DEFAULT_MODEL
        self.timeout = timeout if timeout is not None else settings.AMD_REQUEST_TIMEOUT
        self.stream_chunk_timeout = (
            stream_chunk_timeout
            if stream_chunk_timeout is not None
            else settings.AMD_STREAM_CHUNK_TIMEOUT
        )
        self.max_retries = (
            max_retries if max_retries is not None else settings.AMD_MAX_RETRIES
        )
        self._http_client: Optional[httpx.AsyncClient] = None

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(
                    timeout=float(self.timeout),
                    connect=30.0,
                    read=float(self.timeout),
                    write=30.0,
                ),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._http_client

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    def _ensure_api_key(self) -> str:
        """Check that API key is configured."""
        if not self.api_key or not self.api_key.strip():
            logger.warning("AMD Token Factory API key is not configured")
            raise AIConfigException(
                message="AMD Token Factory API key is not configured. Please set AMD_API_KEY in environment."
            )
        return self.api_key.strip()

    def _build_auth_headers(self) -> Dict[str, str]:
        """Construct authorization headers."""
        key = self._ensure_api_key()
        return {"Authorization": f"Bearer {key}"}

    def _parse_error_body(self, response: httpx.Response) -> Dict[str, Any]:
        """
        Parse error response supporting both OpenAI gateway format:
          {"error": {"message": ..., "type": ..., "code": ...}}
        and AMD platform layer format:
          {"detail": {"error": {"message": ...}}} or {"detail": "..."}
        """
        try:
            body = response.json()
        except Exception:
            return {"message": response.text or f"HTTP {response.status_code}"}

        if isinstance(body, dict):
            # Check for OpenAI gateway shape: {"error": {...}}
            if "error" in body:
                err = body["error"]
                if isinstance(err, dict):
                    return {
                        "message": err.get("message") or str(err),
                        "code": err.get("code"),
                        "type": err.get("type"),
                        "raw": body,
                    }
                return {"message": str(err), "raw": body}

            # Check for AMD platform shape: {"detail": {"error": {...}}}
            if "detail" in body:
                detail = body["detail"]
                if isinstance(detail, dict) and "error" in detail:
                    err = detail["error"]
                    if isinstance(err, dict):
                        return {
                            "message": err.get("message") or str(err),
                            "code": err.get("code"),
                            "type": err.get("type"),
                            "raw": body,
                        }
                    return {"message": str(err), "raw": body}
                if isinstance(detail, str):
                    return {"message": detail, "raw": body}
                return {"message": str(detail), "raw": body}

        return {"message": str(body), "raw": body}

    def _handle_response_error(self, response: httpx.Response) -> None:
        """Map HTTP error status codes to standardized Gyros AppException types."""
        err_info = self._parse_error_body(response)
        msg = err_info.get("message") or f"AMD API request failed with status {response.status_code}"
        status_code = response.status_code
        req_url = str(response._request.url) if getattr(response, "_request", None) is not None else "-"

        logger.error(
            f"AMD API error response: status={status_code}, url={req_url}, error={err_info}"
        )

        if status_code == 400:
            raise ValidationException(
                message=msg,
                errors={"amd": msg, "details": err_info},
                error_code=ErrorCodeRegistry.AI_BAD_REQUEST,
            )
        elif status_code == 401:
            raise AuthenticationException(
                message="Invalid or missing AMD Token Factory credentials",
                errors={"amd": msg},
                error_code=ErrorCodeRegistry.AI_AUTH_FAILED,
            )
        elif status_code == 403:
            raise AuthorizationException(
                message=f"AMD Token Factory authorization failed: {msg}",
                errors={"amd": msg},
                error_code=ErrorCodeRegistry.AI_FORBIDDEN,
            )
        elif status_code == 422:
            raise ValidationException(
                message=f"AMD Token Factory rejected request body: {msg}",
                errors={"amd": msg, "details": err_info},
                error_code=ErrorCodeRegistry.AI_BAD_REQUEST,
            )
        elif status_code == 429:
            retry_after_str = response.headers.get("Retry-After")
            retry_after_int = None
            if retry_after_str:
                try:
                    retry_after_int = int(float(retry_after_str))
                except ValueError:
                    pass
            raise AIRateLimitException(
                message=f"AMD Token Factory rate limit exceeded: {msg}",
                retry_after=retry_after_int,
                errors={"amd": msg, "retry_after": retry_after_str},
            )
        elif status_code in (502, 503, 504):
            raise AIServiceException(
                status_code=502,
                message=f"AMD Token Factory service unavailable ({status_code}): {msg}",
                errors={"amd": msg},
                error_code=ErrorCodeRegistry.AI_PROVIDER_ERROR,
            )
        else:
            raise AIServiceException(
                status_code=status_code if 400 <= status_code < 600 else 500,
                message=f"AMD Token Factory error ({status_code}): {msg}",
                errors={"amd": msg},
                error_code=ErrorCodeRegistry.AI_PROVIDER_ERROR,
            )

    async def _execute_with_retry(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """
        Execute an HTTP request with exponential backoff and jitter on 429, 502, 503.
        Non-retryable status codes (400, 401, 403, 404, 422) fail immediately.
        """
        client = self._get_http_client()
        merged_headers = self._build_auth_headers()
        if headers:
            merged_headers.update(headers)

        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await client.request(
                    method=method,
                    url=path,
                    params=params,
                    json=json_data,
                    headers=merged_headers,
                )

                # If status is retryable (429, 502, 503) and we haven't exhausted attempts
                if response.status_code in (429, 502, 503) and attempt < self.max_retries:
                    retry_after_header = response.headers.get("Retry-After")
                    delay = None
                    if retry_after_header:
                        try:
                            delay = float(retry_after_header)
                        except ValueError:
                            pass

                    if delay is None or delay <= 0:
                        # Exponential backoff with jitter: base * 2^attempt + jitter
                        jitter = random.uniform(0.1, 0.5)
                        delay = min((1.0 * (2 ** attempt)) + jitter, 60.0)

                    logger.warning(
                        f"AMD API returned {response.status_code} on attempt {attempt + 1}/{self.max_retries + 1}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                    continue

                # Check if response status indicates an error
                if response.is_error:
                    self._handle_response_error(response)

                return response

            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as net_err:
                last_exception = net_err
                if attempt < self.max_retries:
                    jitter = random.uniform(0.1, 0.5)
                    delay = min((1.0 * (2 ** attempt)) + jitter, 30.0)
                    logger.warning(
                        f"AMD API network error ({type(net_err).__name__}) on attempt {attempt + 1}/{self.max_retries + 1}: {net_err}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"AMD API connection failure after {self.max_retries + 1} attempts: {net_err}")
                raise AIServiceException(
                    status_code=503,
                    message=f"Failed to connect to AMD Token Factory service: {str(net_err)}",
                    errors={"connection": str(net_err)},
                    error_code=ErrorCodeRegistry.AI_CONNECTION_ERROR,
                ) from net_err

        # Retries exhausted with an error response
        if response.is_error:
            self._handle_response_error(response)
        return response

    async def list_models(self) -> Dict[str, Any]:
        """
        Fetch available model catalog from GET /models (or /v1/models depending on base_url).
        """
        response = await self._execute_with_retry("GET", "/models")
        return response.json()

    async def get_usage(self) -> Dict[str, Any]:
        """
        Fetch remaining usage and quota info from GET /usage?include_recent=true.
        """
        response = await self._execute_with_retry("GET", "/usage", params={"include_recent": "true"})
        return response.json()

    async def chat_completion(
        self,
        model: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        *,
        stream: bool = False,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        response_format: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        parallel_tool_calls: Optional[bool] = None,
        reasoning_effort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a non-streaming chat completion request to POST /chat/completions.
        Filters payload to fields accepted by AMD gateway.
        """
        payload: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages or [],
            "stream": stream,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if presence_penalty is not None:
            payload["presence_penalty"] = presence_penalty
        if frequency_penalty is not None:
            payload["frequency_penalty"] = frequency_penalty
        if response_format is not None:
            payload["response_format"] = response_format
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if parallel_tool_calls is not None:
            payload["parallel_tool_calls"] = parallel_tool_calls
        if reasoning_effort is not None:
            payload["reasoning_effort"] = reasoning_effort

        response = await self._execute_with_retry("POST", "/chat/completions", json_data=payload)
        return response.json()

    async def chat_completion_stream(
        self,
        model: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        *,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        response_format: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        parallel_tool_calls: Optional[bool] = None,
        reasoning_effort: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Stream chat completion chunks from POST /chat/completions.
        Yields raw SSE line / chunk strings ending when [DONE] is encountered.
        """
        payload: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages or [],
            "stream": True,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if presence_penalty is not None:
            payload["presence_penalty"] = presence_penalty
        if frequency_penalty is not None:
            payload["frequency_penalty"] = frequency_penalty
        if response_format is not None:
            payload["response_format"] = response_format
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if parallel_tool_calls is not None:
            payload["parallel_tool_calls"] = parallel_tool_calls
        if reasoning_effort is not None:
            payload["reasoning_effort"] = reasoning_effort

        client = self._get_http_client()
        headers = self._build_auth_headers()
        headers["Accept"] = "text/event-stream"

        try:
            # Note: 10 minutes timeout per streaming chunk gap per documentation
            stream_timeout = httpx.Timeout(
                timeout=float(self.stream_chunk_timeout),
                connect=30.0,
                read=float(self.stream_chunk_timeout),
                write=30.0,
            )
            async with client.stream(
                "POST",
                "/chat/completions",
                json=payload,
                headers=headers,
                timeout=stream_timeout,
            ) as response:
                if response.is_error:
                    await response.aread()
                    self._handle_response_error(response)

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_content = line[6:].strip()
                        if data_content == "[DONE]":
                            break
                        yield data_content
                    else:
                        yield line
        except (httpx.ConnectError, httpx.ReadTimeout) as stream_err:
            logger.error(f"Streaming connection error: {stream_err}")
            raise AIServiceException(
                status_code=504,
                message=f"AMD streaming connection failed or timed out: {str(stream_err)}",
                errors={"streaming": str(stream_err)},
                error_code=ErrorCodeRegistry.AI_CONNECTION_ERROR,
            ) from stream_err


# Singleton instance and getter
_amd_client_instance: Optional[AMDTokenFactoryClient] = None


def get_amd_client() -> AMDTokenFactoryClient:
    """Return singleton AMDTokenFactoryClient instance."""
    global _amd_client_instance
    if _amd_client_instance is None:
        _amd_client_instance = AMDTokenFactoryClient()
    return _amd_client_instance


async def close_amd_client() -> None:
    """Close singleton client if open."""
    global _amd_client_instance
    if _amd_client_instance is not None:
        await _amd_client_instance.close()
        _amd_client_instance = None
