import pytest
from decimal import Decimal

from app.services.promotion_engine import (
    PromotionEngine,
    ItemInputData,
    DEFAULT_MIN_MARGIN_PCT,
)


def test_percentage_discount_calculation():
    original = Decimal("100.00")
    discounted = PromotionEngine.calculate_discount_price(original, "percentage", Decimal("20.00"))
    assert discounted == Decimal("80.00")


def test_fixed_discount_calculation():
    original = Decimal("100.00")
    discounted = PromotionEngine.calculate_discount_price(original, "fixed_amount", Decimal("25.00"))
    assert discounted == Decimal("75.00")


def test_bundle_price_calculation():
    original = Decimal("100.00")
    discounted = PromotionEngine.calculate_discount_price(original, "bundle_price", Decimal("60.00"))
    assert discounted == Decimal("60.00")


def test_fixed_discount_exceeds_price_clamps_to_zero():
    original = Decimal("50.00")
    discounted = PromotionEngine.calculate_discount_price(original, "fixed_amount", Decimal("60.00"))
    assert discounted == Decimal("0.00")


def test_margin_calculation_with_cost():
    discounted = Decimal("80.00")
    cost = Decimal("50.00")
    margin_unit, margin_pct = PromotionEngine.calculate_margin(discounted, cost)
    assert margin_unit == Decimal("30.00")
    assert margin_pct == Decimal("37.50")


def test_margin_below_minimum_generates_warning():
    item = ItemInputData(
        product_id=1,
        product_name="Product A",
        discount_type="percentage",
        discount_value=Decimal("50.00"),
        original_price=Decimal("100.00"),
        unit_cost=Decimal("45.00"),  # discounted price = 50.00, margin = 5.00 (10%)
        expected_qty=10,
    )
    evaluation = PromotionEngine.evaluate_item(item, min_margin_pct=Decimal("15.00"))
    assert evaluation.margin_pct == Decimal("10.00")
    assert any("below the minimum threshold" in w for w in evaluation.warnings)


def test_negative_margin_generates_high_warning():
    item = ItemInputData(
        product_id=1,
        product_name="Product B",
        discount_type="percentage",
        discount_value=Decimal("40.00"),
        original_price=Decimal("100.00"),
        unit_cost=Decimal("70.00"),  # discounted price = 60.00, cost = 70.00 -> margin = -10.00
        expected_qty=5,
    )
    evaluation = PromotionEngine.evaluate_item(item)
    assert evaluation.margin_per_unit == Decimal("-10.00")
    assert any("sold below cost" in w for w in evaluation.warnings)


def test_missing_cost_marks_unvalidated():
    item = ItemInputData(
        product_id=1,
        product_name="Product C",
        discount_type="percentage",
        discount_value=Decimal("20.00"),
        original_price=Decimal("100.00"),
        unit_cost=None,
        expected_qty=10,
    )
    plan_eval = PromotionEngine.evaluate_plan([item])
    assert plan_eval.is_financially_validated is False
    assert plan_eval.items[0].cost_data_available is False
    assert any("missing cost data" in w for w in plan_eval.warnings)


def test_missing_price_generates_warning():
    item = ItemInputData(
        product_id=1,
        product_name="Product D",
        discount_type="percentage",
        discount_value=Decimal("20.00"),
        original_price=None,
        unit_cost=Decimal("30.00"),
        expected_qty=10,
    )
    plan_eval = PromotionEngine.evaluate_plan([item])
    assert plan_eval.is_financially_validated is False
    assert plan_eval.items[0].price_data_available is False
    assert any("Price for product" in m for m in plan_eval.missing_data)


def test_contribution_calculation():
    margin = Decimal("25.00")
    qty = 200
    contrib = PromotionEngine.calculate_contribution(margin, qty)
    assert contrib == Decimal("5000.00")


def test_invalid_discount_over_100pct():
    with pytest.raises(ValueError, match="cannot exceed 100%"):
        PromotionEngine.calculate_discount_price(Decimal("100.00"), "percentage", Decimal("105.00"))


def test_invalid_negative_discount():
    with pytest.raises(ValueError, match="cannot be negative"):
        PromotionEngine.calculate_discount_price(Decimal("100.00"), "percentage", Decimal("-10.00"))


def test_weighted_avg_margin():
    items = [
        ItemInputData(
            product_id=1,
            product_name="Prod 1",
            discount_type="percentage",
            discount_value=Decimal("10.00"),  # orig 100 -> disc 90, cost 50, margin 40
            original_price=Decimal("100.00"),
            unit_cost=Decimal("50.00"),
            expected_qty=100,  # disc rev: 9000, cost: 5000, margin: 4000
        ),
        ItemInputData(
            product_id=2,
            product_name="Prod 2",
            discount_type="percentage",
            discount_value=Decimal("20.00"),  # orig 200 -> disc 160, cost 120, margin 40
            original_price=Decimal("200.00"),
            unit_cost=Decimal("120.00"),
            expected_qty=50,  # disc rev: 8000, cost: 6000, margin: 2000
        ),
    ]
    # Total disc rev = 9000 + 8000 = 17000
    # Total cost = 5000 + 6000 = 11000
    # Total margin = 6000
    # avg margin pct = (6000 / 17000) * 100 = 35.29%
    plan_eval = PromotionEngine.evaluate_plan(items)
    assert plan_eval.total_original_revenue == Decimal("20000.00")
    assert plan_eval.total_discounted_revenue == Decimal("17000.00")
    assert plan_eval.total_estimated_cost == Decimal("11000.00")
    assert plan_eval.total_estimated_margin == Decimal("6000.00")
    assert plan_eval.avg_margin_pct == Decimal("35.29")
    assert plan_eval.is_financially_validated is True


def test_all_items_have_cost_data_validated():
    items = [
        ItemInputData(
            product_id=1,
            product_name="Prod 1",
            discount_type="percentage",
            discount_value=Decimal("15.00"),
            original_price=Decimal("100.00"),
            unit_cost=Decimal("60.00"),
            expected_qty=20,
        )
    ]
    plan_eval = PromotionEngine.evaluate_plan(items)
    assert plan_eval.is_financially_validated is True
    assert len(plan_eval.warnings) == 0


def test_partial_cost_data_not_validated():
    items = [
        ItemInputData(
            product_id=1,
            product_name="Prod 1",
            discount_type="percentage",
            discount_value=Decimal("15.00"),
            original_price=Decimal("100.00"),
            unit_cost=Decimal("60.00"),
            expected_qty=20,
        ),
        ItemInputData(
            product_id=2,
            product_name="Prod 2",
            discount_type="percentage",
            discount_value=Decimal("15.00"),
            original_price=Decimal("100.00"),
            unit_cost=None,
            expected_qty=20,
        ),
    ]
    plan_eval = PromotionEngine.evaluate_plan(items)
    assert plan_eval.is_financially_validated is False
    assert len(plan_eval.missing_data) >= 1
