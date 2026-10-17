from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.branch import Branch
from app.models.sales_report_staging_row import SalesReportStagingRow
from app.models.import_issue import ImportIssue
from app.models.schemas.branch import BranchCreate, BranchUpdate, BranchActivate
from app.helpers.exceptions import NotFoundException, ConflictException, ValidationException
from app.helpers.pagination import paginate_query


def create_branch(db: Session, business_id: int, data: BranchCreate) -> Branch:
    existing = db.query(Branch).filter(
        Branch.business_id == business_id,
        Branch.name == data.name,
    ).first()
    if existing:
        raise ConflictException(
            message="Branch creation failed",
            errors={"name": f"A branch with the name '{data.name}' already exists in this business"},
        )

    branch = Branch(
        business_id=business_id,
        name=data.name,
        branch_code=data.branch_code,
        address=data.address,
        is_active=data.is_active,
    )
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return branch


def list_branches(
    db: Session,
    business_id: int,
    is_active: Optional[bool] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list[Branch], dict]:
    query = db.query(Branch).filter(Branch.business_id == business_id)
    if is_active is not None:
        query = query.filter(Branch.is_active == is_active)
    if status is not None:
        if status != "all":
            query = query.filter(Branch.status == status)
    else:
        query = query.filter(Branch.status != "draft")
    query = query.order_by(Branch.id.asc())
    return paginate_query(query, page, page_size)


def activate_draft_branch(
    db: Session,
    business_id: int,
    branch_id: int,
    data: BranchActivate,
) -> Branch:
    branch = get_branch(db, business_id, branch_id)

    if branch.status != "draft":
        raise ValidationException(
            message="Branch activation failed",
            errors={"status": f"Branch with ID {branch_id} is not in draft status (current: '{branch.status}')"},
        )

    new_name = data.name.strip() if data.name else branch.name
    if new_name != branch.name:
        existing_name = db.query(Branch).filter(
            Branch.business_id == business_id,
            Branch.name == new_name,
            Branch.id != branch.id,
        ).first()
        if existing_name:
            raise ConflictException(
                message="Branch activation failed",
                errors={"name": f"A branch with the name '{new_name}' already exists in this business"},
            )
        branch.name = new_name

    if data.branch_code is not None:
        branch.branch_code = data.branch_code
    if data.address is not None:
        branch.address = data.address

    branch.status = "active"
    branch.is_active = True

    # Re-evaluate linked staging rows and resolve RPT-VAL-012 issues
    staging_rows = (
        db.query(SalesReportStagingRow)
        .filter(SalesReportStagingRow.branch_id == branch.id)
        .all()
    )
    if staging_rows:
        row_ids = [r.id for r in staging_rows]
        issues = (
            db.query(ImportIssue)
            .filter(
                ImportIssue.staging_row_id.in_(row_ids),
                ImportIssue.issue_code == "RPT-VAL-012",
            )
            .all()
        )
        for issue in issues:
            issue.resolution_status = "resolved"

        for r in staging_rows:
            open_issues = (
                db.query(ImportIssue)
                .filter(
                    ImportIssue.staging_row_id == r.id,
                    ImportIssue.resolution_status == "open",
                )
                .all()
            )
            has_errors = any(i.severity == "error" for i in open_issues)
            has_warnings = any(i.severity in ("warning", "info") for i in open_issues)
            if not has_errors and not has_warnings:
                r.review_status = "ready"
            elif not has_errors:
                r.review_status = "pending_review"
            else:
                r.review_status = "needs_correction"

    db.commit()
    db.refresh(branch)
    return branch


def get_branch(db: Session, business_id: int, branch_id: int) -> Branch:
    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.business_id == business_id,
    ).first()
    if not branch:
        raise NotFoundException(
            message="Branch not found",
            errors={"branch": f"Branch with ID {branch_id} does not exist in this business"},
        )
    return branch


def update_branch(db: Session, business_id: int, branch_id: int, data: BranchUpdate) -> Branch:
    branch = get_branch(db, business_id, branch_id)
    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] != branch.name:
        existing = db.query(Branch).filter(
            Branch.business_id == business_id,
            Branch.name == update_data["name"],
        ).first()
        if existing:
            raise ConflictException(
                message="Branch update failed",
                errors={"name": f"A branch with the name '{update_data['name']}' already exists in this business"},
            )

    for key, value in update_data.items():
        setattr(branch, key, value)

    db.commit()
    db.refresh(branch)
    return branch


def delete_branch(db: Session, business_id: int, branch_id: int) -> None:
    branch = get_branch(db, business_id, branch_id)
    db.delete(branch)
    db.commit()
