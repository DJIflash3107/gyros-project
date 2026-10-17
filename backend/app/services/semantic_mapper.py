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
    "unit_price": "Unit selling price / harga satuan / harga jual per item",
    "unit_cost": "Unit cost / HPP / harga modal / harga pokok / harga beli per item",
    "_skip": "Column contains no mappable sales report data (e.g. row numbers, notes)",
}

# Canonical target fields for expenses
CANONICAL_EXPENSE_FIELDS: Dict[str, str] = {
    "expense_date": "Transaction / expense date (e.g., Tanggal, Date, Tgl, Waktu, Transaksi)",
    "category": "Expense category / budget post / account type (e.g., Kategori, Jenis Biaya, Pos Biaya, Akun)",
    "description": "Expense description, line item name, payee or purpose (e.g., Keterangan, Deskripsi, Uraian, Item, Rincian, Keperluan)",
    "amount": "Expense amount / total / cost / nominal paid (e.g., Jumlah, Nominal, Total, Biaya, Pengeluaran, Debit, Tagihan)",
    "branch_id": "Branch / outlet / store location identifier or name (e.g., Cabang, Branch, Outlet, Lokasi)",
    "currency": "Currency code (e.g., Mata Uang, Currency, IDR)",
    "_skip": "Column contains non-expense metadata, row index, notes or irrelevant data",
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


class SheetClassification(BaseModel):
    sheet_name: str
    role: str = "sales"  # "sales", "reference", "instructional", "expenses", "ambiguous"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reasoning: Optional[str] = None


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


def build_fallback_expense_mapping(
    headers: List[str],
    reason: str = "Fallback to static expense mapping",
) -> SemanticMappingResult:
    """Construct an expense mapping result using the deterministic static CANONICAL_EXPENSE_HEADERS."""
    from app.services.expense_spreadsheet_parser import CANONICAL_EXPENSE_HEADERS

    mappings: List[ColumnMappingEntry] = []
    unmapped: List[str] = []

    for h in headers:
        clean = re.sub(r"[^a-zA-Z0-9]+", "_", str(h).strip().lower()).strip("_")
        target = CANONICAL_EXPENSE_HEADERS.get(clean)
        if target:
            mappings.append(
                ColumnMappingEntry(
                    source_column=h,
                    target_field=target,
                    confidence=1.0,
                    reasoning="Matched via static expense header dictionary",
                )
            )
        else:
            mappings.append(
                ColumnMappingEntry(
                    source_column=h,
                    target_field="_skip",
                    confidence=0.5,
                    reasoning="No static expense rule matched",
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


async def map_expense_columns_with_llm(
    profile: SpreadsheetProfile,
    business_context: Optional[Dict[str, Any]] = None,
    client: Optional[AMDTokenFactoryClient] = None,
) -> SemanticMappingResult:
    """
    Send expense spreadsheet profile to AMD Token Factory LLM for semantic column mapping.
    This is the PRIMARY method for resolving expense columns. Falls back to static mapping if AI is disabled or fails.
    """
    if not settings.SEMANTIC_MAPPING_ENABLED:
        logger.info("Semantic mapping is disabled; using static expense mapping fallback.")
        return build_fallback_expense_mapping(profile.headers, reason="Semantic mapping disabled by configuration")

    if not settings.AMD_API_KEY:
        logger.info("AMD_API_KEY not configured; using static expense mapping fallback.")
        return build_fallback_expense_mapping(profile.headers, reason="AMD API key not configured")

    model = settings.SEMANTIC_MAPPING_MODEL or settings.AMD_DEFAULT_MODEL

    canonical_desc = "\n".join(f"- {field}: {desc}" for field, desc in CANONICAL_EXPENSE_FIELDS.items())
    system_prompt = (
        "You are an expert financial schema mapping assistant specializing in Indonesian and English retail, restaurant, and F&B business bookkeeping.\n"
        "Your task is to analyze an expense spreadsheet profile (headers, sample rows, inferred data types) and map each source column header to exactly one canonical expense field.\n\n"
        "Canonical Expense Target Fields:\n"
        f"{canonical_desc}\n\n"
        "Instructions & Rules:\n"
        "1. Map each source header in the profile to the single best matching canonical field name, or '_skip' if irrelevant/unmappable.\n"
        "2. Recognize Indonesian terms: e.g. 'Tanggal' / 'Tgl' / 'Waktu' -> expense_date; 'Kategori' / 'Jenis Biaya' / 'Pos' / 'Akun' -> category; 'Keterangan' / 'Deskripsi' / 'Uraian' / 'Rincian' / 'Keperluan' -> description; 'Jumlah' / 'Nominal' / 'Total' / 'Biaya' / 'Pengeluaran' / 'Debit' -> amount; 'Cabang' / 'Outlet' / 'Lokasi' -> branch_id.\n"
        "3. Recognize English terms: e.g. 'Date' -> expense_date; 'Category' / 'Cost Type' -> category; 'Description' / 'Notes' / 'Item' -> description; 'Amount' / 'Total' / 'Cost' / 'Debit' -> amount; 'Branch' / 'Store' -> branch_id.\n"
        "4. Use sample values and data types to disambiguate: numbers / currency formats indicate 'amount', dates indicate 'expense_date', short categorical text indicates 'category'.\n"
        "5. Assign a confidence score between 0.0 and 1.0 (e.g. 0.95 for direct match, 0.7 for partial match).\n"
        "6. Return JSON ONLY with the exact schema:\n"
        "{\n"
        '  "mappings": [\n'
        '    {"source_column": "<original header>", "target_field": "<canonical_field_or__skip>", "confidence": 0.95, "reasoning": "<brief reasoning>"}\n'
        "  ],\n"
        '  "unmapped_columns": ["<source_column if not mapped or skipped>"],\n'
        '  "warnings": ["<notes on any ambiguous columns>"]\n'
        "}"
    )

    profile_text = profile_to_prompt_text(profile)
    if business_context and business_context.get("branches"):
        branch_names = [b.get("name") for b in business_context["branches"] if b.get("name")]
        if branch_names:
            profile_text += f"\n\nContext - Known Business Branches:\n{', '.join(branch_names)}"

    user_prompt = f"Map the columns from this expense spreadsheet profile to the canonical expense schema:\n\n{profile_text}"

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
        logger.warning(f"Semantic expense mapping LLM call failed: {e}. Falling back to static mapping.")
        return build_fallback_expense_mapping(profile.headers, reason=f"LLM call error: {str(e)}")
    finally:
        if close_client and client is not None:
            await client.close()

    choices = completion.get("choices", []) if isinstance(completion, dict) else getattr(completion, "choices", [])
    if not choices:
        logger.warning("Empty response from semantic expense mapping LLM; using fallback.")
        return build_fallback_expense_mapping(profile.headers, reason="Empty LLM response")

    raw_content = ""
    if isinstance(choices[0], dict):
        raw_content = choices[0].get("message", {}).get("content", "")
    else:
        msg = getattr(choices[0], "message", None)
        raw_content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")

    cleaned = clean_json_text(raw_content)
    try:
        data = json.loads(cleaned)
    except Exception as e:
        logger.warning(f"Failed to parse LLM expense mapping JSON: {e}. Raw: {raw_content[:200]}. Falling back.")
        return build_fallback_expense_mapping(profile.headers, reason=f"Invalid JSON returned: {str(e)}")

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

        if tgt not in CANONICAL_EXPENSE_FIELDS:
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
STANDARD_EXPENSE_CATEGORIES: List[str] = [
    "Ingredients",
    "Packaging",
    "Utilities",
    "Salaries & Wages",
    "Maintenance",
    "Marketing",
    "Rent & Facilities",
    "Operations",
    "Other",
]


async def categorize_expenses_with_llm(
    items: List[Dict[str, Any]],
    business_context: Optional[Dict[str, Any]] = None,
    client: Optional[AMDTokenFactoryClient] = None,
) -> List[str]:
    """
    Categorize expense line items into standard accounting categories using AMD Token Factory LLM.
    This is the PRIMARY method for resolving expense categories from descriptions and raw category inputs.
    Gracefully falls back to heuristic keyword matching (normalize_category) if AI is disabled or fails.
    """
    from app.services.expense_import_service import normalize_category

    if not items:
        return []

    if not settings.SEMANTIC_MAPPING_ENABLED or not settings.AMD_API_KEY:
        return [normalize_category(item.get("category"), item.get("description")) for item in items]

    model = settings.SEMANTIC_MAPPING_MODEL or settings.AMD_DEFAULT_MODEL
    categories_str = ", ".join(f"'{c}'" for c in STANDARD_EXPENSE_CATEGORIES)

    system_prompt = (
        "You are an expert financial and bookkeeping AI specializing in retail and food & beverage (F&B) business expenses.\n"
        f"Your task is to classify a list of expense records into exactly one of the standard English categories:\n"
        f"[{categories_str}]\n\n"
        "Category Definitions:\n"
        "- 'Ingredients': Food and beverage raw ingredients, meats, vegetables, spices, oil, sauces, cheese, coffee, bread, etc.\n"
        "- 'Packaging': Packaging materials, boxes, takeaway containers, cups, straws, plastic bags, tape, labels, wrappers, etc.\n"
        "- 'Utilities': Electricity (PLN), water (PDAM), internet/WiFi, phone credit, data packages, etc.\n"
        "- 'Salaries & Wages': Staff salaries, employee wages, overtime pay, bonuses, staff meals, cash advances (kasbon), etc.\n"
        "- 'Maintenance': Equipment repair, maintenance, spare parts, AC servicing, chiller/freezer repair, kitchen tools, etc.\n"
        "- 'Marketing': Marketing, advertising, social media ads, flyers, banners, promotional campaigns, influencer endorsements, etc.\n"
        "- 'Rent & Facilities': Rent, booth/kiosk lease, property maintenance fees (IPL), community/security dues, venue fees, etc.\n"
        "- 'Operations': Day-to-day operational supplies, LPG cooking gas, cleaning supplies/detergents, POS receipt paper, shipping/courier, transport, parking, fuel/gasoline, etc.\n"
        "- 'Other': Miscellaneous or unclassifiable expenses.\n\n"
        "Return JSON ONLY with the exact schema:\n"
        "{\n"
        '  "classifications": [\n'
        '    {"index": 0, "category": "<one of standard categories>", "confidence": 0.95, "reasoning": "<brief reasoning>"}\n'
        "  ]\n"
        "}"
    )

    payload_items = [
        {
            "index": idx,
            "category": item.get("category"),
            "description": item.get("description"),
            "amount": str(item.get("amount", "")),
        }
        for idx, item in enumerate(items)
    ]
    user_prompt = f"Classify the following expense items into standard categories:\n{json.dumps(payload_items, ensure_ascii=False)}"

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
        logger.warning(f"Semantic expense categorization LLM call failed: {e}. Falling back to heuristic normalization.")
        return [normalize_category(item.get("category"), item.get("description")) for item in items]
    finally:
        if close_client and client is not None:
            await client.close()

    raw_content = ""
    choices = completion.get("choices", []) if isinstance(completion, dict) else getattr(completion, "choices", [])
    if choices:
        msg = choices[0].get("message", {}) if isinstance(choices[0], dict) else getattr(choices[0], "message", None)
        raw_content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")

    cleaned = clean_json_text(raw_content)
    try:
        data = json.loads(cleaned)
    except Exception as e:
        logger.warning(f"Failed to parse LLM expense categorization JSON: {e}. Falling back.")
        return [normalize_category(item.get("category"), item.get("description")) for item in items]

    classifications_list = data.get("classifications", []) if isinstance(data, dict) else []
    cat_by_idx: Dict[int, str] = {}
    for entry in classifications_list:
        if isinstance(entry, dict) and "index" in entry and "category" in entry:
            c_val = str(entry["category"]).strip()
            matched = None
            for std_cat in STANDARD_EXPENSE_CATEGORIES:
                if std_cat.lower() == c_val.lower():
                    matched = std_cat
                    break
            if matched:
                try:
                    cat_by_idx[int(entry["index"])] = matched
                except (ValueError, TypeError):
                    pass

    results: List[str] = []
    for idx, item in enumerate(items):
        if idx in cat_by_idx:
            results.append(cat_by_idx[idx])
        else:
            results.append(normalize_category(item.get("category"), item.get("description")))

    return results


def build_fallback_sheet_classifications(
    profiles: List[SpreadsheetProfile],
    reason: str = "Fallback to heuristic classification",
) -> List[SheetClassification]:
    """Heuristic rule-based classification of worksheets when LLM is unavailable or fails."""
    results: List[SheetClassification] = []
    instruction_keywords = {"instruction", "instructions", "petunjuk", "panduan", "cara", "readme", "catatan", "guide", "notes", "aturan"}
    reference_keywords = {"product", "produk", "menu", "master", "reference", "referensi", "daftar", "barang", "branch", "cabang", "price", "harga"}
    expense_keywords = {"expense", "expenses", "biaya", "pengeluaran", "operational", "kas", "petty", "overhead", "spending"}
    sales_metric_keywords = {"terjual", "sold", "laku", "qty", "sales", "omzet", "omset", "revenue", "pendapatan", "total"}

    for p in profiles:
        name_clean = re.sub(r"[^a-zA-Z0-9]+", " ", p.active_sheet_name.lower()).strip()
        tokens = set(name_clean.split())

        # Check instruction
        if tokens & instruction_keywords:
            results.append(SheetClassification(
                sheet_name=p.active_sheet_name,
                role="instructional",
                confidence=0.9,
                reasoning=f"{reason}: sheet name matched instructional keywords",
            ))
            continue

        # Check expenses
        if tokens & expense_keywords:
            results.append(SheetClassification(
                sheet_name=p.active_sheet_name,
                role="expenses",
                confidence=0.85,
                reasoning=f"{reason}: sheet name matched expense keywords",
            ))
            continue

        # Check headers
        header_tokens: set = set()
        for h in p.headers:
            h_norm = re.sub(r"[^a-zA-Z0-9]+", "_", str(h).strip().lower()).strip("_")
            header_tokens.add(h_norm)
            for part in h_norm.split("_"):
                if part:
                    header_tokens.add(part)

        # Reference sheet check
        if (tokens & reference_keywords) and not (sales_metric_keywords & header_tokens):
            results.append(SheetClassification(
                sheet_name=p.active_sheet_name,
                role="reference",
                confidence=0.85,
                reasoning=f"{reason}: reference sheet detected without sales metrics",
            ))
            continue

        sales_matches = header_tokens & sales_metric_keywords
        if len(sales_matches) >= 2 or any(k in header_tokens for k in ("sold_qty", "terjual", "laku", "recorded_revenue", "revenue", "omset", "omzet")):
            results.append(SheetClassification(
                sheet_name=p.active_sheet_name,
                role="sales",
                confidence=0.9,
                reasoning=f"{reason}: sales metrics matched in headers",
            ))
        elif any(k in header_tokens for k in ("product", "produk", "menu", "item", "kode", "code", "harga", "price", "kategori", "category")):
            results.append(SheetClassification(
                sheet_name=p.active_sheet_name,
                role="reference",
                confidence=0.7,
                reasoning=f"{reason}: reference columns detected without sales metrics",
            ))
        else:
            results.append(SheetClassification(
                sheet_name=p.active_sheet_name,
                role="ambiguous",
                confidence=0.5,
                reasoning=f"{reason}: unrecognized columns and layout",
            ))

    return results


async def classify_sheet_roles(
    profiles: List[SpreadsheetProfile],
    business_context: Optional[Dict[str, Any]] = None,
    client: Optional[AMDTokenFactoryClient] = None,
) -> List[SheetClassification]:
    """
    Classify the semantic role of each worksheet in an Excel workbook using LLM.
    Identifies sheet roles such as:
      - 'sales': Daily branch reports, sales summaries, catering orders, sold/leftover quantities, revenue.
      - 'reference': Master data tables such as product catalog, price lists, or branch lists.
      - 'instructional': Guidelines, instructions, readme, format explanations, notes.
      - 'expenses': Operational costs, petty cash, expense breakdown.
      - 'ambiguous': Unclear, unsupported, or ambiguous structure requiring user review.
    """
    if not profiles:
        return []

    if not settings.SEMANTIC_MAPPING_ENABLED:
        logger.info("Semantic mapping is disabled; using heuristic sheet role classification.")
        return build_fallback_sheet_classifications(profiles, reason="Semantic mapping disabled by configuration")

    if not settings.AMD_API_KEY:
        logger.info("AMD_API_KEY not configured; using heuristic sheet role classification fallback.")
        return build_fallback_sheet_classifications(profiles, reason="AMD API key not configured")

    model = settings.SEMANTIC_MAPPING_MODEL or settings.AMD_DEFAULT_MODEL

    system_prompt = (
        "You are an expert data architect specializing in retail, restaurant, and food-service spreadsheet analysis.\n"
        "Your task is to analyze multiple worksheet profiles from an Excel workbook and classify each sheet's semantic role.\n\n"
        "Semantic Roles:\n"
        "1. 'sales': Contains transaction or summary sales records, daily branch reports, catering orders, quantities (sold, prepared, leftover, spoiled), or revenue. Compatible with sales reporting.\n"
        "2. 'reference': Master reference data such as product catalogs, price lists, branch directories, or menu item tables.\n"
        "3. 'instructional': Template guidelines, readme, instructions, legends, or notes for users filling the spreadsheet.\n"
        "4. 'expenses': Cost sheets, petty cash, purchase invoices, or operational expenses.\n"
        "5. 'ambiguous': Unclear layout, non-standard tabular data, or ambiguous content requiring human review.\n\n"
        "Instructions:\n"
        "- Classify every sheet listed in the user prompt.\n"
        "- Consider Indonesian and English sheet titles and headers (e.g. 'Penjualan' -> sales, 'Petunjuk' -> instructional, 'Daftar Menu' -> reference, 'Pengeluaran' -> expenses).\n"
        "- Return JSON ONLY in the following format:\n"
        "{\n"
        '  "classifications": [\n'
        '    {"sheet_name": "<exact sheet title>", "role": "sales|reference|instructional|expenses|ambiguous", "confidence": 0.95, "reasoning": "<brief explanation>"}\n'
        "  ]\n"
        "}"
    )

    sheet_lines = []
    for p in profiles:
        sheet_lines.append(f"Sheet Title: \"{p.active_sheet_name}\"")
        sheet_lines.append(f"  Total Data Rows: {p.total_data_rows}")
        sheet_lines.append(f"  Headers: {', '.join(p.headers)}")
        col_types = ", ".join(f"{h}: {p.column_types.get(h, 'text')}" for h in p.headers[:8])
        sheet_lines.append(f"  Inferred Column Types: {col_types}")
        if p.sample_rows:
            sample_str = " | ".join(str(r[:6]) for r in p.sample_rows[:2])
            sheet_lines.append(f"  Sample Rows (up to 2): {sample_str}")
        sheet_lines.append("")

    user_prompt = "Classify the semantic roles of these worksheets:\n\n" + "\n".join(sheet_lines)

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
        logger.warning(f"Sheet role classification LLM call failed: {e}. Falling back to heuristic classification.")
        return build_fallback_sheet_classifications(profiles, reason=f"LLM call error: {str(e)}")
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
        logger.warning(f"Failed to parse LLM sheet classification JSON: {e}. Raw: {raw_content[:200]}. Falling back to heuristic.")
        return build_fallback_sheet_classifications(profiles, reason=f"Invalid JSON returned: {str(e)}")

    classifications_raw = data.get("classifications", []) if isinstance(data, dict) else []
    classified_map: Dict[str, SheetClassification] = {}
    valid_roles = {"sales", "reference", "instructional", "expenses", "ambiguous"}

    for item in classifications_raw:
        if not isinstance(item, dict):
            continue
        s_name = str(item.get("sheet_name", "")).strip()
        role = str(item.get("role", "ambiguous")).strip().lower()
        if role not in valid_roles:
            role = "ambiguous"

        try:
            conf = float(item.get("confidence", 0.8))
        except (ValueError, TypeError):
            conf = 0.8
        conf = max(0.0, min(1.0, conf))

        classified_map[s_name.lower()] = SheetClassification(
            sheet_name=s_name,
            role=role,
            confidence=conf,
            reasoning=item.get("reasoning"),
        )

    # Reconstruct in order of profiles and fill any missing sheets
    results: List[SheetClassification] = []
    fallback_results = {fb.sheet_name.lower(): fb for fb in build_fallback_sheet_classifications(profiles)}

    for p in profiles:
        lower_name = p.active_sheet_name.lower()
        if lower_name in classified_map:
            cls = classified_map[lower_name]
            cls.sheet_name = p.active_sheet_name  # preserve exact original casing
            results.append(cls)
        elif lower_name in fallback_results:
            results.append(fallback_results[lower_name])
        else:
            results.append(SheetClassification(
                sheet_name=p.active_sheet_name,
                role="ambiguous",
                confidence=0.5,
                reasoning="Sheet was omitted from LLM response",
            ))

    return results
