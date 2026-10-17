from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.sales_report_submission import SalesReportSubmission
from app.models.sales_report_staging_row import SalesReportStagingRow
from app.models.schemas.sales_report_staging_row import (
    SalesReportStagingRowCreate,
    SalesReportStagingRowUpdate,
    SalesReportStagingRowBulkUpdate,
)
from app.helpers.exceptions import NotFoundException
from app.helpers.pagination import paginate_query


def create_staging_row(
    db: Session,
    submission_id: int,
    data: SalesReportStagingRowCreate,
) -> SalesReportStagingRow:
    submission = db.query(SalesReportSubmission).filter(
        SalesReportSubmission.id == submission_id
    ).first()
    if not submission:
        raise NotFoundException(
            message="Submission not found",
            errors={"submission_id": f"Submission with ID {submission_id} does not exist"},
        )

    row = SalesReportStagingRow(
        submission_id=submission_id,
        source_row_number=data.source_row_number,
        raw_payload_json=data.raw_payload_json,
        raw_product_name=data.raw_product_name,
        branch_id=data.branch_id,
        product_id=data.product_id,
        period_start=data.period_start,
        period_end=data.period_end,
        granularity=data.granularity,
        prepared_qty=data.prepared_qty,
        opening_stock_qty=data.opening_stock_qty,
        received_qty=data.received_qty,
        available_stock_qty=data.available_stock_qty,
        sold_qty=data.sold_qty,
        leftover_qty=data.leftover_qty,
        spoiled_qty=data.spoiled_qty,
        damaged_qty=data.damaged_qty,
        staff_meals_qty=data.staff_meals_qty,
        donated_qty=data.donated_qty,
        other_disposition_qty=data.other_disposition_qty,
        recorded_revenue=data.recorded_revenue,
        unit_price=data.unit_price,
        unit_cost=data.unit_cost,
        extraction_confidence_json=data.extraction_confidence_json,
        review_status=data.review_status,
        review_notes=data.review_notes,
    )

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_staging_rows(
    db: Session,
    submission_id: int,
    review_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list[SalesReportStagingRow], dict]:
    query = db.query(SalesReportStagingRow).filter(SalesReportStagingRow.submission_id == submission_id)
    if review_status:
        query = query.filter(SalesReportStagingRow.review_status == review_status)
    query = query.order_by(SalesReportStagingRow.id.asc())
    return paginate_query(query, page, page_size)


def get_staging_row(db: Session, submission_id: int, row_id: int) -> SalesReportStagingRow:
    row = db.query(SalesReportStagingRow).filter(
        SalesReportStagingRow.id == row_id,
        SalesReportStagingRow.submission_id == submission_id,
    ).first()
    if not row:
        raise NotFoundException(
            message="Staging row not found",
            errors={"staging_row": f"Staging row with ID {row_id} does not exist in this submission"},
        )
    return row


def update_staging_row(
    db: Session,
    submission_id: int,
    row_id: int,
    data: SalesReportStagingRowUpdate,
) -> SalesReportStagingRow:
    row = get_staging_row(db, submission_id, row_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def delete_staging_row(db: Session, submission_id: int, row_id: int) -> None:
    row = get_staging_row(db, submission_id, row_id)
    db.delete(row)
    db.commit()


def bulk_update_staging_rows(
    db: Session,
    submission_id: int,
    data: SalesReportStagingRowBulkUpdate,
) -> list[SalesReportStagingRow]:
    submission = db.query(SalesReportSubmission).filter(
        SalesReportSubmission.id == submission_id
    ).first()
    if not submission:
        raise NotFoundException(
            message="Submission not found",
            errors={"submission_id": f"Submission with ID {submission_id} does not exist"},
        )

    query = db.query(SalesReportStagingRow).filter(
        SalesReportStagingRow.submission_id == submission_id
    )

    if not data.apply_to_all and data.row_ids:
        query = query.filter(SalesReportStagingRow.id.in_(data.row_ids))

    if data.filter_review_status:
        query = query.filter(SalesReportStagingRow.review_status == data.filter_review_status)

    rows = query.order_by(SalesReportStagingRow.id.asc()).all()

    update_fields = {}
    if data.review_status is not None:
        update_fields["review_status"] = data.review_status
    if data.review_notes is not None:
        update_fields["review_notes"] = data.review_notes
    if data.branch_id is not None:
        update_fields["branch_id"] = data.branch_id
    if data.product_id is not None:
        update_fields["product_id"] = data.product_id

    for row in rows:
        for key, value in update_fields.items():
            setattr(row, key, value)

    if rows:
        db.commit()
        for row in rows:
            db.refresh(row)

    return rows

