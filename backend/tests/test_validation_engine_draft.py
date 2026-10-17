from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.branch import Branch
from app.models.product import Product
from app.models.sales_report_submission import SalesReportSubmission
from app.services.validation_engine import (
    resolve_or_create_product,
    resolve_or_create_branch,
    compute_missing_product_fields,
    compute_missing_branch_fields,
    validate_staging_rows,
)


def _setup_entities(db: Session):
    biz = Business(name="Draft Test Biz")
    db.add(biz)
    db.flush()

    branch = Branch(business_id=biz.id, name="Central Branch", branch_code="BR-01", is_active=True, status="active")
    product = Product(business_id=biz.id, name="Known Gyros", base_unit="portion", sku="GYR-01", is_active=True, status="active")
    db.add_all([branch, product])
    db.flush()

    sub = SalesReportSubmission(
        business_id=biz.id,
        submitted_by_user_id=1,
        input_method="spreadsheet",
        report_period_type="daily",
        coverage_start=date(2026, 10, 1),
        coverage_end=date(2026, 10, 1),
        status="pending",
        total_rows=0,
        accepted_rows=0,
        rejected_rows=0,
    )
    db.add(sub)
    db.flush()
    return biz, branch, product, sub


def test_resolve_known_product(db_session):
    biz, branch, product, _ = _setup_entities(db_session)

    pid, pname, draft, created = resolve_or_create_product(
        db=db_session,
        business_id=biz.id,
        raw_name="Known Gyros",
    )
    assert pid == product.id
    assert pname == product.name
    assert draft is None
    assert created is False


def test_resolve_unknown_product_creates_draft(db_session):
    biz, branch, _, _ = _setup_entities(db_session)

    pid, pname, draft, created = resolve_or_create_product(
        db=db_session,
        business_id=biz.id,
        raw_name="New Mystery Wrap",
    )
    assert pid is not None
    assert pname == "New Mystery Wrap"
    assert draft is not None
    assert draft.status == "draft"
    assert draft.is_active is False
    assert draft.auto_created_from == "New Mystery Wrap"
    assert created is True

    # Check missing fields
    missing = compute_missing_product_fields(draft)
    assert "sku" in missing
    assert "category" in missing

    # Repeating with same name should return existing draft (idempotent)
    pid2, pname2, draft2, created2 = resolve_or_create_product(
        db=db_session,
        business_id=biz.id,
        raw_name="new mystery wrap",  # case-insensitive check
    )
    assert pid2 == pid
    assert created2 is False


def test_resolve_branch_draft_and_idempotency(db_session):
    biz, branch, _, _ = _setup_entities(db_session)

    # 1. Known branch by ID
    bid, candidate_id, draft, created = resolve_or_create_branch(
        db=db_session,
        business_id=biz.id,
        branch_id=branch.id,
    )
    assert bid == branch.id
    assert draft is None
    assert created is False

    # 2. Unknown branch with name -> creates draft
    bid2, candidate_id2, draft2, created2 = resolve_or_create_branch(
        db=db_session,
        business_id=biz.id,
        raw_branch_name="Branch Bali",
    )
    assert bid2 is not None
    assert draft2 is not None
    assert draft2.name == "Branch Bali"
    assert draft2.status == "draft"
    assert draft2.is_active is False
    assert created2 is True

    # Missing fields for draft branch
    missing_b = compute_missing_branch_fields(draft2)
    assert "branch_code" in missing_b
    assert "address" in missing_b

    # 3. Repeat call -> returns existing draft
    bid3, _, draft3, created3 = resolve_or_create_branch(
        db=db_session,
        business_id=biz.id,
        raw_branch_name="branch bali",
    )
    assert bid3 == bid2
    assert created3 is False

    # 4. Unknown branch ID without name -> cannot create draft
    bid4, candidate_id4, draft4, created4 = resolve_or_create_branch(
        db=db_session,
        business_id=biz.id,
        branch_id=99999,
    )
    assert bid4 is None
    assert candidate_id4 == 99999
    assert draft4 is None
    assert created4 is False


def test_validate_staging_rows_draft_warnings(db_session):
    biz, branch, product, sub = _setup_entities(db_session)

    rows = [
        {
            "source_row_number": 1,
            "raw_product_name": "Brand New Doner",
            "branch_id": branch.id,
            "period_start": "2026-10-01",
            "period_end": "2026-10-01",
            "granularity": "daily",
            "sold_qty": 15,
        },
        {
            "source_row_number": 2,
            "raw_product_name": "Known Gyros",
            "branch_name": "Brand New Branch",
            "period_start": "2026-10-01",
            "period_end": "2026-10-01",
            "granularity": "daily",
            "sold_qty": 10,
        },
    ]

    staging_rows, issues = validate_staging_rows(
        db=db_session,
        business_id=biz.id,
        submission_id=sub.id,
        rows=rows,
        coverage_start=date(2026, 10, 1),
        coverage_end=date(2026, 10, 1),
        report_period_type="daily",
        is_vision=False,
    )

    assert len(staging_rows) == 2
    # Both rows should have status pending_review (due to draft warnings, no errors)
    assert staging_rows[0].review_status == "pending_review"
    assert staging_rows[1].review_status == "pending_review"

    # Check issue codes
    issue_codes = [i.issue_code for i in issues]
    assert "RPT-VAL-011" in issue_codes  # draft product created
    assert "RPT-VAL-012" in issue_codes  # draft branch created

    # Severities should be warning
    draft_prod_issue = next(i for i in issues if i.issue_code == "RPT-VAL-011")
    assert draft_prod_issue.severity == "warning"
    draft_branch_issue = next(i for i in issues if i.issue_code == "RPT-VAL-012")
    assert draft_branch_issue.severity == "warning"


def test_validate_staging_rows_missing_product_fails(db_session):
    biz, branch, product, sub = _setup_entities(db_session)

    # Empty raw_product_name cannot be resolved or turned into draft
    rows = [
        {
            "source_row_number": 1,
            "raw_product_name": "",
            "branch_id": branch.id,
            "period_start": "2026-10-01",
            "period_end": "2026-10-01",
            "granularity": "daily",
            "sold_qty": 15,
        }
    ]

    staging_rows, issues = validate_staging_rows(
        db=db_session,
        business_id=biz.id,
        submission_id=sub.id,
        rows=rows,
        coverage_start=date(2026, 10, 1),
        coverage_end=date(2026, 10, 1),
        report_period_type="daily",
        is_vision=False,
    )

    assert len(staging_rows) == 1
    assert staging_rows[0].review_status == "needs_correction"
    assert any(i.issue_code == "RPT-VAL-001" and i.severity == "error" for i in issues)


def test_validate_staging_rows_single_date_fallback_and_monthly_coverage(db_session):
    biz, branch, product, sub = _setup_entities(db_session)

    # Row only has a single date (period_start: "2026-08-15"), no period_end, no granularity
    # Submission is monthly spanning August 2026
    rows = [
        {
            "source_row_number": 1,
            "raw_product_name": product.name,
            "branch_id": branch.id,
            "period_start": "2026-08-15",
            "sold_qty": 20,
        }
    ]

    staging_rows, issues = validate_staging_rows(
        db=db_session,
        business_id=biz.id,
        submission_id=sub.id,
        rows=rows,
        coverage_start=date(2026, 8, 1),
        coverage_end=date(2026, 8, 31),
        report_period_type="monthly",
        is_vision=False,
    )

    assert len(staging_rows) == 1
    row = staging_rows[0]
    # Intelligent fallback sets period_end equal to period_start, and granularity to daily
    assert row.period_start == date(2026, 8, 15)
    assert row.period_end == date(2026, 8, 15)
    assert row.granularity == "daily"
    # Row should be completely ready without any date or granularity errors/warnings
    assert row.review_status == "ready"
    assert not any(i.issue_code in ("RPT-VAL-003", "RPT-VAL-005") for i in issues)
