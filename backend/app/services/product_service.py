from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.product import Product
from app.models.sales_report_staging_row import SalesReportStagingRow
from app.models.import_issue import ImportIssue
from app.models.schemas.product import ProductCreate, ProductUpdate, ProductActivate
from app.helpers.exceptions import NotFoundException, ConflictException, ValidationException
from app.helpers.pagination import paginate_query


def create_product(db: Session, business_id: int, data: ProductCreate) -> Product:
    # Check name unique per business
    existing_name = db.query(Product).filter(
        Product.business_id == business_id,
        Product.name == data.name,
    ).first()
    if existing_name:
        raise ConflictException(
            message="Product creation failed",
            errors={"name": f"A product with the name '{data.name}' already exists in this business"},
        )

    # Check sku unique per business if provided
    if data.sku:
        existing_sku = db.query(Product).filter(
            Product.business_id == business_id,
            Product.sku == data.sku,
        ).first()
        if existing_sku:
            raise ConflictException(
                message="Product creation failed",
                errors={"sku": f"A product with SKU '{data.sku}' already exists in this business"},
            )

    product = Product(
        business_id=business_id,
        name=data.name,
        sku=data.sku,
        category=data.category,
        base_unit=data.base_unit,
        is_active=data.is_active,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def list_products(
    db: Session,
    business_id: int,
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list[Product], dict]:
    query = db.query(Product).filter(Product.business_id == business_id)
    if category:
        query = query.filter(Product.category == category)
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)
    if status is not None:
        if status != "all":
            query = query.filter(Product.status == status)
    else:
        query = query.filter(Product.status != "draft")
    query = query.order_by(Product.id.asc())
    return paginate_query(query, page, page_size)


def activate_draft_product(
    db: Session,
    business_id: int,
    product_id: int,
    data: ProductActivate,
) -> Product:
    product = get_product(db, business_id, product_id)

    if product.status != "draft":
        raise ValidationException(
            message="Product activation failed",
            errors={"status": f"Product with ID {product_id} is not in draft status (current: '{product.status}')"},
        )

    # Check name unique if renaming
    new_name = data.name.strip() if data.name else product.name
    if new_name != product.name:
        existing_name = db.query(Product).filter(
            Product.business_id == business_id,
            Product.name == new_name,
            Product.id != product.id,
        ).first()
        if existing_name:
            raise ConflictException(
                message="Product activation failed",
                errors={"name": f"A product with the name '{new_name}' already exists in this business"},
            )
        product.name = new_name

    # Check sku unique if provided
    if data.sku:
        existing_sku = db.query(Product).filter(
            Product.business_id == business_id,
            Product.sku == data.sku,
            Product.id != product.id,
        ).first()
        if existing_sku:
            raise ConflictException(
                message="Product activation failed",
                errors={"sku": f"A product with SKU '{data.sku}' already exists in this business"},
            )
        product.sku = data.sku

    product.base_unit = data.base_unit
    if data.category is not None:
        product.category = data.category

    product.status = "active"
    product.is_active = True

    # Re-evaluate linked staging rows and resolve RPT-VAL-011 issues
    staging_rows = (
        db.query(SalesReportStagingRow)
        .filter(SalesReportStagingRow.product_id == product.id)
        .all()
    )
    if staging_rows:
        row_ids = [r.id for r in staging_rows]
        issues = (
            db.query(ImportIssue)
            .filter(
                ImportIssue.staging_row_id.in_(row_ids),
                ImportIssue.issue_code == "RPT-VAL-011",
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
    db.refresh(product)
    return product


def get_product(db: Session, business_id: int, product_id: int) -> Product:
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.business_id == business_id,
    ).first()
    if not product:
        raise NotFoundException(
            message="Product not found",
            errors={"product": f"Product with ID {product_id} does not exist in this business"},
        )
    return product


def update_product(db: Session, business_id: int, product_id: int, data: ProductUpdate) -> Product:
    product = get_product(db, business_id, product_id)
    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] != product.name:
        existing = db.query(Product).filter(
            Product.business_id == business_id,
            Product.name == update_data["name"],
        ).first()
        if existing:
            raise ConflictException(
                message="Product update failed",
                errors={"name": f"A product with the name '{update_data['name']}' already exists in this business"},
            )

    if "sku" in update_data and update_data["sku"] and update_data["sku"] != product.sku:
        existing = db.query(Product).filter(
            Product.business_id == business_id,
            Product.sku == update_data["sku"],
        ).first()
        if existing:
            raise ConflictException(
                message="Product update failed",
                errors={"sku": f"A product with SKU '{update_data['sku']}' already exists in this business"},
            )

    for key, value in update_data.items():
        setattr(product, key, value)

    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, business_id: int, product_id: int) -> None:
    product = get_product(db, business_id, product_id)
    db.delete(product)
    db.commit()
