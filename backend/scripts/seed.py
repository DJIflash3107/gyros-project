"""Database seeder for core entities.

Seeds: business, users, memberships, branches, products,
product cost/price history, and a small set of sales submissions
with observations.

Idempotent: safe to run multiple times; existing rows are skipped.

Usage:
    cd backend
    source .venv/bin/activate
    python -m scripts.seed
"""

import random
from datetime import date, timedelta
from decimal import Decimal

import bcrypt

from app.configs.database import SessionLocal
from app.models.business import Business
from app.models.business_membership import BusinessMembership
from app.models.branch import Branch
from app.models.product import Product
from app.models.product_cost_history import ProductCostHistory
from app.models.product_price_history import ProductPriceHistory
from app.models.sales_report_observation import SalesReportObservation
from app.models.sales_report_submission import SalesReportSubmission
from app.models.user import User

SALES_DAYS = 14
SALES_PER_PRODUCT_PER_DAY_RANGE = (5, 40)
SEED_PASSWORD = "password123"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def get_or_create_business(db) -> Business:
    business = db.query(Business).filter(Business.name == "Gyros Demo").first()
    if business:
        return business
    business = Business(name="Gyros Demo", currency="IDR", timezone="Asia/Jakarta")
    db.add(business)
    db.flush()
    return business


def get_or_create_user(db, full_name: str, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        if not user.password_hash:
            user.password_hash = hash_password(SEED_PASSWORD)
        return user
    user = User(
        full_name=full_name,
        email=email,
        password_hash=hash_password(SEED_PASSWORD),
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def ensure_membership(db, business_id: int, user_id: int, role: str) -> None:
    exists = (
        db.query(BusinessMembership)
        .filter(
            BusinessMembership.business_id == business_id,
            BusinessMembership.user_id == user_id,
        )
        .first()
    )
    if not exists:
        db.add(BusinessMembership(business_id=business_id, user_id=user_id, role=role))


def get_or_create_branch(
    db, business_id: int, name: str, code: str, address: str
) -> Branch:
    branch = (
        db.query(Branch)
        .filter(Branch.business_id == business_id, Branch.name == name)
        .first()
    )
    if branch:
        return branch
    branch = Branch(
        business_id=business_id,
        name=name,
        branch_code=code,
        address=address,
        is_active=True,
        status="active",
    )
    db.add(branch)
    db.flush()
    return branch


PRODUCTS = [
    # (name, sku, category, base_unit, unit_cost, selling_price)
    (
        "Chicken Gyros",
        "GYR-CHK",
        "Mains",
        "portion",
        Decimal("18000"),
        Decimal("35000"),
    ),
    ("Beef Gyros", "GYR-BEF", "Mains", "portion", Decimal("22000"), Decimal("42000")),
    ("Lamb Gyros", "GYR-LAM", "Mains", "portion", Decimal("28000"), Decimal("52000")),
    ("Falafel Wrap", "WRP-FAL", "Mains", "portion", Decimal("12000"), Decimal("28000")),
    ("Greek Salad", "SAL-GRK", "Sides", "portion", Decimal("8000"), Decimal("20000")),
    ("Pita Bread", "BRD-PIT", "Sides", "piece", Decimal("3000"), Decimal("8000")),
    ("Tzatziki Dip", "DIP-TZA", "Sides", "cup", Decimal("4000"), Decimal("10000")),
    ("French Fries", "SID-FRY", "Sides", "portion", Decimal("6000"), Decimal("15000")),
    ("Iced Tea", "DRI-TEA", "Drinks", "cup", Decimal("2000"), Decimal("8000")),
    ("Soft Drink", "DRI-SOD", "Drinks", "can", Decimal("5000"), Decimal("12000")),
]


def seed_products(db, business: Business, user: User) -> list[Product]:
    products: list[Product] = []
    today = date.today()
    for name, sku, category, base_unit, unit_cost, selling_price in PRODUCTS:
        product = (
            db.query(Product)
            .filter(Product.business_id == business.id, Product.name == name)
            .first()
        )
        if not product:
            product = Product(
                business_id=business.id,
                name=name,
                sku=sku,
                category=category,
                base_unit=base_unit,
                is_active=True,
                status="active",
            )
            db.add(product)
            db.flush()

        cost_exists = (
            db.query(ProductCostHistory)
            .filter(
                ProductCostHistory.business_id == business.id,
                ProductCostHistory.product_id == product.id,
                ProductCostHistory.effective_to.is_(None),
            )
            .first()
        )
        if not cost_exists:
            db.add(
                ProductCostHistory(
                    business_id=business.id,
                    product_id=product.id,
                    effective_from=today - timedelta(days=90),
                    effective_to=None,
                    unit_cost=unit_cost,
                    cost_unit=base_unit,
                    created_by_user_id=user.id,
                )
            )

        price_exists = (
            db.query(ProductPriceHistory)
            .filter(
                ProductPriceHistory.business_id == business.id,
                ProductPriceHistory.product_id == product.id,
                ProductPriceHistory.effective_to.is_(None),
            )
            .first()
        )
        if not price_exists:
            db.add(
                ProductPriceHistory(
                    business_id=business.id,
                    product_id=product.id,
                    effective_from=today - timedelta(days=90),
                    effective_to=None,
                    selling_price=selling_price,
                    price_unit=base_unit,
                    created_by_user_id=user.id,
                )
            )

        products.append(product)
    return products


def seed_sales(
    db,
    business: Business,
    branches: list[Branch],
    products: list[Product],
    user: User,
) -> None:
    today = date.today()
    start = today - timedelta(days=SALES_DAYS)

    existing = (
        db.query(SalesReportSubmission)
        .filter(
            SalesReportSubmission.business_id == business.id,
            SalesReportSubmission.status == "completed",
        )
        .first()
    )
    if existing:
        return

    price_by_product = {
        p.name: price for p, price in zip(products, [r[5] for r in PRODUCTS])
    }

    for branch in branches:
        submission = SalesReportSubmission(
            business_id=business.id,
            submitted_by_user_id=user.id,
            branch_id=branch.id,
            input_method="manual",
            report_period_type="daily",
            coverage_start=start,
            coverage_end=today,
            status="completed",
            total_rows=0,
            accepted_rows=0,
            rejected_rows=0,
        )
        db.add(submission)
        db.flush()

        row_count = 0
        for product in products:
            for offset in range(SALES_DAYS + 1):
                day = start + timedelta(days=offset)
                sold = random.randint(*SALES_PER_PRODUCT_PER_DAY_RANGE)
                prepared = sold + random.randint(0, 8)
                leftover = prepared - sold
                revenue = Decimal(sold) * price_by_product[product.name]
                db.add(
                    SalesReportObservation(
                        business_id=business.id,
                        branch_id=branch.id,
                        product_id=product.id,
                        source_submission_id=submission.id,
                        period_start=day,
                        period_end=day,
                        granularity="daily",
                        prepared_qty=Decimal(prepared),
                        sold_qty=Decimal(sold),
                        leftover_qty=Decimal(leftover),
                        recorded_revenue=revenue,
                        record_status="active",
                        created_by_user_id=user.id,
                    )
                )
                row_count += 1

        submission.total_rows = row_count
        submission.accepted_rows = row_count


def main() -> None:
    random.seed(42)
    db = SessionLocal()
    try:
        business = get_or_create_business(db)

        admin = get_or_create_user(db, "Admin User", "admin@gyros.localhost.com")
        staff = get_or_create_user(db, "Staff User", "staff@gyros.localhost.com")
        ensure_membership(db, business.id, admin.id, "owner")
        ensure_membership(db, business.id, staff.id, "staff")

        main_branch = get_or_create_branch(
            db, business.id, "Main Branch", "MAIN", "Jl. Merdeka No. 1, Jakarta"
        )
        second_branch = get_or_create_branch(
            db, business.id, "Second Branch", "BR-02", "Jl. Sudirman No. 45, Jakarta"
        )

        products = seed_products(db, business, admin)
        seed_sales(db, business, [main_branch, second_branch], products, admin)

        db.commit()
        print("Seed complete:")
        print(f"  business: {business.name} (id={business.id})")
        print(f"  users: {admin.email}, {staff.email} (password: {SEED_PASSWORD})")
        print(f"  branches: {main_branch.name}, {second_branch.name}")
        print(f"  products: {len(products)}")
        print(f"  sales: {SALES_DAYS + 1} days x {len(products)} products x 2 branches")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
