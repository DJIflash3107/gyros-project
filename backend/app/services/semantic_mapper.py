import json
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.configs.amd_client import AMDTokenFactoryClient, get_amd_client
from app.configs.settings import settings
from app.helpers.logging import logger
from app.services.input_profiler import SpreadsheetProfile, profile_to_prompt_text

# Canonical target fields for sales reports
CANONICAL_FIELDS: Dict[str, str] = {
    "raw_product_name": "Product name or item name",
    "product_id": "Numeric product identifier",
    "branch_id": "Branch/outlet/store identifier",
    "period_start": "Report period start date",
    "period_end": "Report period end date",
    "granularity": "Period type: daily, weekly, monthly, custom_range",
    "prepared_qty": "Quantity prepared/produced",
    "opening_stock_qty": "Opening/beginning stock quantity",
    "received_qty": "Quantity received/incoming",
    "available_stock_qty": "Total available stock",
    "sold_qty": "Quantity sold",
    "leftover_qty": "Leftover/remaining/closing stock",
    "spoiled_qty": "Spoiled/expired quantity",
    "damaged_qty": "Damaged quantity",
    "staff_meals_qty": "Staff meals/employee consumption",
    "donated_qty": "Donated quantity",
    "other_disposition_qty": "Other disposition/write-off",
    "recorded_revenue": "Total revenue/sales amount/omzet",
    "_skip": "Column contains no mappable sales report data (e.g. row numbers, notes)",
}


class ColumnMappingEntry(BaseModel):
    source_column: str
    target_field: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reasoning: Optional[str] = None


class SemanticMappingResult(BaseModel):
    mappings: List[ColumnMappingEntry]
    unmapped_columns: List[str] = []
    warnings: List[str] = []
    model_used: str
    fallback_used: bool = False


def clean_json_text(text: str) -> str:
    """Strip markdown code fences and surrounding whitespace."""
    text = (text or "").strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


def build_fallback_mapping(headers: List[str], reason: str = "Fallback to static mapping") -> SemanticMappingResult:
    """Construct a mapping result using the deterministic static COLUMN_MAPPING."""
    from app.services.spreadsheet_parser import COLUMN_MAPPING

    mappings: List[ColumnMappingEntry] = []
    unmapped: List[str] = []

    for h in headers:
        clean = re.sub(r"[^a-zA-Z0-9]+", "_", str(h).strip().lower()).strip("_")
        target = COLUMN_MAPPING.get(clean)
        if target:
            mappings.append(
                ColumnMappingEntry(
                    source_column=h,
                    target_field=target,
                    confidence=1.0,
                    reasoning="Matched via static column mapping dictionary",
                )
            )
        else:
            mappings.append(
                ColumnMappingEntry(
                    source_column=h,
                    target_field="_skip",
                    confidence=0.5,
                    reasoning="No static rule matched",
                )
            )
            unmapped.append(h)

    return SemanticMappingResult(
        mappings=mappings,
        unmapped_columns=unmapped,
        warnings=[reason] if reason else [],
        model_used="static_fallback",
        fallback_used=True,
    )


async def map_columns_with_llm(
    profile: SpreadsheetProfile,
    business_context: Optional[Dict[str, Any]] = None,
    client: Optional[AMDTokenFactoryClient] = None,
) -> SemanticMappingResult:
    """
    Send spreadsheet profile to AMD Token Factory LLM for semantic column mapping.
    Gracefully falls back to static COLUMN_MAPPING on missing configuration or errors.
    """
    if not settings.SEMANTIC_MAPPING_ENABLED:
        logger.info("Semantic mapping is disabled; using static column mapping.")
        return build_fallback_mapping(profile.headers, reason="Semantic mapping disabled by configuration")

    if not settings.AMD_API_KEY:
        logger.info("AMD_API_KEY not configured; using static column mapping fallback.")
        return build_fallback_mapping(profile.headers, reason="AMD API key not configured")

    model = settings.SEMANTIC_MAPPING_MODEL or settings.AMD_DEFAULT_MODEL

    canonical_desc = "\n".join(f"- {field}: {desc}" for field, desc in CANONICAL_FIELDS.items())
    system_prompt = (
        "You are a data schema mapping expert for retail and food-service businesses, with specialized knowledge of Indonesian and English business terminology.\n"
        "Your task is to analyze a spreadsheet's structural profile and map each source column header to exactly one canonical sales report field.\n\n"
        "Canonical Target Fields:\n"
        f"{canonical_desc}\n\n"
        "Instructions & Rules:\n"
        "1. Map each source header in the profile to the single best matching canonical field name, or '_skip' if irrelevant/unmappable.\n"
        "2. Support Indonesian business terms: e.g., 'Nama Barang' / 'Menu' / 'Item' -> raw_product_name; 'Terjual' / 'Laku' / 'Qty' -> sold_qty; 'Sisa' / 'Stok Akhir' -> leftover_qty; 'Stok Awal' -> opening_stock_qty; 'Omzet' / 'Total Pendapatan' / 'Subtotal' -> recorded_revenue; 'Basi' -> spoiled_qty; 'Rusak' -> damaged_qty; 'Makan Karyawan' -> staff_meals_qty; 'Tanggal' -> period_start.\n"
        "3. Support English terms: e.g., 'Product' -> raw_product_name, 'Sold' / 'Qty Sold' -> sold_qty, 'Revenue' / 'Amount' -> recorded_revenue, 'Branch' -> branch_id.\n"
        "4. Use data types and sample values to disambiguate. For example, columns with dates suggest period_start/period_end; numbers suggest quantities or amounts.\n"
        "5. For each mapping, assign a confidence score between 0.0 and 1.0:\n"
        "   - 0.8 to 1.0: Very confident / clear match.\n"
        "   - 0.5 to 0.79: Probable match, some ambiguity.\n"
        "   - Below 0.5: Weak guess or low confidence.\n"
        "6. If a column represents row numbers, indices, notes, comments, or unmappable details, set target_field to '_skip'.\n"
        "7. Return JSON ONLY with the exact schema:\n"
        "{\n"
        '  "mappings": [\n'
        '    {"source_column": "<original header>", "target_field": "<canonical_field_or__skip>", "confidence": 0.95, "reasoning": "<brief reasoning>"}\n'
        "  ],\n"
        '  "unmapped_columns": ["<source_column if not mapped or skipped>"],\n'
        '  "warnings": ["<notes on any ambiguous columns>"]\n'
        "}"
    )

    profile_text = profile_to_prompt_text(profile)
    if business_context and business_context.get("products"):
        prod_names = [p.get("name") for p in business_context["products"] if p.get("name")]
        if prod_names:
            profile_text += f"\n\nContext - Known Business Products:\n{', '.join(prod_names[:50])}"

    user_prompt = f"Map the columns from this spreadsheet profile to the canonical schema:\n\n{profile_text}"

    close_client = False
    if client is None:
        client = AMDTokenFactoryClient()
        close_client = True

    try:
        completion = await client.chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.SEMANTIC_MAPPING_TEMPERATURE,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.warning(f"Semantic mapping LLM call failed: {e}. Falling back to static mapping.")
        return build_fallback_mapping(profile.headers, reason=f"LLM call error: {str(e)}")
    finally:
        if close_client and client is not None:
            try:
                await client.close()
            except Exception:
                pass

    raw_content = ""
    if isinstance(completion, dict):
        choices = completion.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            raw_content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
    else:
        choices = getattr(completion, "choices", [])
        if choices:
            msg = getattr(choices[0], "message", None)
            raw_content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")

    cleaned = clean_json_text(raw_content)
    try:
        data = json.loads(cleaned)
    except Exception as e:
        logger.warning(f"Failed to parse LLM mapping JSON: {e}. Raw: {raw_content[:200]}. Falling back to static mapping.")
        return build_fallback_mapping(profile.headers, reason=f"Invalid JSON returned: {str(e)}")

    mappings_list = data.get("mappings", []) if isinstance(data, dict) else []
    unmapped_list = data.get("unmapped_columns", []) if isinstance(data, dict) else []
    warnings_list = data.get("warnings", []) if isinstance(data, dict) else []

    mapped_headers = set()
    mappings: List[ColumnMappingEntry] = []

    for item in mappings_list:
        if not isinstance(item, dict):
            continue
        src = str(item.get("source_column", "")).strip()
        tgt = str(item.get("target_field", "")).strip()
        if not src:
            continue

        if tgt not in CANONICAL_FIELDS:
            if tgt in ("skip", "none", "null", "ignore", ""):
                tgt = "_skip"
            else:
                tgt = "_skip"

        try:
            conf = float(item.get("confidence", 0.8))
        except (ValueError, TypeError):
            conf = 0.8
        conf = max(0.0, min(1.0, conf))

        mapped_headers.add(src.lower())
        mappings.append(
            ColumnMappingEntry(
                source_column=src,
                target_field=tgt,
                confidence=conf,
                reasoning=item.get("reasoning"),
            )
        )

    # Ensure all original headers are present in mappings
    for h in profile.headers:
        if h.lower() not in mapped_headers:
            mappings.append(
                ColumnMappingEntry(
                    source_column=h,
                    target_field="_skip",
                    confidence=0.0,
                    reasoning="Header omitted from LLM response",
                )
            )
            if h not in unmapped_list:
                unmapped_list.append(h)

    return SemanticMappingResult(
        mappings=mappings,
        unmapped_columns=unmapped_list,
        warnings=warnings_list,
        model_used=model,
        fallback_used=False,
    )
