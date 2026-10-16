import csv
import io
import re
from typing import Any, Dict, List, Optional, Tuple
import openpyxl

from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.exceptions import ValidationException
from app.helpers.logging import logger
from app.services.semantic_mapper import SemanticMappingResult


COLUMN_MAPPING = {
    # Product
    "product": "raw_product_name",
    "product_name": "raw_product_name",
    "nama_produk": "raw_product_name",
    "nama": "raw_product_name",
    "item": "raw_product_name",
    "item_name": "raw_product_name",
    "nama_item": "raw_product_name",
    "product_id": "product_id",
    "id_produk": "product_id",
    # Branch
    "branch": "branch_id",
    "branch_id": "branch_id",
    "id_cabang": "branch_id",
    "cabang": "branch_id",
    "nama_cabang": "branch_id",
    # Period & Granularity
    "period_start": "period_start",
    "start_date": "period_start",
    "tanggal_mulai": "period_start",
    "mulai": "period_start",
    "tanggal": "period_start",
    "date": "period_start",
    "period_end": "period_end",
    "end_date": "period_end",
    "tanggal_selesai": "period_end",
    "selesai": "period_end",
    "granularity": "granularity",
    "tipe_periode": "granularity",
    # Quantities
    "prepared_qty": "prepared_qty",
    "prepared": "prepared_qty",
    "qty_disiapkan": "prepared_qty",
    "disiapkan": "prepared_qty",
    "opening_stock_qty": "opening_stock_qty",
    "opening_stock": "opening_stock_qty",
    "stok_awal": "opening_stock_qty",
    "awal": "opening_stock_qty",
    "received_qty": "received_qty",
    "received": "received_qty",
    "qty_diterima": "received_qty",
    "diterima": "received_qty",
    "masuk": "received_qty",
    "available_stock_qty": "available_stock_qty",
    "available_stock": "available_stock_qty",
    "stok_tersedia": "available_stock_qty",
    "tersedia": "available_stock_qty",
    "sold_qty": "sold_qty",
    "sold": "sold_qty",
    "qty_terjual": "sold_qty",
    "terjual": "sold_qty",
    "leftover_qty": "leftover_qty",
    "leftover": "leftover_qty",
    "sisa": "leftover_qty",
    "stok_akhir": "leftover_qty",
    "spoiled_qty": "spoiled_qty",
    "spoiled": "spoiled_qty",
    "basi": "spoiled_qty",
    "damaged_qty": "damaged_qty",
    "damaged": "damaged_qty",
    "rusak": "damaged_qty",
    "staff_meals_qty": "staff_meals_qty",
    "staff_meals": "staff_meals_qty",
    "makan_karyawan": "staff_meals_qty",
    "donated_qty": "donated_qty",
    "donated": "donated_qty",
    "donasi": "donated_qty",
    "other_disposition_qty": "other_disposition_qty",
    "other_disposition": "other_disposition_qty",
    "disposisi_lain": "other_disposition_qty",
    # Revenue
    "recorded_revenue": "recorded_revenue",
    "revenue": "recorded_revenue",
    "pendapatan": "recorded_revenue",
    "omset": "recorded_revenue",
    "total_penjualan": "recorded_revenue",
    "sales": "recorded_revenue",
}


def normalize_header(header: str) -> str:
    """Normalize raw column header to standard snake_case."""
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", header.strip().lower()).strip("_")
    return COLUMN_MAPPING.get(clean, clean)


def normalize_header_from_mapping(header: str, mapping: Optional[SemanticMappingResult] = None) -> str:
    """Apply LLM-derived mapping for a given source header, falling back to static mapping."""
    if mapping and mapping.mappings:
        norm_h = header.strip().lower()
        for entry in mapping.mappings:
            if entry.source_column.strip().lower() == norm_h:
                if entry.target_field == "_skip":
                    return f"_skip_{header}"
                return entry.target_field
    return normalize_header(header)


def is_csv_content(mime_type: str, file_name: str) -> bool:
    """Determine if input is a CSV file."""
    mt = (mime_type or "").lower()
    fn = (file_name or "").lower()
    return "csv" in mt or "text/plain" in mt or fn.endswith(".csv")


def is_excel_content(mime_type: str, file_name: str) -> bool:
    """Determine if input is an Excel file."""
    mt = (mime_type or "").lower()
    fn = (file_name or "").lower()
    return (
        "spreadsheet" in mt
        or "excel" in mt
        or fn.endswith(".xlsx")
        or fn.endswith(".xls")
        or fn.endswith(".xlsm")
    )


def parse_csv(
    file_bytes: bytes,
    mapping_result: Optional[SemanticMappingResult] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse CSV bytes into normalized row dictionaries."""
    text_content = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text_content = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if text_content is None:
        raise ValidationException(
            errors={"file": "Failed to decode CSV text with supported encodings", "error_code": ErrorCodeRegistry.RPT_MALFORMED_FILE},
            message="Malformed or corrupt CSV file",
            error_code=ErrorCodeRegistry.RPT_MALFORMED_FILE,
        )

    # Check for empty file
    if not text_content.strip():
        raise ValidationException(
            errors={"file": "Spreadsheet contains no data rows", "error_code": ErrorCodeRegistry.RPT_EMPTY_FILE},
            message="Spreadsheet contains no data rows",
            error_code=ErrorCodeRegistry.RPT_EMPTY_FILE,
        )

    stream = io.StringIO(text_content)
    try:
        # Detect delimiter using sniffer if possible, default to comma
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
                errors={"file": "Spreadsheet contains no headers", "error_code": ErrorCodeRegistry.RPT_EMPTY_FILE},
                message="Spreadsheet contains no data rows",
                error_code=ErrorCodeRegistry.RPT_EMPTY_FILE,
            )

        col_keys = [normalize_header_from_mapping(str(c), mapping_result) for c in header_row]

        parsed_rows: List[Dict[str, Any]] = []
        parse_errors: List[Dict[str, Any]] = []
        data_row_count = 0

        for row_idx, row in enumerate(reader, start=2):
            if not any(str(cell).strip() for cell in row):
                continue

            data_row_count += 1
            raw_payload: Dict[str, Any] = {}
            row_dict: Dict[str, Any] = {"source_row_number": row_idx}

            for col_idx, cell in enumerate(row):
                orig_col = header_row[col_idx] if col_idx < len(header_row) else f"col_{col_idx+1}"
                norm_col = col_keys[col_idx] if col_idx < len(col_keys) else f"col_{col_idx+1}"
                cell_val = cell.strip() if isinstance(cell, str) else cell
                raw_payload[orig_col] = cell_val

                if cell_val != "":
                    row_dict[norm_col] = cell_val

            row_dict["raw_payload_json"] = raw_payload
            if mapping_result:
                row_dict["extraction_confidence_json"] = {
                    "mapping_method": "llm" if not mapping_result.fallback_used else "static_fallback",
                    "model": mapping_result.model_used,
                    "column_confidences": {
                        entry.source_column: {
                            "target": entry.target_field,
                            "confidence": entry.confidence,
                            "reasoning": entry.reasoning,
                        }
                        for entry in mapping_result.mappings
                    },
                    "warnings": mapping_result.warnings,
                }
            parsed_rows.append(row_dict)

        if data_row_count == 0:
            raise ValidationException(
                errors={"file": "Spreadsheet contains no data rows", "error_code": ErrorCodeRegistry.RPT_EMPTY_FILE},
                message="Spreadsheet contains no data rows",
                error_code=ErrorCodeRegistry.RPT_EMPTY_FILE,
            )

        return parsed_rows, parse_errors

    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"Error parsing CSV file: {e}", exc_info=True)
        raise ValidationException(
            errors={"file": f"Failed to parse CSV file: {str(e)}", "error_code": ErrorCodeRegistry.RPT_MALFORMED_FILE},
            message="Malformed or corrupt spreadsheet file",
            error_code=ErrorCodeRegistry.RPT_MALFORMED_FILE,
        )


def _parse_single_sheet(
    sheet: Any,
    sheet_name: str,
    mapping_result: Optional[SemanticMappingResult] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse a single worksheet into row dictionaries, with source_sheet_name attached."""
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
    col_keys = [normalize_header_from_mapping(h, mapping_result) for h in header_strings]

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

            if cell is not None and str(cell).strip() != "":
                row_dict[norm_col] = cell

        row_dict["raw_payload_json"] = raw_payload
        if mapping_result:
            row_dict["extraction_confidence_json"] = {
                "mapping_method": "llm" if not mapping_result.fallback_used else "static_fallback",
                "model": mapping_result.model_used,
                "column_confidences": {
                    entry.source_column: {
                        "target": entry.target_field,
                        "confidence": entry.confidence,
                        "reasoning": entry.reasoning,
                    }
                    for entry in mapping_result.mappings
                },
                "warnings": mapping_result.warnings,
            }
        parsed_rows.append(row_dict)

    return parsed_rows, parse_errors


def parse_excel(
    file_bytes: bytes,
    mapping_result: Optional[SemanticMappingResult] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse XLSX bytes into normalized row dictionaries from the active worksheet."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as e:
        logger.error(f"Error loading Excel workbook: {e}", exc_info=True)
        raise ValidationException(
            errors={"file": f"Invalid or corrupt Excel workbook: {str(e)}", "error_code": ErrorCodeRegistry.RPT_MALFORMED_FILE},
            message="Malformed or corrupt spreadsheet file",
            error_code=ErrorCodeRegistry.RPT_MALFORMED_FILE,
        )

    try:
        sheet = wb.active
        if sheet is None:
            raise ValidationException(
                errors={"file": "No active worksheet found in workbook", "error_code": ErrorCodeRegistry.RPT_EMPTY_FILE},
                message="Spreadsheet contains no data rows",
                error_code=ErrorCodeRegistry.RPT_EMPTY_FILE,
            )

        parsed_rows, parse_errors = _parse_single_sheet(sheet, sheet.title, mapping_result)

        if not parsed_rows:
            raise ValidationException(
                errors={"file": "Spreadsheet contains no data rows", "error_code": ErrorCodeRegistry.RPT_EMPTY_FILE},
                message="Spreadsheet contains no data rows",
                error_code=ErrorCodeRegistry.RPT_EMPTY_FILE,
            )

        return parsed_rows, parse_errors

    finally:
        wb.close()


def parse_excel_workbook(
    file_bytes: bytes,
    sheet_mappings: Dict[str, Optional[SemanticMappingResult]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parse multiple worksheets in an Excel workbook according to sheet_mappings.
    Only sheets present in sheet_mappings will be parsed.
    Raises ValidationException if workbook is corrupt or no data rows extracted.
    """
    if not file_bytes:
        raise ValidationException(
            errors={"file": "File is empty", "error_code": ErrorCodeRegistry.RPT_EMPTY_FILE},
            message="Spreadsheet contains no data rows",
            error_code=ErrorCodeRegistry.RPT_EMPTY_FILE,
        )

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as e:
        logger.error(f"Error loading Excel workbook: {e}", exc_info=True)
        raise ValidationException(
            errors={"file": f"Invalid or corrupt Excel workbook: {str(e)}", "error_code": ErrorCodeRegistry.RPT_MALFORMED_FILE},
            message="Malformed or corrupt spreadsheet file",
            error_code=ErrorCodeRegistry.RPT_MALFORMED_FILE,
        )

    try:
        all_parsed_rows: List[Dict[str, Any]] = []
        all_parse_errors: List[Dict[str, Any]] = []

        for sheet_name, mapping_result in sheet_mappings.items():
            if sheet_name not in wb.sheetnames:
                continue
            sheet = wb[sheet_name]
            p_rows, p_errs = _parse_single_sheet(sheet, sheet_name, mapping_result)
            all_parsed_rows.extend(p_rows)
            all_parse_errors.extend(p_errs)

        if not all_parsed_rows:
            raise ValidationException(
                errors={"file": "Spreadsheet contains no data rows across relevant worksheets", "error_code": ErrorCodeRegistry.RPT_EMPTY_FILE},
                message="Spreadsheet contains no data rows",
                error_code=ErrorCodeRegistry.RPT_EMPTY_FILE,
            )

        return all_parsed_rows, all_parse_errors
    finally:
        wb.close()


def parse_spreadsheet(
    file_bytes: bytes,
    mime_type: str,
    file_name: str,
    mapping_result: Optional[SemanticMappingResult] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parse spreadsheet (Excel or CSV) into row dictionaries.
    Raises ValidationException if file is invalid or empty.
    """
    if not file_bytes:
        raise ValidationException(
            errors={"file": "File is empty", "error_code": ErrorCodeRegistry.RPT_EMPTY_FILE},
            message="Spreadsheet contains no data rows",
            error_code=ErrorCodeRegistry.RPT_EMPTY_FILE,
        )

    if is_csv_content(mime_type, file_name):
        return parse_csv(file_bytes, mapping_result=mapping_result)
    elif is_excel_content(mime_type, file_name):
        return parse_excel(file_bytes, mapping_result=mapping_result)
    else:
        # Try excel first, then csv
        try:
            return parse_excel(file_bytes, mapping_result=mapping_result)
        except ValidationException as e:
            if e.error_code == ErrorCodeRegistry.RPT_EMPTY_FILE:
                raise
            try:
                return parse_csv(file_bytes, mapping_result=mapping_result)
            except Exception:
                raise ValidationException(
                    errors={"file": "Unsupported spreadsheet format. Please upload .xlsx, .xls, or .csv", "error_code": ErrorCodeRegistry.RPT_UNSUPPORTED_FORMAT},
                    message="Unsupported file format",
                    error_code=ErrorCodeRegistry.RPT_UNSUPPORTED_FORMAT,
                )
