from datetime import date
import hashlib
import json
import re
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.product import Product
from app.models.sales_report_submission import SalesReportSubmission
from app.models.sales_report_staging_row import SalesReportStagingRow
from app.models.import_issue import ImportIssue
from app.models.user import User
from app.models.schemas.sales_report_submission import SalesReportSubmissionResponse
from app.models.schemas.import_issue import ImportIssueResponse, ImportIssueCreate
from app.models.schemas.sales_report_processing import (
    ManualFormBatchCreate,
    ProcessingResultResponse,
    ProcessingSummary,
)
from app.configs.settings import settings
from app.helpers.error_codes import ErrorCodeRegistry
from app.helpers.exceptions import ConflictException, ValidationException, NotFoundException
from app.helpers.logging import logger
from app.services.input_profiler import (
    profile_excel,
    profile_csv,
    profile_excel_workbook,
    WorkbookProfile,
)
from app.services.semantic_mapper import (
    map_columns_with_llm,
    classify_sheet_roles,
    build_fallback_mapping,
    SemanticMappingResult,
    SheetClassification,
)
from app.services.spreadsheet_parser import (
    parse_spreadsheet,
    parse_csv,
    parse_excel,
    parse_excel_workbook,
    is_excel_content,
    normalize_header,
)
from app.services.photo_extractor import extract_from_photo
from app.services.validation_engine import validate_staging_rows


MAX_SPREADSHEET_BYTES = 10 * 1024 * 1024  # 10 MB limit


def _run_coroutine_sync(coro):
    """Run an async coroutine synchronously in an isolated thread with its own event loop."""
    import asyncio
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def format_sse(event_name: str, payload: Dict[str, Any]) -> str:
    """Format SSE payload with event and data lines."""
    body = {"event": event_name, **payload}
    return f"event: {event_name}\ndata: {json.dumps(body, default=str)}\n\n"


def compute_sha256(file_bytes: bytes) -> str:
    """Compute hex SHA-256 digest of file bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def check_duplicate_submission(
    db: Session,
    business_id: int,
    sha256_hex: str,
) -> None:
    """Check if file with same SHA-256 already exists for this business."""
    existing = (
        db.query(SalesReportSubmission)
        .filter(
            SalesReportSubmission.business_id == business_id,
            SalesReportSubmission.source_sha256 == sha256_hex,
            SalesReportSubmission.status.notin_(["rejected", "failed"]),
        )
        .first()
    )
    if existing:
        raise ConflictException(
            errors={
                "source_sha256": f"This file was already submitted as submission ID {existing.id}",
                "error_code": ErrorCodeRegistry.RPT_DUPLICATE_FILE,
            },
            message="Duplicate file detected",
            error_code=ErrorCodeRegistry.RPT_DUPLICATE_FILE,
        )


def _deduplicate_cross_sheet(
    rows: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[ImportIssueCreate]]:
    """
    Prevent duplicate imports or double-counting across sheets by checking
    a normalized composite key: (raw_product, branch, period_start, period_end).
    If a record from a subsequent sheet matches an already seen record from an earlier sheet,
    it is filtered out and flagged as an ImportIssue.
    """
    seen: Dict[Tuple[str, str, str, str], Tuple[str, int]] = {}
    unique_rows: List[Dict[str, Any]] = []
    issues: List[ImportIssueCreate] = []

    for row in rows:
        sheet_name = str(row.get("source_sheet_name") or "")
        row_num = row.get("source_row_number")

        raw_prod = str(
            row.get("raw_product_name")
            or row.get("product")
            or row.get("item")
            or row.get("product_id")
            or ""
        ).strip().lower()

        if not raw_prod:
            unique_rows.append(row)
            continue

        branch = str(row.get("branch_id") or row.get("branch") or "").strip()
        p_start = str(row.get("period_start") or row.get("date") or "").strip()
        p_end = str(row.get("period_end") or p_start or "").strip()

        key = (raw_prod, branch, p_start, p_end)
        if key in seen:
            orig_sheet, orig_row = seen[key]
            issues.append(
                ImportIssueCreate(
                    source_row_number=row_num,
                    field_name="raw_product_name",
                    issue_code=ErrorCodeRegistry.RPT_CROSS_SHEET_DUPLICATE,
                    severity="warning",
                    message=(
                        f"Duplicate record detected across worksheets. Product '{raw_prod}' "
                        f"in worksheet '{sheet_name}' (row {row_num}) was already provided in "
                        f"worksheet '{orig_sheet}' (row {orig_row}); row skipped to prevent double-counting."
                    ),
                    raw_value=f"{sheet_name}!row_{row_num}",
                )
            )
        else:
            seen[key] = (sheet_name, row_num if row_num is not None else 0)
            unique_rows.append(row)

    return unique_rows, issues


def _persist_staging_rows_and_issues(
    db: Session,
    submission_id: int,
    staging_rows_create: list,
    issues_create: list,
) -> Tuple[List[SalesReportStagingRow], List[ImportIssue], ProcessingSummary]:
    """Persist staging rows and link them with issues transactionally."""
    created_rows: List[SalesReportStagingRow] = []
    rows_by_source_num: Dict[int, SalesReportStagingRow] = {}

    for row_data in staging_rows_create:
        staging_row = SalesReportStagingRow(
            submission_id=submission_id,
            source_row_number=row_data.source_row_number,
            source_sheet_name=row_data.source_sheet_name,
            raw_payload_json=row_data.raw_payload_json,
            raw_product_name=row_data.raw_product_name,
            branch_id=row_data.branch_id,
            product_id=row_data.product_id,
            period_start=row_data.period_start,
            period_end=row_data.period_end,
            granularity=row_data.granularity,
            prepared_qty=row_data.prepared_qty,
            opening_stock_qty=row_data.opening_stock_qty,
            received_qty=row_data.received_qty,
            available_stock_qty=row_data.available_stock_qty,
            sold_qty=row_data.sold_qty,
            leftover_qty=row_data.leftover_qty,
            spoiled_qty=row_data.spoiled_qty,
            damaged_qty=row_data.damaged_qty,
            staff_meals_qty=row_data.staff_meals_qty,
            donated_qty=row_data.donated_qty,
            other_disposition_qty=row_data.other_disposition_qty,
            recorded_revenue=row_data.recorded_revenue,
            extraction_confidence_json=row_data.extraction_confidence_json,
            review_status=row_data.review_status,
        )
        db.add(staging_row)
        created_rows.append(staging_row)

    db.flush()

    for r in created_rows:
        if r.source_row_number is not None:
            rows_by_source_num[r.source_row_number] = r

    created_issues: List[ImportIssue] = []
    for issue_data in issues_create:
        staging_row_id = None
        if issue_data.source_row_number is not None and issue_data.source_row_number in rows_by_source_num:
            staging_row_id = rows_by_source_num[issue_data.source_row_number].id

        issue = ImportIssue(
            submission_id=submission_id,
            staging_row_id=staging_row_id,
            source_row_number=issue_data.source_row_number,
            field_name=issue_data.field_name,
            issue_code=issue_data.issue_code,
            severity=issue_data.severity,
            message=issue_data.message,
            raw_value=issue_data.raw_value,
            resolution_status="open",
        )
        db.add(issue)
        created_issues.append(issue)

    db.flush()

    # Calculate summary
    ready_count = sum(1 for r in created_rows if r.review_status == "ready")
    pending_count = sum(1 for r in created_rows if r.review_status == "pending_review")
    needs_corr_count = sum(1 for r in created_rows if r.review_status == "needs_correction")

    summary = ProcessingSummary(
        total_rows=len(created_rows),
        ready_rows=ready_count,
        pending_review_rows=pending_count,
        needs_correction_rows=needs_corr_count,
        issue_count=len(created_issues),
    )

    return created_rows, created_issues, summary


def process_file_submission(
    db: Session,
    business_id: int,
    current_user: User,
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
    input_method: str,
    report_period_type: str,
    coverage_start: date,
    coverage_end: date,
    branch_id: Optional[int] = None,
) -> ProcessingResultResponse:
    """
    Process spreadsheet or non-streaming photo upload submission.
    """
    # Validate branch existence if provided
    if branch_id is not None:
        branch = (
            db.query(Branch)
            .filter(
                Branch.id == branch_id,
                Branch.business_id == business_id,
                Branch.is_active == True,
            )
            .first()
        )
        if not branch:
            raise NotFoundException(
                errors={"branch_id": f"Branch with ID {branch_id} does not exist in this business"},
                message="Branch not found",
            )

    # Validate file size
    if input_method == "spreadsheet":
        if len(file_bytes) > MAX_SPREADSHEET_BYTES:
            raise ValidationException(
                errors={
                    "file": f"Spreadsheet exceeds maximum size limit of 10MB ({len(file_bytes)} bytes)",
                    "error_code": ErrorCodeRegistry.RPT_FILE_TOO_LARGE,
                },
                message="File exceeds size limit",
                error_code=ErrorCodeRegistry.RPT_FILE_TOO_LARGE,
            )
        # Verify content type compatibility
        if mime_type.startswith("image/"):
            raise ValidationException(
                errors={
                    "file": "Spreadsheet input method cannot accept image files",
                    "error_code": ErrorCodeRegistry.RPT_UNSUPPORTED_FORMAT,
                },
                message="Unsupported file format",
                error_code=ErrorCodeRegistry.RPT_UNSUPPORTED_FORMAT,
            )
    elif input_method == "photo":
        max_img_bytes = settings.VISION_MAX_IMAGE_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_img_bytes:
            raise ValidationException(
                errors={
                    "file": f"Image exceeds maximum size limit of {settings.VISION_MAX_IMAGE_SIZE_MB}MB",
                    "error_code": ErrorCodeRegistry.RPT_IMAGE_TOO_LARGE,
                },
                message="Image exceeds size limit",
                error_code=ErrorCodeRegistry.RPT_IMAGE_TOO_LARGE,
            )
        if not (mime_type.startswith("image/") or any(file_name.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp"))):
            raise ValidationException(
                errors={
                    "file": "Photo input method requires an image file (JPEG, PNG, WEBP)",
                    "error_code": ErrorCodeRegistry.RPT_UNSUPPORTED_FORMAT,
                },
                message="Unsupported file format",
                error_code=ErrorCodeRegistry.RPT_UNSUPPORTED_FORMAT,
            )

    # Compute SHA-256 and check duplicates
    sha256_hex = compute_sha256(file_bytes)
    check_duplicate_submission(db, business_id, sha256_hex)

    # Create submission record in "processing" state
    submission = SalesReportSubmission(
        business_id=business_id,
        submitted_by_user_id=current_user.id,
        branch_id=branch_id,
        input_method=input_method,
        report_period_type=report_period_type,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        source_file_name=file_name,
        source_mime_type=mime_type,
        source_sha256=sha256_hex,
        status="processing",
        total_rows=0,
        accepted_rows=0,
        rejected_rows=0,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    try:
        # Extract rows
        mapping_results: List[SemanticMappingResult] = []
        sheets_processed: List[str] = []
        sheets_skipped: List[str] = []
        sheets_ambiguous: List[str] = []
        extra_issues: List[ImportIssueCreate] = []

        if input_method == "spreadsheet":
            is_excel = is_excel_content(mime_type, file_name)
            products = (
                db.query(Product)
                .filter(Product.business_id == business_id, Product.is_active == True)
                .all()
            )
            known_prod_names = {p.name for p in products if p.name}
            biz_context = {"products": [{"name": p.name} for p in products]}

            if is_excel:
                workbook_profile = profile_excel_workbook(file_bytes)
                sheets_skipped.extend(workbook_profile.skipped_sheets)

                classifications = _run_coroutine_sync(
                    classify_sheet_roles(workbook_profile.sheet_profiles, biz_context)
                )

                reference_sheets: List[str] = []
                for cls in classifications:
                    if cls.role == "sales":
                        sheets_processed.append(cls.sheet_name)
                    elif cls.role == "reference":
                        reference_sheets.append(cls.sheet_name)
                        sheets_skipped.append(cls.sheet_name)
                    elif cls.role in ("instructional", "expenses"):
                        sheets_skipped.append(cls.sheet_name)
                    else:  # ambiguous
                        sheets_ambiguous.append(cls.sheet_name)
                        extra_issues.append(
                            ImportIssueCreate(
                                source_row_number=None,
                                issue_code=ErrorCodeRegistry.RPT_AMBIGUOUS_SHEET,
                                severity="warning",
                                message=f"Worksheet '{cls.sheet_name}' has an unsupported or ambiguous layout and was skipped for review. Reason: {cls.reasoning or 'Unrecognized table structure'}",
                                raw_value=cls.sheet_name,
                            )
                        )

                # Retain relevant reference sheets for matching
                for p in workbook_profile.sheet_profiles:
                    if p.active_sheet_name in reference_sheets:
                        for idx, h in enumerate(p.headers):
                            h_clean = re.sub(r"[^a-zA-Z0-9]+", "_", str(h).strip().lower()).strip("_")
                            if h_clean in ("product", "product_name", "nama_produk", "item", "nama"):
                                for s_row in p.sample_rows:
                                    if idx < len(s_row) and s_row[idx]:
                                        val = str(s_row[idx]).strip()
                                        if val and val not in known_prod_names:
                                            biz_context["products"].append({"name": val})
                                            known_prod_names.add(val)

                if not sheets_processed:
                    raise ValidationException(
                        errors={"file": "Workbook contains no worksheets classified with sales report data", "error_code": ErrorCodeRegistry.RPT_EMPTY_FILE},
                        message="Spreadsheet contains no data rows",
                        error_code=ErrorCodeRegistry.RPT_EMPTY_FILE,
                    )

                # Map columns per sales sheet
                sheet_mappings: Dict[str, Optional[SemanticMappingResult]] = {}
                profile_by_name = {p.active_sheet_name: p for p in workbook_profile.sheet_profiles}

                for s_name in sheets_processed:
                    s_profile = profile_by_name[s_name]
                    m_res = None
                    if settings.SEMANTIC_MAPPING_ENABLED:
                        try:
                            m_res = _run_coroutine_sync(map_columns_with_llm(s_profile, biz_context))
                        except Exception as e:
                            logger.warning(f"Failed to profile or semantically map sheet {s_name}: {e}. Falling back to default mapping.")
                            m_res = build_fallback_mapping(s_profile.headers, reason=f"Semantic mapping error: {str(e)}")
                    else:
                        m_res = build_fallback_mapping(s_profile.headers, reason="Semantic mapping disabled")
                    sheet_mappings[s_name] = m_res
                    if m_res:
                        mapping_results.append(m_res)

                raw_rows, _ = parse_excel_workbook(file_bytes, sheet_mappings)
                # Prevent duplicate imports or double-counting across sheets
                raw_rows, cross_sheet_issues = _deduplicate_cross_sheet(raw_rows)
                extra_issues.extend(cross_sheet_issues)
                is_vision = False

            else:
                # CSV parsing path
                sheets_processed.append("CSV")
                profile = profile_csv(file_bytes)
                if settings.SEMANTIC_MAPPING_ENABLED:
                    try:
                        m_res = _run_coroutine_sync(map_columns_with_llm(profile, biz_context))
                    except Exception as e:
                        logger.warning(f"Failed to profile or semantically map CSV: {e}. Falling back to default parsing.")
                        m_res = build_fallback_mapping(profile.headers, reason=f"Semantic mapping error: {str(e)}")
                else:
                    m_res = build_fallback_mapping(profile.headers, reason="Semantic mapping disabled")

                if m_res:
                    mapping_results.append(m_res)

                raw_rows, _ = parse_csv(file_bytes, mapping_result=m_res)
                is_vision = False

        else:
            # Synchronous photo path
            products = (
                db.query(Product)
                .filter(Product.business_id == business_id, Product.is_active == True)
                .all()
            )
            biz_context = {"products": [{"name": p.name} for p in products]}
            raw_rows, _ = _run_coroutine_sync(extract_from_photo(file_bytes, mime_type, biz_context))
            is_vision = True

        # Validation engine
        staging_rows_create, issues_create = validate_staging_rows(
            db=db,
            business_id=business_id,
            submission_id=submission.id,
            rows=raw_rows,
            branch_id_default=branch_id,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            report_period_type=report_period_type,
            is_vision=is_vision,
        )

        # Low-confidence semantic mapping warning issues
        for m_res in mapping_results:
            if m_res and m_res.mappings:
                for entry in m_res.mappings:
                    if entry.confidence < settings.SEMANTIC_MAPPING_CONFIDENCE_THRESHOLD:
                        issues_create.append(
                            ImportIssueCreate(
                                source_row_number=None,
                                field_name=entry.target_field if entry.target_field != "_skip" else None,
                                issue_code=ErrorCodeRegistry.RPT_LOW_CONFIDENCE,
                                severity="warning",
                                message=f"Column '{entry.source_column}' mapped to '{entry.target_field}' with low confidence ({entry.confidence:.0%}). Reason: {entry.reasoning or 'Ambiguous mapping'}",
                                raw_value=entry.source_column,
                            )
                        )

        # Append ambiguous sheet warnings and cross-sheet duplicate issues
        issues_create.extend(extra_issues)

        # Persist rows and issues
        created_rows, created_issues, summary = _persist_staging_rows_and_issues(
            db=db,
            submission_id=submission.id,
            staging_rows_create=staging_rows_create,
            issues_create=issues_create,
        )

        # Enrich summary with sheet metrics
        summary.sheets_processed = sheets_processed
        summary.sheets_skipped = sheets_skipped
        summary.sheets_ambiguous = sheets_ambiguous

        submission.status = "reviewed"
        submission.total_rows = summary.total_rows
        submission.rejected_rows = summary.needs_correction_rows
        submission.accepted_rows = 0  # Only set upon explicit confirmation
        db.commit()
        db.refresh(submission)

        return ProcessingResultResponse(
            submission=SalesReportSubmissionResponse.model_validate(submission),
            summary=summary,
            issues=[ImportIssueResponse.model_validate(i) for i in created_issues],
        )

    except Exception:
        # Mark submission failed on unexpected error
        submission.status = "failed"
        db.commit()
        raise


def process_manual_form_batch(
    db: Session,
    business_id: int,
    current_user: User,
    batch_data: ManualFormBatchCreate,
) -> ProcessingResultResponse:
    """
    Process batch of manual form entries.
    """
    if batch_data.branch_id is not None:
        branch = (
            db.query(Branch)
            .filter(
                Branch.id == batch_data.branch_id,
                Branch.business_id == business_id,
                Branch.is_active == True,
            )
            .first()
        )
        if not branch:
            raise NotFoundException(
                errors={"branch_id": f"Branch with ID {batch_data.branch_id} does not exist in this business"},
                message="Branch not found",
            )

    submission = SalesReportSubmission(
        business_id=business_id,
        submitted_by_user_id=current_user.id,
        branch_id=batch_data.branch_id,
        input_method="form",
        report_period_type=batch_data.report_period_type,
        coverage_start=batch_data.coverage_start,
        coverage_end=batch_data.coverage_end,
        source_file_name=None,
        source_mime_type=None,
        source_sha256=None,
        status="processing",
        total_rows=0,
        accepted_rows=0,
        rejected_rows=0,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    try:
        raw_rows: List[Dict[str, Any]] = []
        for idx, row_item in enumerate(batch_data.rows, start=1):
            row_dict = row_item.model_dump()
            row_dict["source_row_number"] = idx
            row_dict["raw_payload_json"] = row_item.model_dump(mode="json")
            raw_rows.append(row_dict)

        staging_rows_create, issues_create = validate_staging_rows(
            db=db,
            business_id=business_id,
            submission_id=submission.id,
            rows=raw_rows,
            branch_id_default=batch_data.branch_id,
            coverage_start=batch_data.coverage_start,
            coverage_end=batch_data.coverage_end,
            report_period_type=batch_data.report_period_type,
            is_vision=False,
        )

        created_rows, created_issues, summary = _persist_staging_rows_and_issues(
            db=db,
            submission_id=submission.id,
            staging_rows_create=staging_rows_create,
            issues_create=issues_create,
        )

        submission.status = "reviewed"
        submission.total_rows = summary.total_rows
        submission.rejected_rows = summary.needs_correction_rows
        submission.accepted_rows = 0
        db.commit()
        db.refresh(submission)

        return ProcessingResultResponse(
            submission=SalesReportSubmissionResponse.model_validate(submission),
            summary=summary,
            issues=[ImportIssueResponse.model_validate(i) for i in created_issues],
        )
    except Exception:
        submission.status = "failed"
        db.commit()
        raise


async def process_photo_submission_stream(
    db: Session,
    business_id: int,
    current_user: User,
    image_bytes: bytes,
    file_name: str,
    mime_type: str,
    report_period_type: str,
    coverage_start: date,
    coverage_end: date,
    branch_id: Optional[int] = None,
) -> AsyncIterator[str]:
    """
    Asynchronously process photo input yielding structured SSE progress events.
    """
    # Initial validation
    max_img_bytes = settings.VISION_MAX_IMAGE_SIZE_MB * 1024 * 1024
    if len(image_bytes) > max_img_bytes:
        err_msg = f"Image exceeds maximum size limit of {settings.VISION_MAX_IMAGE_SIZE_MB}MB"
        yield format_sse("report_error", {"error_code": ErrorCodeRegistry.RPT_IMAGE_TOO_LARGE, "message": err_msg})
        return

    sha256_hex = compute_sha256(image_bytes)
    existing = (
        db.query(SalesReportSubmission)
        .filter(
            SalesReportSubmission.business_id == business_id,
            SalesReportSubmission.source_sha256 == sha256_hex,
            SalesReportSubmission.status.notin_(["rejected", "failed"]),
        )
        .first()
    )
    if existing:
        yield format_sse(
            "report_error",
            {
                "error_code": ErrorCodeRegistry.RPT_DUPLICATE_FILE,
                "message": f"This file was already submitted as submission ID {existing.id}",
            },
        )
        return

    submission = SalesReportSubmission(
        business_id=business_id,
        submitted_by_user_id=current_user.id,
        branch_id=branch_id,
        input_method="photo",
        report_period_type=report_period_type,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        source_file_name=file_name,
        source_mime_type=mime_type,
        source_sha256=sha256_hex,
        status="processing",
        total_rows=0,
        accepted_rows=0,
        rejected_rows=0,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    yield format_sse("report_status", {"step": "extracting", "message": "Sending image to vision model..."})

    try:
        products = (
            db.query(Product)
            .filter(Product.business_id == business_id, Product.is_active == True)
            .all()
        )
        biz_context = {"products": [{"name": p.name} for p in products]}

        raw_rows, metadata = await extract_from_photo(
            image_bytes=image_bytes,
            mime_type=mime_type,
            business_context=biz_context,
        )
    except Exception as e:
        error_code = getattr(e, "error_code", ErrorCodeRegistry.RPT_EXTRACTION_FAILED)
        msg = getattr(e, "message", str(e))
        logger.error(f"Photo extraction failed: {msg}", exc_info=True)
        submission.status = "failed"
        db.commit()
        yield format_sse("report_error", {"error_code": error_code, "message": msg})
        return

    yield format_sse("report_status", {"step": "mapping", "message": "Structuring and verifying extracted fields..."})
    yield format_sse("report_status", {"step": "validating", "message": "Validating extracted rows..."})

    try:
        staging_rows_create, issues_create = validate_staging_rows(
            db=db,
            business_id=business_id,
            submission_id=submission.id,
            rows=raw_rows,
            branch_id_default=branch_id,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            report_period_type=report_period_type,
            is_vision=True,
        )

        error_issues_count = sum(1 for i in issues_create if i.severity == "error")
        ready_count = sum(1 for r in staging_rows_create if r.review_status == "ready")
        pending_count = sum(1 for r in staging_rows_create if r.review_status == "pending_review")
        needs_corr_count = sum(1 for r in staging_rows_create if r.review_status == "needs_correction")

        yield format_sse(
            "validation_result",
            {
                "total": len(staging_rows_create),
                "ready": ready_count,
                "pending_review": pending_count,
                "needs_correction": needs_corr_count,
                "errors": error_issues_count,
            },
        )

        yield format_sse("report_status", {"step": "staging", "message": "Persisting staging records..."})

        created_rows, created_issues, summary = _persist_staging_rows_and_issues(
            db=db,
            submission_id=submission.id,
            staging_rows_create=staging_rows_create,
            issues_create=issues_create,
        )

        submission.status = "reviewed"
        submission.total_rows = summary.total_rows
        submission.rejected_rows = summary.needs_correction_rows
        submission.accepted_rows = 0
        db.commit()
        db.refresh(submission)

        yield format_sse(
            "report_complete",
            {
                "submission_id": submission.id,
                "total_rows": summary.total_rows,
                "accepted_rows": 0,
                "rejected_rows": summary.needs_correction_rows,
                "summary": summary.model_dump(),
            },
        )

    except Exception as e:
        logger.error(f"Error during photo staging: {e}", exc_info=True)
        submission.status = "failed"
        db.commit()
        yield format_sse("report_error", {"error_code": ErrorCodeRegistry.RPT_PROCESSING_ERROR, "message": str(e)})
