import csv
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
import io
import re
from typing import Any, Dict, List, Optional, Tuple
import openpyxl

from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.exceptions import ValidationException
from app.helpers.logging import logger


CANONICAL_EXPENSE_HEADERS = {
    # Date
    "tanggal": "expense_date",
    "date": "expense_date",
    "tgl": "expense_date",
    "waktu": "expense_date",
    "expense_date": "expense_date",
    "tgl_pengeluaran": "expense_date",
    "tgl_biaya": "expense_date",
    "transaksi": "expense_date",
    "tgl_transaksi": "expense_date",
    # Category
    "kategori": "category",
    "category": "category",
    "jenis_biaya": "category",
    "jenis_pengeluaran": "category",
    "pos_biaya": "category",
    "pos_anggaran": "category",
    "pos": "category",
    "akun": "category",
    "kategori_biaya": "category",
    "tipe_biaya": "category",
    # Description / Item
    "keterangan": "description",
    "deskripsi": "description",
    "description": "description",
    "uraian": "description",
    "item": "description",
    "item_name": "description",
    "nama_item": "description",
    "nama_biaya": "description",
    "nama_pengeluaran": "description",
    "keperluan": "description",
    "catatan": "description",
    "rincian": "description",
    "detail": "description",
    # Amount / Total
    "jumlah": "amount",
    "nominal": "amount",
    "total": "amount",
    "biaya": "amount",
    "pengeluaran": "amount",
    "amount": "amount",
    "total_biaya": "amount",
    "total_pengeluaran": "amount",
    "debit": "amount",
    "subtotal": "amount",
    "nilai": "amount",
    "harga": "amount",
    "tagihan": "amount",
    # Branch
    "cabang": "branch",
    "branch": "branch",
    "branch_name": "branch",
    "outlet": "branch",
    "lokasi": "branch",
    "store": "branch",
    "id_cabang": "branch_id",
    "branch_id": "branch_id",
    # Currency
    "mata_uang": "currency",
    "currency": "currency",
}


def normalize_expense_header(header: str) -> str:
    """Normalize raw header name to canonical expense field or snake_case."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", str(header).strip().lower()).strip("_")
    return CANONICAL_EXPENSE_HEADERS.get(cleaned, cleaned)


def normalize_expense_header_from_mapping(
    header: str,
    mapping_result: Optional[Any] = None,
) -> str:
    """Normalize a header using SemanticMappingResult if available, otherwise static mapping."""
    if mapping_result and getattr(mapping_result, "mappings", None):
        h_clean = str(header).strip().lower()
        for entry in mapping_result.mappings:
            if entry.source_column.strip().lower() == h_clean:
                if entry.target_field and entry.target_field != "_skip":
                    return entry.target_field
                elif entry.target_field == "_skip":
                    return "_skip"
    return normalize_expense_header(header)



def parse_currency_amount(val: Any) -> Optional[Decimal]:
    """
    Parse a numeric value or formatted currency string (e.g., 'Rp 1.500.000,00', '1,500,000.50', '(50.000)').
    Returns positive Decimal or None if unparseable.
    """
    if val is None:
        return None
    if isinstance(val, (int, float, Decimal)):
        try:
            dec = Decimal(str(val))
            return abs(dec)
        except InvalidOperation:
            return None

    raw_str = str(val).strip()
    if not raw_str or raw_str == "-" or raw_str.lower() == "null":
        return None

    # Check negative in parentheses e.g. (10.000)
    is_paren_negative = raw_str.startswith("(") and raw_str.endswith(")")
    if is_paren_negative:
        raw_str = raw_str[1:-1].strip()

    # Strip currency prefixes and spaces
    cleaned = re.sub(r"^(?:rp\.?|idr|\$)\s*", "", raw_str, flags=re.IGNORECASE).strip()

    # Handle Indonesian format: 1.500.000,00 vs US format: 1,500,000.00
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            # Indonesian: 1.500.000,50 -> 1500000.50
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # US: 1,500,000.50 -> 1500000.50
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        # e.g. 1500000,50 or 1,500,000
        comma_parts = cleaned.split(",")
        if len(comma_parts) == 2 and len(comma_parts[1]) in (1, 2):
            # Decimal comma: 50000,50 -> 50000.50
            cleaned = cleaned.replace(",", ".")
        else:
            # Thousand separator: 1,500,000 -> 1500000
            cleaned = cleaned.replace(",", "")
    elif "." in cleaned:
        dot_parts = cleaned.split(".")
        if len(dot_parts) > 2 or (len(dot_parts) == 2 and len(dot_parts[1]) == 3):
            # Thousand separator: 1.500.000 or 150.000 -> 1500000 / 150000
            cleaned = cleaned.replace(".", "")

    # Clean out any non-numeric/decimal characters remaining
    cleaned = re.sub(r"[^\d.]", "", cleaned)
    if not cleaned:
        return None

    try:
        dec = Decimal(cleaned)
        return abs(dec)
    except InvalidOperation:
        return None


def parse_flexible_date(val: Any, default_date: Optional[date] = None) -> Optional[date]:
    """
    Parse a date from datetime.date, datetime.datetime, Excel serial number, or string formats.
    """
    if val is None or val == "":
        return default_date
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val

    # Excel serial number (e.g. 45210)
    if isinstance(val, (int, float)):
        try:
            excel_base = datetime(1899, 12, 30)
            return (excel_base + timedelta(days=float(val))).date()
        except Exception:
            pass

    s = str(val).strip()
    # Check if string is float/int serial number
    if re.match(r"^\d{4,6}(?:\.0+)?$", s):
        try:
            serial_val = float(s)
            if 30000 < serial_val < 60000:
                excel_base = datetime(1899, 12, 30)
                return (excel_base + timedelta(days=serial_val)).date()
        except Exception:
            pass

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d/%m/%y",
        "%d-%m-%y",
        "%Y-%m-%d %H:%M:%S",
        "%d %B %Y",
        "%d %b %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue

    # Try matching YYYY-MM-DD within string (e.g. ISO timestamp)
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    return default_date


def parse_expense_worksheet(
    sheet: Any,
    sheet_name: str,
    mapping_result: Optional[Any] = None,
    default_date: Optional[date] = None,
    default_branch_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse a single openpyxl worksheet for expense data with optional semantic mapping."""
    rows_iter = sheet.iter_rows(values_only=True)
    header_row = None
    header_row_idx = 1

    for idx, r in enumerate(rows_iter, start=1):
        if any(cell is not None and str(cell).strip() != "" for cell in r):
            header_row = r
            header_row_idx = idx
            break

    if not header_row:
        return [], []

    header_strings = [str(c).strip() if c is not None else f"col_{idx+1}" for idx, c in enumerate(header_row)]
    col_keys = [normalize_expense_header_from_mapping(h, mapping_result) for h in header_strings]

    parsed_rows: List[Dict[str, Any]] = []
    parse_errors: List[Dict[str, Any]] = []

    for row_idx, r in enumerate(rows_iter, start=header_row_idx + 1):
        if not any(cell is not None and str(cell).strip() != "" for cell in r):
            continue

        clean_cells = [str(c).strip() if c is not None else "" for c in r[:len(header_strings)]]
        if clean_cells == header_strings:
            # Skip repeated header row
            continue

        raw_payload: Dict[str, Any] = {}
        row_dict: Dict[str, Any] = {
            "source_row_number": row_idx,
            "source_sheet_name": sheet_name,
        }

        for col_idx, cell in enumerate(r):
            orig_col = header_strings[col_idx] if col_idx < len(header_strings) else f"col_{col_idx+1}"
            norm_col = col_keys[col_idx] if col_idx < len(col_keys) else f"col_{col_idx+1}"
            raw_payload[orig_col] = str(cell) if cell is not None else None

            if cell is not None and str(cell).strip() != "" and norm_col != "_skip":
                row_dict[norm_col] = cell

        row_dict["raw_payload_json"] = raw_payload

        # Attach semantic mapping extraction confidence
        if mapping_result and getattr(mapping_result, "mappings", None):
            row_dict["extraction_confidence_json"] = {
                "mapping_method": "llm" if not getattr(mapping_result, "fallback_used", False) else "static_fallback",
                "model": getattr(mapping_result, "model_used", "unknown"),
                "column_confidences": {
                    entry.source_column: {
                        "target": entry.target_field,
                        "confidence": entry.confidence,
                        "reasoning": entry.reasoning,
                    }
                    for entry in mapping_result.mappings
                },
                "warnings": getattr(mapping_result, "warnings", []),
            }

        # Parse and validate amount
        amount_val = row_dict.get("amount")
        parsed_amount = parse_currency_amount(amount_val)
        if parsed_amount is None:
            parse_errors.append({
                "source_row_number": row_idx,
                "field_name": "amount",
                "issue_code": ErrorCodeRegistry.EXP_INVALID_ROW,
                "message": f"Invalid or missing expense amount: '{amount_val}'",
                "raw_value": str(amount_val),
            })
            continue

        # Parse date
        date_val = row_dict.get("expense_date")
        parsed_date = parse_flexible_date(date_val, default_date or date.today())

        # Clean description & category
        desc = row_dict.get("description")
        desc_str = str(desc).strip() if desc is not None else None
        if desc_str and len(desc_str) > 255:
            desc_str = desc_str[:255]

        cat = row_dict.get("category")
        cat_str = str(cat).strip() if cat is not None else None

        currency_str = str(row_dict.get("currency") or "IDR").strip().upper()[:3]
        if not currency_str:
            currency_str = "IDR"

        parsed_rows.append({
            "source_row_number": row_idx,
            "source_sheet_name": sheet_name,
            "expense_date": parsed_date,
            "category": cat_str,
            "description": desc_str,
            "amount": parsed_amount,
            "currency": currency_str,
            "branch": row_dict.get("branch"),
            "branch_id": row_dict.get("branch_id") or default_branch_id,
            "raw_payload_json": raw_payload,
            "extraction_confidence_json": row_dict.get("extraction_confidence_json"),
        })

    return parsed_rows, parse_errors


def parse_expense_excel(
    file_bytes: bytes,
    file_name: str = "",
    sheet_mappings: Optional[Dict[str, Optional[Any]]] = None,
    mapping_result: Optional[Any] = None,
    default_date: Optional[date] = None,
    default_branch_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse XLSX / XLS bytes into list of normalized expense dictionaries using semantic mappings."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as e:
        logger.error(f"Error loading Excel workbook for expenses: {e}", exc_info=True)
        raise ValidationException(
            errors={"file": f"Invalid or corrupt Excel workbook: {str(e)}", "error_code": ErrorCodeRegistry.EXP_PARSE_ERROR},
            message="Malformed or corrupt spreadsheet file",
            error_code=ErrorCodeRegistry.EXP_PARSE_ERROR,
        )

    all_rows: List[Dict[str, Any]] = []
    all_errors: List[Dict[str, Any]] = []

    # If there are multiple sheets, prioritize sheets with expense-related names
    expense_keywords = {"expense", "expenses", "biaya", "pengeluaran", "kas", "petty", "overhead", "spending"}
    matched_sheets = [s for s in wb.sheetnames if any(kw in s.lower() for kw in expense_keywords)]
    sheets_to_process = matched_sheets if matched_sheets else wb.sheetnames

    for sheet_name in sheets_to_process:
        sheet = wb[sheet_name]
        m_res = None
        if sheet_mappings and sheet_name in sheet_mappings:
            m_res = sheet_mappings[sheet_name]
        elif mapping_result:
            m_res = mapping_result

        sheet_rows, sheet_errors = parse_expense_worksheet(
            sheet=sheet,
            sheet_name=sheet_name,
            mapping_result=m_res,
            default_date=default_date,
            default_branch_id=default_branch_id,
        )
        all_rows.extend(sheet_rows)
        all_errors.extend(sheet_errors)

    if not all_rows and not all_errors:
        raise ValidationException(
            errors={"file": "Workbook contains no valid expense rows", "error_code": ErrorCodeRegistry.EXP_EMPTY_FILE},
            message="Spreadsheet contains no data rows",
            error_code=ErrorCodeRegistry.EXP_EMPTY_FILE,
        )

    return all_rows, all_errors


def parse_expense_csv(
    file_bytes: bytes,
    file_name: str = "",
    mapping_result: Optional[Any] = None,
    default_date: Optional[date] = None,
    default_branch_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse CSV bytes into list of normalized expense dictionaries using semantic mapping."""
    try:
        text_content = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text_content = file_bytes.decode("latin-1")
        except Exception as e:
            raise ValidationException(
                errors={"file": f"Unable to decode CSV text: {str(e)}", "error_code": ErrorCodeRegistry.EXP_PARSE_ERROR},
                message="Malformed CSV file",
                error_code=ErrorCodeRegistry.EXP_PARSE_ERROR,
            )

    if not text_content.strip():
        raise ValidationException(
            errors={"file": "CSV contains no data", "error_code": ErrorCodeRegistry.EXP_EMPTY_FILE},
            message="Spreadsheet contains no data rows",
            error_code=ErrorCodeRegistry.EXP_EMPTY_FILE,
        )

    stream = io.StringIO(text_content)
    try:
        sample = text_content[:2048]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except Exception:
            dialect = csv.excel

        reader = csv.reader(stream, dialect=dialect)
        header_row = None
        for row in reader:
            if any(cell.strip() for cell in row):
                header_row = row
                break

        if not header_row:
            raise ValidationException(
                errors={"file": "CSV contains no headers", "error_code": ErrorCodeRegistry.EXP_EMPTY_FILE},
                message="Spreadsheet contains no data rows",
                error_code=ErrorCodeRegistry.EXP_EMPTY_FILE,
            )

        col_keys = [normalize_expense_header_from_mapping(c, mapping_result) for c in header_row]
        parsed_rows: List[Dict[str, Any]] = []
        parse_errors: List[Dict[str, Any]] = []

        for row_idx, row in enumerate(reader, start=2):
            if not any(str(cell).strip() for cell in row):
                continue

            raw_payload: Dict[str, Any] = {}
            row_dict: Dict[str, Any] = {"source_row_number": row_idx}

            for col_idx, cell in enumerate(row):
                orig_col = header_row[col_idx] if col_idx < len(header_row) else f"col_{col_idx+1}"
                norm_col = col_keys[col_idx] if col_idx < len(col_keys) else f"col_{col_idx+1}"
                cell_val = cell.strip() if isinstance(cell, str) else cell
                raw_payload[orig_col] = cell_val
                if cell_val != "" and norm_col != "_skip":
                    row_dict[norm_col] = cell_val

            row_dict["raw_payload_json"] = raw_payload

            # Attach semantic mapping extraction confidence
            if mapping_result and getattr(mapping_result, "mappings", None):
                row_dict["extraction_confidence_json"] = {
                    "mapping_method": "llm" if not getattr(mapping_result, "fallback_used", False) else "static_fallback",
                    "model": getattr(mapping_result, "model_used", "unknown"),
                    "column_confidences": {
                        entry.source_column: {
                            "target": entry.target_field,
                            "confidence": entry.confidence,
                            "reasoning": entry.reasoning,
                        }
                        for entry in mapping_result.mappings
                    },
                    "warnings": getattr(mapping_result, "warnings", []),
                }

            # Validate amount
            amount_val = row_dict.get("amount")
            parsed_amount = parse_currency_amount(amount_val)
            if parsed_amount is None:
                parse_errors.append({
                    "source_row_number": row_idx,
                    "field_name": "amount",
                    "issue_code": ErrorCodeRegistry.EXP_INVALID_ROW,
                    "message": f"Invalid or missing expense amount: '{amount_val}'",
                    "raw_value": str(amount_val),
                })
                continue

            date_val = row_dict.get("expense_date")
            parsed_date = parse_flexible_date(date_val, default_date or date.today())

            desc = row_dict.get("description")
            desc_str = str(desc).strip() if desc is not None else None
            if desc_str and len(desc_str) > 255:
                desc_str = desc_str[:255]

            cat = row_dict.get("category")
            cat_str = str(cat).strip() if cat is not None else None

            currency_str = str(row_dict.get("currency") or "IDR").strip().upper()[:3]
            if not currency_str:
                currency_str = "IDR"

            parsed_rows.append({
                "source_row_number": row_idx,
                "source_sheet_name": file_name or "CSV",
                "expense_date": parsed_date,
                "category": cat_str,
                "description": desc_str,
                "amount": parsed_amount,
                "currency": currency_str,
                "branch": row_dict.get("branch"),
                "branch_id": row_dict.get("branch_id") or default_branch_id,
                "raw_payload_json": raw_payload,
                "extraction_confidence_json": row_dict.get("extraction_confidence_json"),
            })

        if not parsed_rows and not parse_errors:
            raise ValidationException(
                errors={"file": "CSV contains no data rows", "error_code": ErrorCodeRegistry.EXP_EMPTY_FILE},
                message="Spreadsheet contains no data rows",
                error_code=ErrorCodeRegistry.EXP_EMPTY_FILE,
            )

        return parsed_rows, parse_errors

    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"Error parsing expense CSV: {e}", exc_info=True)
        raise ValidationException(
            errors={"file": f"Failed to parse CSV file: {str(e)}", "error_code": ErrorCodeRegistry.EXP_PARSE_ERROR},
            message="Malformed or corrupt spreadsheet file",
            error_code=ErrorCodeRegistry.EXP_PARSE_ERROR,
        )


def parse_expense_file(
    file_bytes: bytes,
    file_name: str,
    mime_type: Optional[str] = None,
    sheet_mappings: Optional[Dict[str, Optional[Any]]] = None,
    mapping_result: Optional[Any] = None,
    default_date: Optional[date] = None,
    default_branch_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Auto-detect Excel vs CSV and parse into expense dictionaries using semantic mapping."""
    lower_name = (file_name or "").lower()
    is_excel = (
        lower_name.endswith(".xlsx")
        or lower_name.endswith(".xls")
        or (mime_type and "spreadsheet" in mime_type)
        or file_bytes[:4] == b"PK\x03\x04"  # zip magic bytes for xlsx
    )

    if is_excel:
        return parse_expense_excel(
            file_bytes=file_bytes,
            file_name=file_name,
            sheet_mappings=sheet_mappings,
            mapping_result=mapping_result,
            default_date=default_date,
            default_branch_id=default_branch_id,
        )
    else:
        return parse_expense_csv(
            file_bytes=file_bytes,
            file_name=file_name,
            mapping_result=mapping_result,
            default_date=default_date,
            default_branch_id=default_branch_id,
        )

