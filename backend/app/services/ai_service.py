import time
from typing import Any, AsyncIterator, Dict, List, Optional, Union
from app.configs.amd_client import AMDTokenFactoryClient, get_amd_client
from app.configs.settings import settings
from app.helpers.exceptions import (
    AIConfigException,
    AIServiceException,
    ValidationException,
)
from app.helpers.logging import logger
from app.models.schemas.ai import AIHealthResponse, AIModelInfo

# Known model capability mapping from AMD Token Factory documentation
VISION_SUPPORTED_MODELS = {
    "DeepSeek-V4.1-Flash",
    "DeepSeek-V4-Flash-Vision-Exp",
    "MiMo-V2.6-Flash",
    "Qwen3.8-Flash-Next",
    "Qwen3.8-27B",
    "Gemma-4-31B-IT",
}

REASONING_BY_DEFAULT_MODELS = {
    "MiMo-V2.6-Flash",
    "GLM-5.3-Flash",
    "Qwen3.8-Flash-Next",
    "Qwen3.8-27B",
}


def _infer_capabilities(model_id: str, raw_item: Dict[str, Any]) -> Dict[str, Any]:
    """Infer capability flags from model id and raw catalog metadata."""
    is_ocr = "ocr" in model_id.lower() or "mineru" in model_id.lower()
    supports_vision = (
        model_id in VISION_SUPPORTED_MODELS
        or "vision" in model_id.lower()
        or raw_item.get("vision", False)
    )
    supports_reasoning = (
        model_id in REASONING_BY_DEFAULT_MODELS
        or "deepseek" in model_id.lower()
        or raw_item.get("reasoning", False)
    )

    # Document OCR does not support chat streaming or tools
    supports_streaming = not is_ocr
    supports_tools = not is_ocr

    return {
        "supports_streaming": supports_streaming,
        "supports_tools": supports_tools,
        "supports_vision": supports_vision,
        "supports_reasoning": supports_reasoning,
    }


async def list_models(client: Optional[AMDTokenFactoryClient] = None) -> List[AIModelInfo]:
    """
    Fetch available models from AMD Token Factory and parse into AIModelInfo models.
    """
    ai_client = client or get_amd_client()
    logger.info(f"Discovering AMD Token Factory models from {ai_client.base_url}")

    catalog_data = await ai_client.list_models()

    raw_items: List[Dict[str, Any]] = []
    if isinstance(catalog_data, dict):
        if "data" in catalog_data and isinstance(catalog_data["data"], list):
            raw_items = catalog_data["data"]
        elif "models" in catalog_data and isinstance(catalog_data["models"], list):
            raw_items = catalog_data["models"]
    elif isinstance(catalog_data, list):
        raw_items = catalog_data

    model_infos: List[AIModelInfo] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id") or item.get("name") or "unknown"
        caps = _infer_capabilities(model_id, item)

        model_info = AIModelInfo(
            id=model_id,
            object=item.get("object", "model"),
            owned_by=item.get("owned_by") or item.get("publisher"),
            created=item.get("created"),
            context_length=item.get("context_length") or item.get("context_window"),
            supports_streaming=caps["supports_streaming"],
            supports_tools=caps["supports_tools"],
            supports_vision=caps["supports_vision"],
            supports_reasoning=caps["supports_reasoning"],
            raw=item,
        )
        model_infos.append(model_info)

    logger.info(f"Discovered {len(model_infos)} models from AMD Token Factory")
    return model_infos


async def check_health(client: Optional[AMDTokenFactoryClient] = None) -> AIHealthResponse:
    """
    Perform a health check against AMD Token Factory.
    If API key is not configured, returns status='unconfigured'.
    If configured, validates connectivity and reads usage details.
    """
    ai_client = client or get_amd_client()
    key_configured = bool(ai_client.api_key and ai_client.api_key.strip())

    if not key_configured:
        logger.warning("AI health check: API key not configured")
        return AIHealthResponse(
            status="unconfigured",
            key_configured=False,
            base_url=ai_client.base_url,
            default_model=ai_client.default_model,
        )

    start_time = time.perf_counter()
    usage_info: Optional[Dict[str, Any]] = None
    rate_limits: Optional[Dict[str, Any]] = None
    models_count: Optional[int] = None

    try:
        models = await list_models(ai_client)
        models_count = len(models)
    except Exception as exc:
        latency = (time.perf_counter() - start_time) * 1000.0
        logger.error(f"AI health check failed to reach models endpoint: {exc}")
        return AIHealthResponse(
            status="unavailable",
            key_configured=True,
            base_url=ai_client.base_url,
            default_model=ai_client.default_model,
            latency_ms=round(latency, 2),
            usage={"error": str(exc)},
        )

    # Optionally attempt to read usage info
    try:
        usage_res = await ai_client.get_usage()
        if isinstance(usage_res, dict):
            usage_info = {
                "total_quota": usage_res.get("total_quota"),
                "used_amount": usage_res.get("used_amount"),
                "remaining": usage_res.get("remaining"),
                "reset_time": usage_res.get("reset_time"),
                "rpm_limit": usage_res.get("rpm_limit"),
            }
    except Exception as usage_err:
        logger.info(f"AI health check: usage details not retrieved: {usage_err}")
        # Usage endpoint optional / might be restricted on some keys

    latency = (time.perf_counter() - start_time) * 1000.0
    logger.info(f"AI health check succeeded in {latency:.2f}ms with {models_count} models")

    return AIHealthResponse(
        status="healthy",
        key_configured=True,
        base_url=ai_client.base_url,
        default_model=ai_client.default_model,
        latency_ms=round(latency, 2),
        models_count=models_count,
        usage=usage_info,
        rate_limits=rate_limits,
    )


async def chat_completion(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    client: Optional[AMDTokenFactoryClient] = None,
    **params: Any,
) -> Dict[str, Any]:
    """
    Send chat completion request to AMD Token Factory.
    Enforces that placeholder output is NEVER returned on failure.
    """
    ai_client = client or get_amd_client()
    selected_model = model or ai_client.default_model

    logger.info(f"Executing chat completion with model={selected_model}, messages_count={len(messages)}")

    result = await ai_client.chat_completion(
        model=selected_model,
        messages=messages,
        **params,
    )

    logger.info(f"Chat completion succeeded with model={selected_model}")
    return result


async def chat_completion_stream(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    client: Optional[AMDTokenFactoryClient] = None,
    **params: Any,
) -> AsyncIterator[str]:
    """
    Stream chat completion tokens from AMD Token Factory.
    """
    ai_client = client or get_amd_client()
    selected_model = model or ai_client.default_model

    logger.info(f"Starting chat stream with model={selected_model}, messages_count={len(messages)}")

    async for chunk in ai_client.chat_completion_stream(
        model=selected_model,
        messages=messages,
        **params,
    ):
        yield chunk
