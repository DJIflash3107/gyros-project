from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple, Set
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.product import Product
from app.models.product_alias import ProductAlias
from app.models.sales_report_observation import SalesReportObservation
from app.models.schemas.sales_report_staging_row import SalesReportStagingRowCreate, Granularity
from app.models.schemas.import_issue import ImportIssueCreate
from app.helpers.logging import logger


QUANTITY_FIELDS = [
    "prepared_qty",
    "opening_stock_qty",
    "received_qty",
    "available_stock_qty",
    "sold_qty",
    "leftover_qty",
    "spoiled_qty",
    "damaged_qty",
    "staff_meals_qty",
    "donated_qty",
    "other_disposition_qty",
]


def parse_date(val: Any) -> Optional[date]:
    """Parse date from date, datetime, or string."""
    if val is None or val == "":
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        val_str = val.strip()
        # Try ISO format YYYY-MM-DD
        try:
            return date.fromisoformat(val_str)
        except ValueError:
            pass
        # Common alternative formats
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(val_str, fmt).date()
            except ValueError:
                continue
    return None


def parse_decimal(val: Any) -> Optional[Decimal]:
    """Parse numeric value to Decimal."""
    if val is None or val == "":
        return None
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    if isinstance(val, str):
        cleaned = val.strip().replace(",", "")
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
    return None


def resolve_product(
    db: Session,
    business_id: int,
    raw_name: Optional[str] = None,
    product_id: Optional[int] = None,
) -> Tuple[Optional[int], Optional[str]]:
    """
    Resolve product ID and name.
    1. If product_id given, check if valid & active in business.
    2. Exact product name match.
    3. Case-insensitive product name match.
    4. Normalized alias match via ProductAlias table.
    """
    if product_id is not None:
        prod = (
            db.query(Product)
            .filter(
                Product.id == product_id,
                Product.business_id == business_id,
                Product.is_active == True,
            )
            .first()
        )
        if prod:
            return prod.id, prod.name

    if raw_name:
        clean_name = raw_name.strip()
        # Exact match
        prod = (
            db.query(Product)
            .filter(
                Product.business_id == business_id,
                Product.name == clean_name,
                Product.is_active == True,
            )
            .first()
        )
        if prod:
            return prod.id, prod.name

        # Case-insensitive match
        prod = (
            db.query(Product)
            .filter(
                Product.business_id == business_id,
                func.lower(Product.name) == clean_name.lower(),
                Product.is_active == True,
            )
            .first()
        )
        if prod:
            return prod.id, prod.name

        # Normalized alias lookup
        alias = (
            db.query(ProductAlias)
            .filter(
                ProductAlias.business_id == business_id,
                ProductAlias.normalized_alias == clean_name.lower(),
            )
            .first()
        )
        if alias:
            prod = (
                db.query(Product)
                .filter(
                    Product.id == alias.product_id,
                    Product.is_active == True,
                )
                .first()
            )
            if prod:
                return prod.id, prod.name

    return None, None


def resolve_branch(
    db: Session,
    business_id: int,
    branch_id: Optional[int] = None,
    branch_id_default: Optional[int] = None,
) -> Tuple[Optional[int], Optional[int]]:
    """
    Check if branch belongs to business and is active.
    Returns (resolved_branch_id, candidate_branch_id_used).
    """
    candidate = branch_id if branch_id is not None else branch_id_default
    if candidate is None:
        return None, None

    branch = (
        db.query(Branch)
        .filter(
            Branch.id == candidate,
            Branch.business_id == business_id,
            Branch.is_active == True,
        )
        .first()
    )
    if branch:
        return branch.id, candidate
    return None, candidate


def validate_staging_rows(
    db: Session,
    business_id: int,
    submission_id: int,
    rows: List[Dict[str, Any]],
    branch_id_default: Optional[int] = None,
    coverage_start: Optional[date] = None,
    coverage_end: Optional[date] = None,
    report_period_type: Optional[str] = None,
    is_vision: bool = False,
) -> Tuple[List[SalesReportStagingRowCreate], List[ImportIssueCreate]]:
    """
    Validate and normalize extracted/submitted rows against the 10 domain rules.
    Returns (staging_rows, issues).
    """
    staging_rows: List[SalesReportStagingRowCreate] = []
    issues: List[ImportIssueCreate] = []
    seen_row_keys: Set[Tuple[int, int, date, date]] = set()

    today = date.today()

    for idx, row_dict in enumerate(rows, start=1):
        row_issues: List[ImportIssueCreate] = []
        source_row_num = row_dict.get("source_row_number") or idx

        # Raw values
        raw_product_name = row_dict.get("raw_product_name") or row_dict.get("product_name") or row_dict.get("item")
        if raw_product_name:
            raw_product_name = str(raw_product_name).strip()

        row_product_id = row_dict.get("product_id")
        try:
            row_product_id = int(row_product_id) if row_product_id is not None else None
        except (ValueError, TypeError):
            row_product_id = None

        row_branch_id = row_dict.get("branch_id")
        try:
            row_branch_id = int(row_branch_id) if row_branch_id is not None else None
        except (ValueError, TypeError):
            row_branch_id = None

        # Check 1: Product Resolution (RPT-VAL-001, error)
        resolved_prod_id, resolved_prod_name = resolve_product(
            db=db,
            business_id=business_id,
            raw_name=raw_product_name,
            product_id=row_product_id,
        )
        if not resolved_prod_id:
            row_issues.append(
                ImportIssueCreate(
                    source_row_number=source_row_num,
                    field_name="raw_product_name",
                    issue_code="RPT-VAL-001",
                    severity="error",
                    message=f"Product could not be resolved from raw name '{raw_product_name or row_product_id}'",
                    raw_value=str(raw_product_name or row_product_id),
                )
            )

        # Check 2: Branch Existence (RPT-VAL-002, error)
        resolved_b_id, candidate_b_id = resolve_branch(
            db=db,
            business_id=business_id,
            branch_id=row_branch_id,
            branch_id_default=branch_id_default,
        )
        if not resolved_b_id:
            row_issues.append(
                ImportIssueCreate(
                    source_row_number=source_row_num,
                    field_name="branch_id",
                    issue_code="RPT-VAL-002",
                    severity="error",
                    message=f"Branch ID {candidate_b_id} does not exist or is inactive in this business",
                    raw_value=str(candidate_b_id) if candidate_b_id is not None else None,
                )
            )

        # Check 3: Date Validity (RPT-VAL-003, error)
        raw_start = row_dict.get("period_start")
        raw_end = row_dict.get("period_end")
        period_start = parse_date(raw_start)
        period_end = parse_date(raw_end)

        # If period_start or period_end not provided in row, check if coverage dates can default
        if period_start is None and coverage_start is not None and report_period_type == "daily" and coverage_start == coverage_end:
            period_start = coverage_start
        if period_end is None and coverage_end is not None and report_period_type == "daily" and coverage_start == coverage_end:
            period_end = coverage_end

        if period_start is None:
            row_issues.append(
                ImportIssueCreate(
                    source_row_number=source_row_num,
                    field_name="period_start",
                    issue_code="RPT-VAL-003",
                    severity="error",
                    message="Missing or invalid period_start date",
                    raw_value=str(raw_start) if raw_start is not None else None,
                )
            )

        if period_end is None:
            row_issues.append(
                ImportIssueCreate(
                    source_row_number=source_row_num,
                    field_name="period_end",
                    issue_code="RPT-VAL-003",
                    severity="error",
                    message="Missing or invalid period_end date",
                    raw_value=str(raw_end) if raw_end is not None else None,
                )
            )

        if period_start is not None and period_end is not None:
            if period_end < period_start:
                row_issues.append(
                    ImportIssueCreate(
                        source_row_number=source_row_num,
                        field_name="period_end",
                        issue_code="RPT-VAL-003",
                        severity="error",
                        message=f"period_end ({period_end}) cannot be before period_start ({period_start})",
                        raw_value=str(period_end),
                    )
                )
            if period_start > today or period_end > today:
                row_issues.append(
                    ImportIssueCreate(
                        source_row_number=source_row_num,
                        field_name="period_end",
                        issue_code="RPT-VAL-003",
                        severity="error",
                        message=f"Observation period cannot be in the future (today: {today})",
                        raw_value=str(period_end),
                    )
                )

            # Check 4: Date Within Coverage (RPT-VAL-004, warning)
            if coverage_start is not None and coverage_end is not None:
                if period_start < coverage_start or period_end > coverage_end:
                    row_issues.append(
                        ImportIssueCreate(
                            source_row_number=source_row_num,
                            field_name="period_start",
                            issue_code="RPT-VAL-004",
                            severity="warning",
                            message=f"Row period ({period_start} to {period_end}) is outside submission coverage ({coverage_start} to {coverage_end})",
                            raw_value=f"{period_start} to {period_end}",
                        )
                    )

        # Check 5: Granularity Consistency (RPT-VAL-005, warning)
        raw_granularity = row_dict.get("granularity")
        granularity = raw_granularity or report_period_type or "daily"
        if granularity not in ("daily", "weekly", "monthly", "custom_range"):
            row_issues.append(
                ImportIssueCreate(
                    source_row_number=source_row_num,
                    field_name="granularity",
                    issue_code="RPT-VAL-005",
                    severity="warning",
                    message=f"Invalid granularity '{granularity}'",
                    raw_value=str(raw_granularity),
                )
            )
            granularity = "daily"
        else:
            if report_period_type in ("daily", "weekly", "monthly") and granularity != report_period_type:
                row_issues.append(
                    ImportIssueCreate(
                        source_row_number=source_row_num,
                        field_name="granularity",
                        issue_code="RPT-VAL-005",
                        severity="warning",
                        message=f"Row granularity '{granularity}' does not match submission period type '{report_period_type}'",
                        raw_value=str(granularity),
                    )
                )
            if granularity == "daily" and period_start is not None and period_end is not None:
                if (period_end - period_start).days > 0:
                    row_issues.append(
                        ImportIssueCreate(
                            source_row_number=source_row_num,
                            field_name="granularity",
                            issue_code="RPT-VAL-005",
                            severity="warning",
                            message=f"Daily granularity spans {(period_end - period_start).days + 1} days",
                            raw_value=str(granularity),
                        )
                    )

        # Check 6: Quantity Non-negative (RPT-VAL-006, error)
        parsed_quantities: Dict[str, Optional[Decimal]] = {}
        for q_field in QUANTITY_FIELDS:
            parsed_q = parse_decimal(row_dict.get(q_field))
            if parsed_q is not None and parsed_q < Decimal("0"):
                row_issues.append(
                    ImportIssueCreate(
                        source_row_number=source_row_num,
                        field_name=q_field,
                        issue_code="RPT-VAL-006",
                        severity="error",
                        message=f"Quantity '{q_field}' cannot be negative ({parsed_q})",
                        raw_value=str(parsed_q),
                    )
                )
            parsed_quantities[q_field] = parsed_q

        # Revenue
        parsed_revenue = parse_decimal(row_dict.get("recorded_revenue"))
        if parsed_revenue is not None and parsed_revenue < Decimal("0"):
            row_issues.append(
                ImportIssueCreate(
                    source_row_number=source_row_num,
                    field_name="recorded_revenue",
                    issue_code="RPT-VAL-006",
                    severity="error",
                    message=f"Recorded revenue cannot be negative ({parsed_revenue})",
                    raw_value=str(parsed_revenue),
                )
            )

        # Check 7: Intra-submission Duplicates (RPT-VAL-007, warning)
        if resolved_prod_id and resolved_b_id and period_start and period_end:
            key = (resolved_prod_id, resolved_b_id, period_start, period_end)
            if key in seen_row_keys:
                row_issues.append(
                    ImportIssueCreate(
                        source_row_number=source_row_num,
                        field_name=None,
                        issue_code="RPT-VAL-007",
                        severity="warning",
                        message=f"Duplicate row within submission for product {resolved_prod_id}, branch {resolved_b_id}, period {period_start} to {period_end}",
                        raw_value=None,
                    )
                )
            seen_row_keys.add(key)

            # Check 8: Cross-submission Overlap (RPT-VAL-008, warning)
            overlap = (
                db.query(SalesReportObservation)
                .filter(
                    SalesReportObservation.business_id == business_id,
                    SalesReportObservation.branch_id == resolved_b_id,
                    SalesReportObservation.product_id == resolved_prod_id,
                    SalesReportObservation.record_status == "active",
                    SalesReportObservation.period_start <= period_end,
                    SalesReportObservation.period_end >= period_start,
                )
                .first()
            )
            if overlap:
                row_issues.append(
                    ImportIssueCreate(
                        source_row_number=source_row_num,
                        field_name="period_start",
                        issue_code="RPT-VAL-008",
                        severity="warning",
                        message=f"Active observation already exists for branch {resolved_b_id}, product {resolved_prod_id} covering {overlap.period_start} to {overlap.period_end}",
                        raw_value=f"{period_start} to {period_end}",
                    )
                )

        # Check 9: Stock Balance Check (RPT-VAL-009, info)
        opening = parsed_quantities.get("opening_stock_qty")
        received = parsed_quantities.get("received_qty")
        available = parsed_quantities.get("available_stock_qty")
        if opening is not None and received is not None and available is not None:
            if opening + received != available:
                row_issues.append(
                    ImportIssueCreate(
                        source_row_number=source_row_num,
                        field_name="available_stock_qty",
                        issue_code="RPT-VAL-009",
                        severity="info",
                        message=f"Stock balance discrepancy: opening ({opening}) + received ({received}) != available ({available})",
                        raw_value=str(available),
                    )
                )

        # Check 10: Revenue Plausibility (RPT-VAL-010, info)
        sold = parsed_quantities.get("sold_qty")
        if parsed_revenue is not None and parsed_revenue > Decimal("0"):
            if sold is not None and sold == Decimal("0"):
                row_issues.append(
                    ImportIssueCreate(
                        source_row_number=source_row_num,
                        field_name="recorded_revenue",
                        issue_code="RPT-VAL-010",
                        severity="info",
                        message=f"Recorded revenue is {parsed_revenue} but sold quantity is 0",
                        raw_value=str(parsed_revenue),
                    )
                )

        # Determine review_status
        has_errors = any(i.severity == "error" for i in row_issues)
        has_warnings_or_info = any(i.severity in ("warning", "info") for i in row_issues)

        if is_vision:
            # Safety constraint: OCR output is NEVER auto-finalized and NEVER "ready"
            review_status = "needs_correction" if has_errors else "pending_review"
        else:
            if has_errors:
                review_status = "needs_correction"
            elif has_warnings_or_info:
                review_status = "pending_review"
            else:
                review_status = "ready"

        # Construct raw payload json
        raw_payload = row_dict.get("raw_payload_json") or row_dict

        staging_row = SalesReportStagingRowCreate(
            source_row_number=source_row_num,
            raw_payload_json=raw_payload,
            raw_product_name=raw_product_name or resolved_prod_name,
            branch_id=resolved_b_id,
            product_id=resolved_prod_id,
            period_start=period_start,
            period_end=period_end,
            granularity=granularity,
            prepared_qty=parsed_quantities.get("prepared_qty"),
            opening_stock_qty=parsed_quantities.get("opening_stock_qty"),
            received_qty=parsed_quantities.get("received_qty"),
            available_stock_qty=parsed_quantities.get("available_stock_qty"),
            sold_qty=parsed_quantities.get("sold_qty"),
            leftover_qty=parsed_quantities.get("leftover_qty"),
            spoiled_qty=parsed_quantities.get("spoiled_qty"),
            damaged_qty=parsed_quantities.get("damaged_qty"),
            staff_meals_qty=parsed_quantities.get("staff_meals_qty"),
            donated_qty=parsed_quantities.get("donated_qty"),
            other_disposition_qty=parsed_quantities.get("other_disposition_qty"),
            recorded_revenue=parsed_revenue,
            extraction_confidence_json=row_dict.get("extraction_confidence_json"),
            review_status=review_status,
        )

        staging_rows.append(staging_row)
        issues.extend(row_issues)

    return staging_rows, issues
