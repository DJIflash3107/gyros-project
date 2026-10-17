from datetime import datetime, timezone
from typing import Optional, Tuple, Dict
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from app.models.branch import Branch
from app.models.product import Product
from app.models.sales_report_submission import SalesReportSubmission
from app.models.sales_report_staging_row import SalesReportStagingRow
from app.models.sales_report_observation import SalesReportObservation
from app.models.user import User
from app.models.schemas.sales_report_submission import (
    SalesReportSubmissionCreate,
    SalesReportSubmissionUpdate,
)
from app.helpers.exceptions import NotFoundException, ConflictException, ValidationException
from app.helpers.pagination import paginate_query
from app.helpers.logging import logger


def create_submission(
    db: Session,
    business_id: int,
    data: SalesReportSubmissionCreate,
    current_user: User,
) -> SalesReportSubmission:
    if data.branch_id is not None:
        branch = db.query(Branch).filter(
            Branch.id == data.branch_id,
            Branch.business_id == business_id,
        ).first()
        if not branch:
            raise NotFoundException(
                message="Branch not found",
                errors={"branch_id": f"Branch with ID {data.branch_id} does not exist in this business"},
            )

    submission = SalesReportSubmission(
        business_id=business_id,
        submitted_by_user_id=current_user.id,
        branch_id=data.branch_id,
        input_method=data.input_method,
        report_period_type=data.report_period_type,
        coverage_start=data.coverage_start,
        coverage_end=data.coverage_end,
        source_file_name=data.source_file_name,
        source_mime_type=data.source_mime_type,
        source_storage_key=data.source_storage_key,
        source_sha256=data.source_sha256,
        status="pending",
        total_rows=0,
        accepted_rows=0,
        rejected_rows=0,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def list_submissions(
    db: Session,
    business_id: int,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list[SalesReportSubmission], dict]:
    query = db.query(SalesReportSubmission).filter(SalesReportSubmission.business_id == business_id)
    if status:
        query = query.filter(SalesReportSubmission.status == status)
    query = query.order_by(SalesReportSubmission.id.desc())
    return paginate_query(query, page, page_size)


def get_submission(db: Session, business_id: int, submission_id: int) -> SalesReportSubmission:
    submission = db.query(SalesReportSubmission).filter(
        SalesReportSubmission.id == submission_id,
        SalesReportSubmission.business_id == business_id,
    ).first()
    if not submission:
        raise NotFoundException(
            message="Submission not found",
            errors={"submission": f"Submission with ID {submission_id} does not exist in this business"},
        )
    return submission


def update_submission(
    db: Session,
    business_id: int,
    submission_id: int,
    data: SalesReportSubmissionUpdate,
) -> SalesReportSubmission:
    submission = get_submission(db, business_id, submission_id)
    update_data = data.model_dump(exclude_unset=True)

    if "branch_id" in update_data and update_data["branch_id"] is not None:
        branch = db.query(Branch).filter(
            Branch.id == update_data["branch_id"],
            Branch.business_id == business_id,
        ).first()
        if not branch:
            raise NotFoundException(
                message="Branch not found",
                errors={"branch_id": f"Branch with ID {update_data['branch_id']} does not exist in this business"},
            )

    for key, value in update_data.items():
        setattr(submission, key, value)

    db.commit()
    db.refresh(submission)
    return submission


def delete_submission(db: Session, business_id: int, submission_id: int) -> None:
    submission = get_submission(db, business_id, submission_id)
    db.delete(submission)
    db.commit()


def confirm_submission(
    db: Session,
    business_id: int,
    submission_id: int,
    current_user: User,
) -> SalesReportSubmission:
    """Transactional confirmation and observation conversion service."""
    submission = get_submission(db, business_id, submission_id)

    if submission.status == "confirmed":
        raise ConflictException(
            message="Confirmation failed",
            errors={"status": "Submission is already confirmed"},
        )

    # Check for unactivated draft products/branches referenced by staging rows in this submission
    draft_products = (
        db.query(Product)
        .join(SalesReportStagingRow, SalesReportStagingRow.product_id == Product.id)
        .filter(
            SalesReportStagingRow.submission_id == submission.id,
            SalesReportStagingRow.review_status.in_(["ready", "accepted", "pending_review"]),
            Product.status == "draft",
        )
        .distinct()
        .all()
    )
    if draft_products:
        draft_names = [f"'{p.name}' (ID {p.id})" for p in draft_products]
        raise ValidationException(
            message="Cannot confirm submission with draft products",
            errors={"products": f"Draft products must be activated before confirming: {', '.join(draft_names)}"},
        )

    draft_branches = (
        db.query(Branch)
        .join(SalesReportStagingRow, SalesReportStagingRow.branch_id == Branch.id)
        .filter(
            SalesReportStagingRow.submission_id == submission.id,
            SalesReportStagingRow.review_status.in_(["ready", "accepted", "pending_review"]),
            Branch.status == "draft",
        )
        .distinct()
        .all()
    )
    if draft_branches:
        draft_names = [f"'{b.name}' (ID {b.id})" for b in draft_branches]
        raise ValidationException(
            message="Cannot confirm submission with draft branches",
            errors={"branches": f"Draft branches must be activated before confirming: {', '.join(draft_names)}"},
        )

    staging_rows = db.query(SalesReportStagingRow).filter(
        SalesReportStagingRow.submission_id == submission.id
    ).all()

    accepted_count = 0
    rejected_count = 0

    for row in staging_rows:
        if row.review_status in ["ready", "accepted"]:
            # Ensure branch_id, product_id, period_start, period_end, granularity are set
            if not (row.branch_id and row.product_id and row.period_start and row.period_end and row.granularity):
                row.review_status = "needs_correction"
                rejected_count += 1
                continue

            # Check overlap with existing active observations
            overlap = db.query(SalesReportObservation).filter(
                SalesReportObservation.business_id == business_id,
                SalesReportObservation.branch_id == row.branch_id,
                SalesReportObservation.product_id == row.product_id,
                SalesReportObservation.record_status == "active",
                and_(
                    SalesReportObservation.period_start <= row.period_end,
                    SalesReportObservation.period_end >= row.period_start,
                ),
            ).first()

            if overlap:
                raise ConflictException(
                    message="Observation period overlap detected",
                    errors={
                        "overlap": (
                            f"Overlapping active observation already exists for branch {row.branch_id}, "
                            f"product {row.product_id} between {row.period_start} and {row.period_end}"
                        )
                    },
                )

            # Create observation record
            observation = SalesReportObservation(
                business_id=business_id,
                branch_id=row.branch_id,
                product_id=row.product_id,
                source_submission_id=submission.id,
                source_staging_row_id=row.id,
                period_start=row.period_start,
                period_end=row.period_end,
                granularity=row.granularity,
                prepared_qty=row.prepared_qty,
                opening_stock_qty=row.opening_stock_qty,
                received_qty=row.received_qty,
                available_stock_qty=row.available_stock_qty,
                sold_qty=row.sold_qty,
                leftover_qty=row.leftover_qty,
                spoiled_qty=row.spoiled_qty,
                damaged_qty=row.damaged_qty,
                staff_meals_qty=row.staff_meals_qty,
                donated_qty=row.donated_qty,
                other_disposition_qty=row.other_disposition_qty,
                recorded_revenue=row.recorded_revenue,
                record_status="active",
                created_by_user_id=current_user.id,
                updated_by_user_id=current_user.id,
            )
            db.add(observation)
            row.review_status = "accepted"
            accepted_count += 1
        else:
            rejected_count += 1

    now = datetime.now(timezone.utc)
    submission.total_rows = len(staging_rows)
    submission.accepted_rows = accepted_count
    submission.rejected_rows = rejected_count
    submission.status = "confirmed"
    submission.confirmed_at = now
    submission.completed_at = now

    # Cleanup orphan drafts that were auto-created but not used / unreferenced
    cleanup_result = _cleanup_orphan_drafts(db, submission.id, business_id)
    logger.info(
        f"Orphan draft cleanup for submission {submission.id}: "
        f"{cleanup_result['products_deleted']} products, "
        f"{cleanup_result['branches_deleted']} branches deleted"
    )

    db.commit()
    db.refresh(submission)
    return submission


def _cleanup_orphan_drafts(db: Session, submission_id: int, business_id: int) -> Dict[str, int]:
    """
    Delete draft Products/Branches for this business that were auto-created
    but are no longer referenced by any active/pending staging row across all submissions.
    Returns counts: {"products_deleted": N, "branches_deleted": N}.
    """
    draft_products = (
        db.query(Product)
        .filter(
            Product.business_id == business_id,
            Product.status == "draft",
        )
        .all()
    )

    products_deleted = 0
    for dp in draft_products:
        # Check if ANY unconfirmed / non-rejected staging row still references this draft
        ref_count = (
            db.query(SalesReportStagingRow)
            .join(SalesReportSubmission, SalesReportStagingRow.submission_id == SalesReportSubmission.id)
            .filter(
                SalesReportStagingRow.product_id == dp.id,
                SalesReportSubmission.status != "confirmed",
                SalesReportStagingRow.review_status != "rejected",
            )
            .count()
        )
        if ref_count == 0:
            db.delete(dp)
            products_deleted += 1

    draft_branches = (
        db.query(Branch)
        .filter(
            Branch.business_id == business_id,
            Branch.status == "draft",
        )
        .all()
    )

    branches_deleted = 0
    for db_branch in draft_branches:
        ref_count = (
            db.query(SalesReportStagingRow)
            .join(SalesReportSubmission, SalesReportStagingRow.submission_id == SalesReportSubmission.id)
            .filter(
                SalesReportStagingRow.branch_id == db_branch.id,
                SalesReportSubmission.status != "confirmed",
                SalesReportStagingRow.review_status != "rejected",
            )
            .count()
        )
        if ref_count == 0:
            db.delete(db_branch)
            branches_deleted += 1

    db.flush()
    return {"products_deleted": products_deleted, "branches_deleted": branches_deleted}

