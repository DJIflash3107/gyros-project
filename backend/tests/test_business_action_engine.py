from datetime import date
from decimal import Decimal
import pytest

from app.services.business_action_engine import (
    BusinessActionEngine,
    EngineInput,
    AggregatedObservation,
    AggregatedExpense,
    AggregatedForecast,
)


def test_empty_engine_input():
    engine = BusinessActionEngine()
    inp = EngineInput(business_id=1, business_name="Test Biz")
    results = engine.evaluate(inp)
    assert results == []


def test_rule_inv_001_high_spoilage():
    engine = BusinessActionEngine()
    obs = AggregatedObservation(
        branch_id=10,
        branch_name="Branch A",
        product_id=100,
        product_name="Salad",
        product_category="Food",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 30),
        days_in_period=30,
        total_sold=Decimal("50"),
        total_spoiled=Decimal("30"),  # 30 / (50 + 30) = 37.5% > 30% -> critical
        total_damaged=Decimal("0"),
        total_leftover=Decimal("0"),
        total_revenue=Decimal("1500000"),  # rev per unit = 30,000 -> 30 * 30,000 = 900,000 > 500k -> high impact
        observation_count=20,
    )
    inp = EngineInput(
        business_id=1,
        business_name="Test Biz",
        observations=[obs],
    )
    results = engine.evaluate(inp)
    inv_actions = [r for r in results if r.action_type == "INV-001"]
    assert len(inv_actions) == 1
    action = inv_actions[0]
    assert action.urgency == "critical"
    assert action.expected_impact == "high"
    assert action.evidence_quality == "measured"
    assert action.priority_score >= Decimal("75.00")
    assert action.rule_label == "high_spoilage"
    assert action.title is None
    assert action.rationale is None
    assert action.recommended_steps is None
    assert action.supporting_data["context"]["product_name"] == "Salad"
    assert action.supporting_data["context"]["branch_name"] == "Branch A"


def test_rule_inv_002_excess_leftover():
    engine = BusinessActionEngine()
    obs = AggregatedObservation(
        branch_id=10,
        branch_name="Branch A",
        product_id=101,
        product_name="Croissant",
        product_category="Bakery",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 30),
        days_in_period=30,
        total_sold=Decimal("20"),
        total_spoiled=Decimal("0"),
        total_damaged=Decimal("0"),
        total_leftover=Decimal("50"),  # 50 > 2 * 20 and 50 > 10
        total_revenue=Decimal("400000"),
        observation_count=15,
    )
    inp = EngineInput(
        business_id=1,
        business_name="Test Biz",
        observations=[obs],
    )
    results = engine.evaluate(inp)
    inv_actions = [r for r in results if r.action_type == "INV-002"]
    assert len(inv_actions) == 1
    action = inv_actions[0]
    assert action.urgency == "medium"
    assert action.category == "inventory"
    assert action.rule_label == "excess_leftover"
    assert action.title is None
    assert action.supporting_data["leftover_ratio"] == 2.5


def test_rule_inv_003_high_damage():
    engine = BusinessActionEngine()
    obs = AggregatedObservation(
        branch_id=10,
        branch_name="Branch A",
        product_id=102,
        product_name="Glassware Soda",
        product_category="Beverage",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 30),
        days_in_period=30,
        total_sold=Decimal("80"),
        total_spoiled=Decimal("0"),
        total_damaged=Decimal("15"),  # 15 / 95 = 15.7% > 5%, total_damaged > 10 -> high urgency
        total_leftover=Decimal("0"),
        total_revenue=Decimal("800000"),
        observation_count=20,
    )
    inp = EngineInput(
        business_id=1,
        business_name="Test Biz",
        observations=[obs],
    )
    results = engine.evaluate(inp)
    inv_actions = [r for r in results if r.action_type == "INV-003"]
    assert len(inv_actions) == 1
    action = inv_actions[0]
    assert action.urgency == "high"
    assert action.category == "inventory"
    assert action.rule_label == "high_damage"
    assert action.title is None


def test_rule_sal_001_zero_sales():
    engine = BusinessActionEngine()
    obs = AggregatedObservation(
        branch_id=10,
        branch_name="Branch A",
        product_id=103,
        product_name="Old Sandwich",
        product_category="Food",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 20),
        days_in_period=20,
        total_sold=Decimal("0"),
        total_spoiled=Decimal("0"),
        total_damaged=Decimal("0"),
        total_leftover=Decimal("0"),
        total_revenue=Decimal("0"),
        observation_count=5,
    )
    inp = EngineInput(
        business_id=1,
        business_name="Test Biz",
        observations=[obs],
    )
    results = engine.evaluate(inp)
    sal_actions = [r for r in results if r.action_type == "SAL-001"]
    assert len(sal_actions) == 1
    action = sal_actions[0]
    assert action.urgency == "low"
    assert action.priority_score == Decimal("35.00")
    assert action.category == "sales"
    assert action.rule_label == "zero_sales"
    assert action.title is None


def test_rule_sal_002_top_seller():
    engine = BusinessActionEngine()
    obs = AggregatedObservation(
        branch_id=10,
        branch_name="Branch A",
        product_id=104,
        product_name="Signature Gyros",
        product_category="Food",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 10),
        days_in_period=10,
        total_sold=Decimal("200"),
        total_spoiled=Decimal("1"),
        total_damaged=Decimal("0"),
        total_leftover=Decimal("2"),
        total_revenue=Decimal("10000000"),
        observation_count=10,
    )
    inp = EngineInput(
        business_id=1,
        business_name="Test Biz",
        observations=[obs],
    )
    results = engine.evaluate(inp)
    sal_actions = [r for r in results if r.action_type == "SAL-002"]
    assert len(sal_actions) == 1
    action = sal_actions[0]
    assert action.urgency == "medium"
    assert action.expected_impact == "high"
    assert action.priority_score >= Decimal("65.00")
    assert action.rule_label == "revenue_driver"
    assert action.title is None


def test_rule_fc_001_demand_surge():
    engine = BusinessActionEngine()
    fc = AggregatedForecast(
        forecast_run_id=5,
        branch_id=10,
        branch_name="Branch A",
        product_id=105,
        product_name="Lemonade",
        is_reliable=True,
        mae=Decimal("1.5"),
        wape=Decimal("0.12"),
        forecast_bias=Decimal("0.2"),
        horizon_days=7,
        predicted_total_qty=Decimal("150"),
        historical_recent_qty=Decimal("100"),  # +50% surge
    )
    inp = EngineInput(
        business_id=1,
        business_name="Test Biz",
        forecasts=[fc],
    )
    results = engine.evaluate(inp)
    fc_actions = [r for r in results if r.action_type == "FC-001"]
    assert len(fc_actions) == 1
    action = fc_actions[0]
    assert action.urgency == "high"
    assert action.expected_impact == "high"
    assert action.evidence_quality == "estimated"
    assert action.priority_score >= Decimal("78.00")
    assert action.rule_label == "demand_surge"
    assert action.title is None


def test_rule_fc_002_demand_drop():
    engine = BusinessActionEngine()
    fc = AggregatedForecast(
        forecast_run_id=6,
        branch_id=10,
        branch_name="Branch A",
        product_id=106,
        product_name="Soup",
        is_reliable=True,
        mae=Decimal("1.0"),
        wape=Decimal("0.10"),
        forecast_bias=Decimal("0.0"),
        horizon_days=7,
        predicted_total_qty=Decimal("40"),
        historical_recent_qty=Decimal("100"),  # -60% drop
    )
    inp = EngineInput(
        business_id=1,
        business_name="Test Biz",
        forecasts=[fc],
    )
    results = engine.evaluate(inp)
    fc_actions = [r for r in results if r.action_type == "FC-002"]
    assert len(fc_actions) == 1
    action = fc_actions[0]
    assert action.urgency == "medium"
    assert action.expected_impact == "medium"
    assert action.evidence_quality == "estimated"
    assert action.rule_label == "demand_drop"
    assert action.title is None


def test_rule_fc_003_unreliable_forecast():
    engine = BusinessActionEngine()
    fc = AggregatedForecast(
        forecast_run_id=7,
        branch_id=10,
        branch_name="Branch A",
        product_id=107,
        product_name="New Cake",
        is_reliable=False,
        mae=Decimal("5.0"),
        wape=Decimal("0.55"),
        forecast_bias=Decimal("2.0"),
        horizon_days=7,
        predicted_total_qty=Decimal("30"),
        historical_recent_qty=Decimal("25"),
    )
    inp = EngineInput(
        business_id=1,
        business_name="Test Biz",
        forecasts=[fc],
    )
    results = engine.evaluate(inp)
    fc_actions = [r for r in results if r.action_type == "FC-003"]
    assert len(fc_actions) == 1
    action = fc_actions[0]
    assert action.urgency == "low"
    assert action.priority_score == Decimal("40.00")
    assert action.rule_label == "unreliable_forecast"
    assert action.title is None


def test_rule_exp_001_surge_and_002_concentration():
    engine = BusinessActionEngine()
    exp1 = AggregatedExpense(
        category="Ingredients",
        branch_id=10,
        branch_name="Branch A",
        total_amount=Decimal("3000000"),
        expense_count=12,
        period_amount_prior=Decimal("1800000"),  # +66.7% growth >= 50% -> critical/high
    )
    exp2 = AggregatedExpense(
        category="Utilities",
        branch_id=10,
        branch_name="Branch A",
        total_amount=Decimal("500000"),
        expense_count=2,
        period_amount_prior=Decimal("500000"),
    )
    # Total biz expenses = 3.5M. Ingredients = 3M / 3.5M = 85.7% >= 40% -> triggers EXP-002 as well
    inp = EngineInput(
        business_id=1,
        business_name="Test Biz",
        expenses=[exp1, exp2],
    )
    results = engine.evaluate(inp)
    exp_actions = [r for r in results if r.category == "expenses"]
    types = {r.action_type for r in exp_actions}
    labels = {r.rule_label for r in exp_actions}
    assert "EXP-001" in types
    assert "EXP-002" in types
    assert "expense_surge" in labels
    assert "expense_concentration" in labels
    for r in exp_actions:
        assert r.title is None


def test_cross_validation_modifier():
    engine = BusinessActionEngine()
    obs = AggregatedObservation(
        branch_id=10,
        branch_name="Branch A",
        product_id=200,
        product_name="Beef Bowl",
        product_category="Food",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 30),
        days_in_period=30,
        total_sold=Decimal("50"),
        total_spoiled=Decimal("20"),  # INV-001
        total_damaged=Decimal("0"),
        total_leftover=Decimal("0"),
        total_revenue=Decimal("1000000"),
        observation_count=20,
    )
    fc = AggregatedForecast(
        forecast_run_id=10,
        branch_id=10,
        branch_name="Branch A",
        product_id=200,  # Same product!
        product_name="Beef Bowl",
        is_reliable=True,
        mae=Decimal("1.0"),
        wape=Decimal("0.10"),
        forecast_bias=Decimal("0.0"),
        horizon_days=7,
        predicted_total_qty=Decimal("150"),
        historical_recent_qty=Decimal("100"),  # FC-001
    )
    inp = EngineInput(
        business_id=1,
        business_name="Test Biz",
        observations=[obs],
        forecasts=[fc],
    )
    results = engine.evaluate(inp)
    inv_actions = [r for r in results if r.category == "inventory"]
    fc_actions = [r for r in results if r.category == "demand_forecasting"]
    assert len(inv_actions) > 0
    assert len(fc_actions) > 0
    for r in inv_actions + fc_actions:
        assert r.evidence_quality == "mixed"
        assert r.priority_score > Decimal("75.00")
