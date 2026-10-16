from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.product import Product
from app.models.product_alias import ProductAlias
from app.models.user import User
from app.models.schemas.product_alias import ProductAliasCreate, ProductAliasUpdate
from app.helpers.exceptions import NotFoundException, ConflictException
from app.helpers.pagination import paginate_query


def create_alias(
    db: Session,
    business_id: int,
    data: ProductAliasCreate,
    current_user: User,
) -> ProductAlias:
    # Verify product belongs to this business
    product = db.query(Product).filter(
        Product.id == data.product_id,
        Product.business_id == business_id,
    ).first()
    if not product:
        raise NotFoundException(
            message="Product not found",
            errors={"product_id": f"Product with ID {data.product_id} does not exist in this business"},
        )

    # Check unique normalized alias in business
    existing_alias = db.query(ProductAlias).filter(
        ProductAlias.business_id == business_id,
        ProductAlias.normalized_alias == data.normalized_alias,
    ).first()
    if existing_alias:
        raise ConflictException(
            message="Product alias creation failed",
            errors={"normalized_alias": f"Alias '{data.normalized_alias}' is already registered in this business"},
        )

    alias = ProductAlias(
        business_id=business_id,
        product_id=data.product_id,
        alias_name=data.alias_name,
        normalized_alias=data.normalized_alias,
        created_by_user_id=current_user.id,
    )
    db.add(alias)
    db.commit()
    db.refresh(alias)
    return alias


def list_aliases(
    db: Session,
    business_id: int,
    product_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list[ProductAlias], dict]:
    query = db.query(ProductAlias).filter(ProductAlias.business_id == business_id)
    if product_id is not None:
        query = query.filter(ProductAlias.product_id == product_id)
    query = query.order_by(ProductAlias.id.asc())
    return paginate_query(query, page, page_size)


def get_alias(db: Session, business_id: int, alias_id: int) -> ProductAlias:
    alias = db.query(ProductAlias).filter(
        ProductAlias.id == alias_id,
        ProductAlias.business_id == business_id,
    ).first()
    if not alias:
        raise NotFoundException(
            message="Product alias not found",
            errors={"alias": f"Alias with ID {alias_id} does not exist in this business"},
        )
    return alias


def update_alias(
    db: Session,
    business_id: int,
    alias_id: int,
    data: ProductAliasUpdate,
) -> ProductAlias:
    alias = get_alias(db, business_id, alias_id)
    update_data = data.model_dump(exclude_unset=True)

    if "normalized_alias" in update_data and update_data["normalized_alias"] != alias.normalized_alias:
        existing = db.query(ProductAlias).filter(
            ProductAlias.business_id == business_id,
            ProductAlias.normalized_alias == update_data["normalized_alias"],
        ).first()
        if existing:
            raise ConflictException(
                message="Product alias update failed",
                errors={"normalized_alias": f"Alias '{update_data['normalized_alias']}' is already registered in this business"},
            )

    for key, value in update_data.items():
        setattr(alias, key, value)

    db.commit()
    db.refresh(alias)
    return alias


def delete_alias(db: Session, business_id: int, alias_id: int) -> None:
    alias = get_alias(db, business_id, alias_id)
    db.delete(alias)
    db.commit()
