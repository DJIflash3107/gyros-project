import base64
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from app.configs.amd_client import get_amd_client
from app.configs.settings import settings
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.exceptions import AIConfigException, ValidationException
from app.helpers.logging import logger
from app.services.ai_service import list_models
from app.services.semantic_mapper import CANONICAL_FIELDS


SUPPORTED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}


def clean_json_text(text: str) -> str:
    """Strip markdown code fences and whitespace from LLM JSON response."""
    text = text.strip()
    # Check for ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


async def extract_from_photo(
    image_bytes: bytes,
    mime_type: str,
    business_context: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Extract structured sales report rows from an image using a verified AMD vision model.
    Returns (extracted_rows, extraction_metadata).
    Raises AIConfigException (503) if vision is not configured/supported.
    Raises ValidationException if image size/format is invalid or extraction fails.
    """
    normalized_mime = (mime_type or "").lower().strip()
    if normalized_mime == "image/jpg":
        normalized_mime = "image/jpeg"

    if normalized_mime not in SUPPORTED_IMAGE_MIME_TYPES:
        raise ValidationException(
            errors={
                "file": f"Unsupported image format: {mime_type}. Supported: JPEG, PNG, WEBP",
                "error_code": ErrorCodeRegistry.RPT_UNSUPPORTED_FORMAT,
            },
            message="Unsupported image format",
            error_code=ErrorCodeRegistry.RPT_UNSUPPORTED_FORMAT,
        )

    max_bytes = settings.VISION_MAX_IMAGE_SIZE_MB * 1024 * 1024
    if len(image_bytes) > max_bytes:
        raise ValidationException(
            errors={
                "file": f"Image size exceeds maximum limit of {settings.VISION_MAX_IMAGE_SIZE_MB}MB",
                "error_code": ErrorCodeRegistry.RPT_IMAGE_TOO_LARGE,
            },
            message="Image exceeds size limit",
            error_code=ErrorCodeRegistry.RPT_IMAGE_TOO_LARGE,
        )

    # Check AMD API key configuration
    if not settings.AMD_API_KEY and settings.APP_ENV not in ("testing", "test"):
        raise AIConfigException(
            errors={
                "vision": "AI service is not configured. Please configure AMD_API_KEY.",
                "error_code": ErrorCodeRegistry.RPT_VISION_UNAVAILABLE,
            },
            message="Vision model is unavailable",
            error_code=ErrorCodeRegistry.RPT_VISION_UNAVAILABLE,
        )

    client = get_amd_client()

    # Discover vision-capable model
    vision_model = settings.VISION_MODEL_OVERRIDE
    if not vision_model:
        try:
            models = await list_models(client)
            for m in models:
                if getattr(m, "supports_vision", False):
                    vision_model = m.id
                    break
        except Exception as e:
            logger.error(f"Failed to query AI models for vision support: {e}")
            raise AIConfigException(
                errors={
                    "vision": f"Failed to discover vision models: {str(e)}",
                    "error_code": ErrorCodeRegistry.RPT_VISION_UNAVAILABLE,
                },
                message="Vision model is unavailable",
                error_code=ErrorCodeRegistry.RPT_VISION_UNAVAILABLE,
            )

    if not vision_model:
        raise AIConfigException(
            errors={
                "vision": "No vision-capable model is available in the configured AI catalog",
                "error_code": ErrorCodeRegistry.RPT_VISION_UNAVAILABLE,
            },
            message="No vision-capable model is available",
            error_code=ErrorCodeRegistry.RPT_VISION_UNAVAILABLE,
        )

    # Build prompt with business context for accurate grounding
    catalog_hint = ""
    if business_context and "products" in business_context:
        prod_names = [p.get("name") for p in business_context["products"] if p.get("name")]
        if prod_names:
            catalog_hint = f"\nBusiness Product Catalog Reference: {', '.join(prod_names[:50])}"

    field_lines = "\n".join(
        f"- {field}: {desc}" for field, desc in CANONICAL_FIELDS.items() if field != "_skip"
    )

    system_prompt = (
        "You are an expert document OCR and tabular data extraction system for sales reports and stock sheets.\n"
        "Your task is to analyze the provided sales report image and extract all line items into structured JSON.\n"
        "Output a JSON object with a single key 'rows' containing an array of objects.\n"
        "Each row object may have the following fields (omit or set to null if not clearly visible):\n"
        f"{field_lines}\n"
        f"{catalog_hint}\n"
        "Never fabricate numbers. If handwriting is ambiguous, extract the best estimation."
    )

    b64_img = base64.b64encode(image_bytes).decode("ascii")
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Extract all tabular sales report items from this image into JSON format.",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{normalized_mime};base64,{b64_img}"},
                },
            ],
        },
    ]

    try:
        completion = await client.chat_completion(
            model=vision_model,
            messages=messages,
            temperature=settings.VISION_EXTRACTION_TEMPERATURE,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.error(f"Vision model chat completion failed: {e}", exc_info=True)
        raise ValidationException(
            errors={
                "extraction": f"Vision extraction call failed: {str(e)}",
                "error_code": ErrorCodeRegistry.RPT_EXTRACTION_FAILED,
            },
            message="Vision model extraction failed",
            error_code=ErrorCodeRegistry.RPT_EXTRACTION_FAILED,
        )

    choices = completion.get("choices", [])
    if not choices:
        raise ValidationException(
            errors={
                "extraction": "Vision model returned empty choices",
                "error_code": ErrorCodeRegistry.RPT_EXTRACTION_FAILED,
            },
            message="Vision model extraction failed",
            error_code=ErrorCodeRegistry.RPT_EXTRACTION_FAILED,
        )

    raw_content = choices[0].get("message", {}).get("content", "")
    cleaned_content = clean_json_text(raw_content)

    try:
        parsed_data = json.loads(cleaned_content)
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to decode vision model JSON: {json_err}. Raw content: {raw_content[:200]}")
        raise ValidationException(
            errors={
                "extraction": f"Vision model output could not be parsed as JSON: {str(json_err)}",
                "error_code": ErrorCodeRegistry.RPT_EXTRACTION_FAILED,
            },
            message="Vision model returned unparseable response",
            error_code=ErrorCodeRegistry.RPT_EXTRACTION_FAILED,
        )

    rows: List[Dict[str, Any]] = []
    if isinstance(parsed_data, list):
        rows = parsed_data
    elif isinstance(parsed_data, dict):
        for candidate_key in ("rows", "data", "items", "sales_reports", "observations"):
            if candidate_key in parsed_data and isinstance(parsed_data[candidate_key], list):
                rows = parsed_data[candidate_key]
                break
        if not rows and any(isinstance(v, dict) for v in parsed_data.values()):
            rows = [v for v in parsed_data.values() if isinstance(v, dict)]

    if not rows:
        raise ValidationException(
            errors={
                "extraction": "Vision model did not return any identifiable row items",
                "error_code": ErrorCodeRegistry.RPT_EXTRACTION_FAILED,
            },
            message="Vision model returned unparseable response",
            error_code=ErrorCodeRegistry.RPT_EXTRACTION_FAILED,
        )

    # Attach confidence metadata and index
    for idx, r in enumerate(rows, start=1):
        r["source_row_number"] = idx
        r["extraction_confidence_json"] = {
            "model": vision_model,
            "confidence": 0.85,
        }

    metadata = {
        "model_used": vision_model,
        "raw_response": raw_content,
        "total_extracted": len(rows),
    }

    return rows, metadata
