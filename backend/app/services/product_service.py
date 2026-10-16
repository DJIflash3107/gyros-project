from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.product import Product
from app.models.schemas.product import ProductCreate, ProductUpdate
from app.helpers.exceptions import NotFoundException, ConflictException
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
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list[Product], dict]:
    query = db.query(Product).filter(Product.business_id == business_id)
    if category:
        query = query.filter(Product.category == category)
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)
    query = query.order_by(Product.id.asc())
    return paginate_query(query, page, page_size)


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
