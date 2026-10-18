from datetime import date
from decimal import Decimal
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.configs.settings import settings
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.exceptions import NotFoundException, ValidationException
from app.helpers.logging import logger
from app.models.branch import Branch
from app.models.expense import Expense
from app.models.user import User
from app.models.schemas.expense import (
    ExpenseImportItem,
    ExpenseImportResponse,
    ExpenseImportSummary,
    ExpenseResponse,
)
from app.services.expense_spreadsheet_parser import parse_expense_file
from app.services.expense_photo_extractor import extract_expenses_from_photo


CATEGORY_KEYWORDS: List[Tuple[str, List[str]]] = [
    (
        "Packaging",
        [
            "kemasan", "box", "kotak", "kardus", "kantong", "kresek", "plastik", "cup", "gelas",
            "sedotan", "straw", "paper bag", "paper lunch", "thinwall", "stiker", "sticker", "label",
            "solasi", "lakban", "wrap", "cling wrap", "alumunium foil", "foil", "pita", "packaging",
            "dus", "kertas bungkus", "sendok plastik", "garpu plastik",
        ],
    ),
    (
        "Ingredients",
        [
            "daging", "sapi", "ayam", "beef", "chicken", "telur", "beras", "tepung", "minyak",
            "sayur", "tomat", "bawang", "cabai", "cabe", "bumbu", "saus", "sauce", "keju", "cheese",
            "roti", "bread", "pita", "sosis", "susu", "gula", "garam", "kentang", "french fries",
            "patty", "patty beef", "selada", "mayo", "mayonnaise", "mustard", "lada", "mentega", "butter",
            "margarin", "buah", "kopi", "coffee", "teh", "tea", "sirup", "seasoning", "bahan", "bahan baku",
        ],
    ),
    (
        "Utilities",
        [
            "listrik", "pln", "token pln", "token listrik", "air", "pdam", "air pam", "wifi",
            "internet", "indihome", "biznet", "pulsa", "paket data", "telepon",
        ],
    ),
    (
        "Salaries & Wages",
        [
            "gaji", "salary", "upah", "uang makan", "uang lembur", "lembur", "overtime", "kasbon",
            "thr", "bonus", "insentif", "honor", "crew", "barista", "cook", "kitchen",
        ],
    ),
    (
        "Maintenance",
        [
            "servis", "service", "perbaikan", "repair", "teknisi", "sparepart", "chiller", "freezer",
            "kulkas", "kompor", "blender", "ac", "cuci ac", "las", "ganti lampu", "tambal",
            "alat masak", "pisau", "wajan",
        ],
    ),
    (
        "Marketing",
        [
            "iklan", "ads", "advertising", "marketing", "promo", "promosi", "spanduk", "banner",
            "brosur", "flyer", "cetak", "endorse", "influencer", "meta ads", "google ads", "tiktok ads",
        ],
    ),
    (
        "Rent & Facilities",
        [
            "sewa", "rent", "kontrak", "kontrakan", "ruko", "booth", "kios", "iuran", "retribusi",
            "kebersihan lingkungan", "keamanan", "ipl", "paguyuban",
        ],
    ),
    (
        "Operations",
        [
            "gas", "lpg", "elpiji", "galon", "aqua", "es batu", "ice tube", "sapu", "pel",
            "sabun", "sunlight", "deterjen", "pembersih", "trash bag", "kantong sampah", "tissue",
            "tisu", "atk", "kertas struk", "thermal", "baterai", "transport", "bensin", "pertalite",
            "pertamax", "parkir", "tol", "ongkir", "delivery", "pos", "materai",
        ],
    ),
]


STANDARD_CATEGORIES_MAP: Dict[str, str] = {
    # Ingredients
    "ingredients": "Ingredients",
    "ingredient": "Ingredients",
    "bahan baku": "Ingredients",
    "raw materials": "Ingredients",
    "raw material": "Ingredients",
    "food": "Ingredients",
    "food supplies": "Ingredients",
    "beverage supplies": "Ingredients",
    # Packaging
    "packaging": "Packaging",
    "kemasan": "Packaging",
    # Utilities
    "utilities": "Utilities",
    "utility": "Utilities",
    "utilitas": "Utilities",
    # Salaries & Wages
    "salaries & wages": "Salaries & Wages",
    "salaries": "Salaries & Wages",
    "salary": "Salaries & Wages",
    "wages": "Salaries & Wages",
    "payroll": "Salaries & Wages",
    "gaji & upah": "Salaries & Wages",
    "gaji": "Salaries & Wages",
    "upah": "Salaries & Wages",
    # Maintenance
    "maintenance": "Maintenance",
    "pemeliharaan": "Maintenance",
    "perbaikan": "Maintenance",
    "repair": "Maintenance",
    "service": "Maintenance",
    # Marketing
    "marketing": "Marketing",
    "pemasaran": "Marketing",
    "advertising": "Marketing",
    "promo": "Marketing",
    "promosi": "Marketing",
    # Rent & Facilities
    "rent & facilities": "Rent & Facilities",
    "rent": "Rent & Facilities",
    "lease": "Rent & Facilities",
    "sewa & tempat": "Rent & Facilities",
    "sewa": "Rent & Facilities",
    # Operations
    "operations": "Operations",
    "operational": "Operations",
    "operasional": "Operations",
    "supplies": "Operations",
    # Other
    "other": "Other",
    "others": "Other",
    "miscellaneous": "Other",
    "misc": "Other",
    "lain-lain": "Other",
    "lainnya": "Other",
}


def normalize_category(raw_category: Optional[str], description: Optional[str] = None) -> str:
    """Normalize raw category string or infer category from description using keywords."""
    if raw_category:
        norm = raw_category.strip().lower()
        if norm in STANDARD_CATEGORIES_MAP:
            return STANDARD_CATEGORIES_MAP[norm]

        # Check partial match on standard category keys
        for key, std in STANDARD_CATEGORIES_MAP.items():
            if key in norm or norm in key:
                return std

    # If category is empty or generic, infer from description
    combined_text = f"{raw_category or ''} {description or ''}".lower()
    for std_category, keywords in CATEGORY_KEYWORDS:
        for kw in keywords:
            # Word boundary matching
            if re.search(r"\b" + re.escape(kw) + r"\b", combined_text):
                return std_category

    return "Operations"


def resolve_branch_id(
    db: Session,
    business_id: int,
    branch_val: Optional[Any],
    default_branch_id: Optional[int] = None,
) -> Optional[int]:
    """Resolve branch identifier (ID, name, or code) within the business."""
    if branch_val is not None:
        if isinstance(branch_val, int):
            b = db.query(Branch).filter(Branch.id == branch_val, Branch.business_id == business_id).first()
            if b:
                return b.id
        elif isinstance(branch_val, str) and branch_val.strip():
            b_str = branch_val.strip()
            # If string contains digits only
            if b_str.isdigit():
                b = db.query(Branch).filter(Branch.id == int(b_str), Branch.business_id == business_id).first()
                if b:
                    return b.id
            # Query by name or code case-insensitive
            b = db.query(Branch).filter(
                Branch.business_id == business_id,
                (Branch.name.ilike(b_str)) | (Branch.branch_code.ilike(b_str)),
            ).first()
            if b:
                return b.id

    if default_branch_id is not None:
        b = db.query(Branch).filter(Branch.id == default_branch_id, Branch.business_id == business_id).first()
        if b:
            return b.id

    return None


async def import_expenses(
    db: Session,
    business_id: int,
    files: List[UploadFile],
    input_method: str,
    branch_id: Optional[int],
    default_date: Optional[date],
    current_user: User,
    source_submission_id: Optional[int] = None,
) -> ExpenseImportResponse:
    """
    Import expenses from spreadsheets or photo OCR receipts as draft records
    pending user review and activation.
    """
    if default_branch_id := branch_id:
        branch = db.query(Branch).filter(Branch.id == default_branch_id, Branch.business_id == business_id).first()
        if not branch:
            raise NotFoundException(
                message="Branch not found",
                errors={"branch_id": f"Branch with ID {default_branch_id} does not exist in this business"},
            )

    branches = db.query(Branch).filter(Branch.business_id == business_id).all()
    biz_context = {
        "branches": [{"id": b.id, "name": b.name, "code": b.branch_code} for b in branches]
    }

    raw_items: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    primary_filename = files[0].filename if files and files[0].filename else "import_file"

    if input_method == "spreadsheet":
        from app.services.input_profiler import profile_excel_workbook, profile_csv
        from app.services.semantic_mapper import map_expense_columns_with_llm

        for file in files:
            content = await file.read()
            f_name = file.filename or "upload.xlsx"
            m_type = file.content_type
            is_excel = (
                f_name.lower().endswith(".xlsx")
                or f_name.lower().endswith(".xls")
                or (m_type and "spreadsheet" in m_type)
                or content[:4] == b"PK\x03\x04"
            )

            sheet_mappings: Dict[str, Optional[Any]] = {}
            mapping_result = None

            if is_excel:
                try:
                    wb_prof = profile_excel_workbook(content)
                    for p in wb_prof.sheet_profiles:
                        m_res = await map_expense_columns_with_llm(p, biz_context)
                        sheet_mappings[p.active_sheet_name] = m_res
                        for entry in m_res.mappings:
                            if entry.confidence < settings.SEMANTIC_MAPPING_CONFIDENCE_THRESHOLD and entry.target_field != "_skip":
                                issues.append({
                                    "source_row_number": None,
                                    "field_name": entry.target_field,
                                    "issue_code": ErrorCodeRegistry.RPT_LOW_CONFIDENCE,
                                    "message": f"Column '{entry.source_column}' mapped to '{entry.target_field}' with low confidence ({entry.confidence:.0%})",
                                    "raw_value": entry.source_column,
                                })
                except Exception as e:
                    logger.warning(f"Error during semantic profiling of Excel: {e}")
            else:
                try:
                    csv_prof = profile_csv(content)
                    mapping_result = await map_expense_columns_with_llm(csv_prof, biz_context)
                    for entry in mapping_result.mappings:
                        if entry.confidence < settings.SEMANTIC_MAPPING_CONFIDENCE_THRESHOLD and entry.target_field != "_skip":
                            issues.append({
                                "source_row_number": None,
                                "field_name": entry.target_field,
                                "issue_code": ErrorCodeRegistry.RPT_LOW_CONFIDENCE,
                                "message": f"Column '{entry.source_column}' mapped to '{entry.target_field}' with low confidence ({entry.confidence:.0%})",
                                "raw_value": entry.source_column,
                            })
                except Exception as e:
                    logger.warning(f"Error during semantic profiling of CSV: {e}")

            rows, errs = parse_expense_file(
                file_bytes=content,
                file_name=f_name,
                mime_type=m_type,
                sheet_mappings=sheet_mappings if sheet_mappings else None,
                mapping_result=mapping_result,
                default_date=default_date,
                default_branch_id=branch_id,
            )
            for r in rows:
                r["source_file_name"] = f_name
            raw_items.extend(rows)
            issues.extend(errs)

    elif input_method == "photo":
        for idx, file in enumerate(files, start=1):
            content = await file.read()
            f_name = file.filename or f"receipt_{idx}.jpg"
            m_type = file.content_type or "image/jpeg"
            rows, meta = await extract_expenses_from_photo(
                image_bytes=content,
                mime_type=m_type,
                business_context=biz_context,
                default_date=default_date,
                default_branch_id=branch_id,
            )
            for r in rows:
                r["source_file_name"] = f_name
            raw_items.extend(rows)

    else:
        raise ValidationException(
            errors={"input_method": f"Invalid input_method '{input_method}'. Supported: 'spreadsheet', 'photo'"},
            message="Invalid input method",
        )

    if not raw_items:
        raise ValidationException(
            errors={"file": "No valid expense items could be extracted", "error_code": ErrorCodeRegistry.EXP_EMPTY_FILE},
            message="No expenses extracted",
            error_code=ErrorCodeRegistry.EXP_EMPTY_FILE,
        )

    from app.services.semantic_mapper import categorize_expenses_with_llm

    categories_breakdown: Dict[str, Decimal] = {}
    total_amount = Decimal("0.00")
    items_to_persist: List[Expense] = []
    preview_items: List[ExpenseImportItem] = []

    # Semantic AI category classification as primary method
    inferred_categories = await categorize_expenses_with_llm(raw_items, biz_context)

    for idx, r in enumerate(raw_items, start=1):
        parsed_category = (
            inferred_categories[idx - 1]
            if idx - 1 < len(inferred_categories)
            else normalize_category(r.get("category"), r.get("description"))
        )
        b_id = resolve_branch_id(db, business_id, r.get("branch") or r.get("branch_id"), branch_id)
        amt = Decimal(str(r["amount"]))
        total_amount += amt
        categories_breakdown[parsed_category] = categories_breakdown.get(parsed_category, Decimal("0.00")) + amt

        b_name = None
        if b_id:
            for b in branches:
                if b.id == b_id:
                    b_name = b.name
                    break

        item_preview = ExpenseImportItem(
            source_row_number=r.get("source_row_number", idx),
            branch_id=b_id,
            branch_name=b_name,
            expense_date=r["expense_date"],
            category=parsed_category,
            description=r.get("description"),
            amount=amt,
            currency=r.get("currency", "IDR"),
            status="draft",
            source_file_name=r.get("source_file_name"),
            confidence=r.get("confidence"),
            warnings=[],
        )
        preview_items.append(item_preview)

        exp_model = Expense(
            business_id=business_id,
            branch_id=b_id,
            expense_date=r["expense_date"],
            category=parsed_category,
            description=r.get("description"),
            amount=amt,
            currency=r.get("currency", "IDR"),
            status="draft",
            source_submission_id=source_submission_id or r.get("source_submission_id"),
            source_row_number=r.get("source_row_number"),
            created_by_user_id=current_user.id,
        )
        items_to_persist.append(exp_model)

    saved_expenses: List[Expense] = []
    if items_to_persist:
        db.add_all(items_to_persist)
        db.commit()
        for exp in items_to_persist:
            db.refresh(exp)
            saved_expenses.append(exp)

    summary = ExpenseImportSummary(
        total_extracted=len(raw_items),
        total_saved=len(saved_expenses),
        total_amount=total_amount,
        categories_breakdown=categories_breakdown,
        file_name=primary_filename,
        input_method=input_method,
        status="draft",
    )

    return ExpenseImportResponse(
        summary=summary,
        expenses=[ExpenseResponse.model_validate(e) for e in saved_expenses],
        items=preview_items,
        issues=issues,
    )
