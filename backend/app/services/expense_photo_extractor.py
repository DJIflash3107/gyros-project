import base64
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from app.configs.amd_client import get_amd_client
from app.configs.settings import settings
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.exceptions import AIConfigException, ValidationException
from app.helpers.logging import logger
from app.services.ai_service import list_models
from app.services.expense_spreadsheet_parser import parse_currency_amount, parse_flexible_date


SUPPORTED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}


def clean_json_text(text: str) -> str:
    """Strip markdown code fences and whitespace from LLM JSON response."""
    text = (text or "").strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


async def extract_expenses_from_photo(
    image_bytes: bytes,
    mime_type: str,
    business_context: Optional[Dict[str, Any]] = None,
    default_date: Optional[date] = None,
    default_branch_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Extract structured expense item(s) from a receipt, invoice, or nota image using Vision AI.
    Returns (extracted_expense_rows, extraction_metadata).
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

    if not settings.AMD_API_KEY and settings.APP_ENV not in ("testing", "test"):
        raise AIConfigException(
            errors={
                "vision": "AI service is not configured. Please configure AMD_API_KEY.",
                "error_code": ErrorCodeRegistry.EXP_VISION_UNAVAILABLE,
            },
            message="Vision model is unavailable",
            error_code=ErrorCodeRegistry.EXP_VISION_UNAVAILABLE,
        )

    client = get_amd_client()

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
                    "error_code": ErrorCodeRegistry.EXP_VISION_UNAVAILABLE,
                },
                message="Vision model is unavailable",
                error_code=ErrorCodeRegistry.EXP_VISION_UNAVAILABLE,
            )

    if not vision_model:
        raise AIConfigException(
            errors={
                "vision": "No vision-capable model is available in the configured AI catalog",
                "error_code": ErrorCodeRegistry.EXP_VISION_UNAVAILABLE,
            },
            message="No vision-capable model is available",
            error_code=ErrorCodeRegistry.EXP_VISION_UNAVAILABLE,
        )

    branches_hint = ""
    if business_context and "branches" in business_context:
        branch_names = [b.get("name") for b in business_context["branches"] if b.get("name")]
        if branch_names:
            branches_hint = f"\nBusiness Branches Reference: {', '.join(branch_names)}"

    system_prompt = (
        "You are an expert document OCR and financial expense extraction system specializing in Indonesian & English receipts, invoices, bills, nota kontan, and payment vouchers.\n"
        "Your task is to analyze the provided receipt or invoice image and extract the expense information into structured JSON.\n"
        "Output a JSON object with two keys: 'summary' and 'items'.\n"
        "- 'summary' object: {\n"
        "    'merchant_name': string or null,\n"
        "    'transaction_date': 'YYYY-MM-DD' or null,\n"
        "    'total_amount': numeric value (e.g. 150000.00),\n"
        "    'currency': 'IDR',\n"
        "    'suggested_category': 'Ingredients' | 'Packaging' | 'Utilities' | 'Salaries & Wages' | 'Maintenance' | 'Marketing' | 'Rent & Facilities' | 'Operations' | 'Other',\n"
        "    'description': concise description of the purchase or invoice\n"
        "  }\n"
        "- 'items' array of line item objects (if legible items are listed): [\n"
        "    {\n"
        "      'item_name': string,\n"
        "      'qty': numeric or null,\n"
        "      'price': numeric or null,\n"
        "      'subtotal': numeric or null,\n"
        "      'category': 'Ingredients' | 'Packaging' | 'Utilities' | 'Salaries & Wages' | 'Maintenance' | 'Marketing' | 'Rent & Facilities' | 'Operations' | 'Other'\n"
        "    }\n"
        "  ]\n"
        f"{branches_hint}\n"
        "Instructions:\n"
        "1. Prioritize total amount actually paid / grand total (including tax and discounts if shown).\n"
        "2. Parse dates into YYYY-MM-DD. If year is missing, assume current year.\n"
        "3. Never hallucinate numbers. If text is blurry, provide your best estimation."
    )

    b64_img = base64.b64encode(image_bytes).decode("ascii")
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Extract all expense data, total amount, merchant, date, and line items from this receipt image into JSON.",
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
        logger.error(f"Vision model chat completion failed for expense receipt: {e}", exc_info=True)
        raise ValidationException(
            errors={
                "extraction": f"Vision extraction call failed: {str(e)}",
                "error_code": ErrorCodeRegistry.EXP_EXTRACTION_FAILED,
            },
            message="Vision model extraction failed",
            error_code=ErrorCodeRegistry.EXP_EXTRACTION_FAILED,
        )

    choices = completion.get("choices", [])
    if not choices:
        raise ValidationException(
            errors={
                "extraction": "Vision model returned empty response",
                "error_code": ErrorCodeRegistry.EXP_EXTRACTION_FAILED,
            },
            message="Vision model extraction failed",
            error_code=ErrorCodeRegistry.EXP_EXTRACTION_FAILED,
        )

    raw_content = choices[0].get("message", {}).get("content", "")
    cleaned_content = clean_json_text(raw_content)

    try:
        parsed_data = json.loads(cleaned_content)
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to decode vision model JSON for receipt: {json_err}. Raw content: {raw_content[:200]}")
        raise ValidationException(
            errors={
                "extraction": f"Vision model output could not be parsed as JSON: {str(json_err)}",
                "error_code": ErrorCodeRegistry.EXP_EXTRACTION_FAILED,
            },
            message="Vision model returned unparseable response",
            error_code=ErrorCodeRegistry.EXP_EXTRACTION_FAILED,
        )

    summary = parsed_data.get("summary") if isinstance(parsed_data, dict) else None
    line_items = parsed_data.get("items") if isinstance(parsed_data, dict) else None

    extracted_rows: List[Dict[str, Any]] = []

    # If there is a valid summary total
    if summary and isinstance(summary, dict):
        total_amt = parse_currency_amount(summary.get("total_amount"))
        merchant = summary.get("merchant_name") or ""
        t_date = parse_flexible_date(summary.get("transaction_date"), default_date or date.today())
        cat = summary.get("suggested_category") or "Operasional"
        desc = summary.get("description") or (f"Pembelian di {merchant}" if merchant else "Pengeluaran operasional")
        if merchant and merchant.lower() not in desc.lower():
            desc = f"{merchant}: {desc}"
        desc = desc[:255]

        if total_amt is not None and total_amt > Decimal("0"):
            extracted_rows.append({
                "source_row_number": 1,
                "expense_date": t_date,
                "category": cat,
                "description": desc,
                "amount": total_amt,
                "currency": summary.get("currency") or "IDR",
                "branch_id": default_branch_id,
                "confidence": 0.90,
                "raw_payload_json": parsed_data,
            })

    # If no summary was found but line items exist
    if not extracted_rows and line_items and isinstance(line_items, list):
        for idx, item in enumerate(line_items, start=1):
            if not isinstance(item, dict):
                continue
            amt = parse_currency_amount(item.get("subtotal") or item.get("price"))
            if amt is not None and amt > Decimal("0"):
                name = item.get("item_name") or f"Item {idx}"
                cat = item.get("category") or "Operasional"
                extracted_rows.append({
                    "source_row_number": idx,
                    "expense_date": default_date or date.today(),
                    "category": cat,
                    "description": name[:255],
                    "amount": amt,
                    "currency": "IDR",
                    "branch_id": default_branch_id,
                    "confidence": 0.85,
                    "raw_payload_json": item,
                })

    if not extracted_rows:
        raise ValidationException(
            errors={
                "extraction": "Vision model did not return any identifiable expense total or line items",
                "error_code": ErrorCodeRegistry.EXP_EXTRACTION_FAILED,
            },
            message="Could not extract expense from receipt image",
            error_code=ErrorCodeRegistry.EXP_EXTRACTION_FAILED,
        )

    metadata = {
        "model_used": vision_model,
        "raw_response": raw_content,
        "total_extracted": len(extracted_rows),
    }

    return extracted_rows, metadata
