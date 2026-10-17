from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict, Any


@dataclass
class AggregatedObservation:
    branch_id: int
    branch_name: str
    product_id: int
    product_name: str
    product_category: Optional[str]
    period_start: date
    period_end: date
    days_in_period: int
    total_sold: Decimal
    total_spoiled: Decimal
    total_damaged: Decimal
    total_leftover: Decimal
    total_revenue: Decimal
    observation_count: int
    spoilage_rate: float = 0.0
    daily_sales_velocity: float = 0.0
    revenue_per_unit: float = 0.0

    def __post_init__(self):
        # Calculate derived metrics
        disposition_sum = (
            self.total_sold + self.total_spoiled + self.total_damaged + self.total_leftover
        )
        if disposition_sum > 0:
            self.spoilage_rate = float(self.total_spoiled / disposition_sum)
        else:
            self.spoilage_rate = 0.0

        if self.days_in_period > 0:
            self.daily_sales_velocity = float(self.total_sold / Decimal(self.days_in_period))
        else:
            self.daily_sales_velocity = 0.0

        if self.total_sold > 0:
            self.revenue_per_unit = float(self.total_revenue / self.total_sold)
        else:
            self.revenue_per_unit = 0.0


@dataclass
class AggregatedExpense:
    category: str
    branch_id: Optional[int]
    branch_name: Optional[str]
    total_amount: Decimal
    expense_count: int
    period_amount_prior: Optional[Decimal] = None
    growth_rate: Optional[float] = None

    def __post_init__(self):
        if self.period_amount_prior is not None and self.period_amount_prior > 0:
            diff = self.total_amount - self.period_amount_prior
            self.growth_rate = float(diff / self.period_amount_prior)


@dataclass
class AggregatedForecast:
    forecast_run_id: int
    branch_id: int
    branch_name: str
    product_id: int
    product_name: str
    is_reliable: bool
    mae: Optional[Decimal]
    wape: Optional[Decimal]
    forecast_bias: Optional[Decimal]
    horizon_days: int
    predicted_total_qty: Decimal
    historical_recent_qty: Decimal
    projected_change_pct: float = 0.0

    def __post_init__(self):
        if self.historical_recent_qty > 0:
            diff = self.predicted_total_qty - self.historical_recent_qty
            self.projected_change_pct = float(diff / self.historical_recent_qty)
        else:
            self.projected_change_pct = 0.0


@dataclass
class EngineInput:
    business_id: int
    business_name: str
    observations: List[AggregatedObservation] = field(default_factory=list)
    expenses: List[AggregatedExpense] = field(default_factory=list)
    forecasts: List[AggregatedForecast] = field(default_factory=list)
    lookback_days: int = 30
    active_product_count: int = 0
    active_branch_count: int = 0


@dataclass
class ActionCandidate:
    # === DETERMINISTIC (set by engine) ===
    action_type: str
    category: str
    rule_label: str
    urgency: str
    expected_impact: str
    priority_score: Decimal
    evidence_quality: str
    supporting_data: Dict[str, Any]

    # === AI-GENERATED (set by ActionNarrativeGenerator) ===
    title: Optional[str] = None
    rationale: Optional[str] = None
    recommended_steps: Optional[List[str]] = None
    risks: Optional[List[str]] = None
    success_metrics: Optional[List[str]] = None
    limitations: Optional[str] = None

    # === ENTITY REFERENCES ===
    branch_id: Optional[int] = None
    product_id: Optional[int] = None
    forecast_run_id: Optional[int] = None
    ai_generated: bool = True


class BusinessActionEngine:
    """
    Deterministic rule-based recommendation engine.
    Pure computation, no AI, no external network calls.
    Evaluates business data against established rules and returns ranked ActionCandidates.
    """

    URGENCY_RANKS = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    IMPACT_RANKS = {"high": 3, "medium": 2, "low": 1}

    def evaluate(self, input_data: EngineInput) -> List[ActionCandidate]:
        candidates: List[ActionCandidate] = []

        # 1. Evaluate Observation Rules (INV-001, INV-002, INV-003, SAL-001, SAL-002)
        candidates.extend(self._evaluate_observations(input_data))

        # 2. Evaluate Forecasting Rules (FC-001, FC-002, FC-003)
        candidates.extend(self._evaluate_forecasts(input_data))

        # 3. Evaluate Expense Rules (EXP-001, EXP-002)
        candidates.extend(self._evaluate_expenses(input_data))

        if not candidates:
            return []

        # 4. Apply Deterministic Modifiers
        modified_candidates = self._apply_modifiers(candidates)

        # 5. Sort Deterministically: priority_score desc, urgency desc, expected_impact desc, action_type asc, rule_label asc
        modified_candidates.sort(
            key=lambda c: (
                c.priority_score,
                self.URGENCY_RANKS.get(c.urgency, 0),
                self.IMPACT_RANKS.get(c.expected_impact, 0),
                c.action_type,
                c.rule_label,
            ),
            reverse=True,
        )

        return modified_candidates

    def _evaluate_observations(self, input_data: EngineInput) -> List[ActionCandidate]:
        candidates: List[ActionCandidate] = []
        obs_list = input_data.observations

        # Find top 20% revenue threshold for SAL-002 if applicable
        revenues = sorted([float(o.total_revenue) for o in obs_list if o.total_revenue > 0])
        top_20_rev_threshold = 0.0
        if revenues:
            cutoff_idx = int(len(revenues) * 0.8)
            top_20_rev_threshold = revenues[min(cutoff_idx, len(revenues) - 1)]

        for obs in obs_list:
            # Rule INV-001: High Spoilage Alert
            if obs.spoilage_rate > 0.15 and obs.total_spoiled > 5:
                urgency = "critical" if obs.spoilage_rate > 0.30 else "high"
                est_loss = float(obs.total_spoiled) * obs.revenue_per_unit
                expected_impact = "high" if est_loss > 500000 else "medium"
                score = Decimal(str(round(75.0 + min(20.0, obs.spoilage_rate * 50.0), 2)))

                candidates.append(
                    ActionCandidate(
                        action_type="INV-001",
                        category="inventory",
                        rule_label="high_spoilage",
                        urgency=urgency,
                        expected_impact=expected_impact,
                        priority_score=score,
                        evidence_quality="measured",
                        supporting_data={
                            "spoilage_rate": round(obs.spoilage_rate, 4),
                            "total_spoiled": float(obs.total_spoiled),
                            "total_sold": float(obs.total_sold),
                            "estimated_financial_loss": round(est_loss, 2),
                            "observation_count": obs.observation_count,
                            "context": {
                                "product_name": obs.product_name,
                                "branch_name": obs.branch_name,
                                "days_in_period": obs.days_in_period,
                                "business_name": input_data.business_name,
                            },
                        },
                        branch_id=obs.branch_id,
                        product_id=obs.product_id,
                    )
                )

            # Rule INV-002: Excess Leftover Stock
            if obs.total_leftover > 2 * obs.total_sold and obs.total_sold > 0 and obs.total_leftover > 10:
                leftover_ratio = float(obs.total_leftover / obs.total_sold)
                score = Decimal(str(round(55.0 + min(15.0, leftover_ratio * 3.0), 2)))

                candidates.append(
                    ActionCandidate(
                        action_type="INV-002",
                        category="inventory",
                        rule_label="excess_leftover",
                        urgency="medium",
                        expected_impact="medium",
                        priority_score=score,
                        evidence_quality="measured",
                        supporting_data={
                            "total_leftover": float(obs.total_leftover),
                            "total_sold": float(obs.total_sold),
                            "leftover_ratio": round(leftover_ratio, 2),
                            "observation_count": obs.observation_count,
                            "context": {
                                "product_name": obs.product_name,
                                "branch_name": obs.branch_name,
                                "days_in_period": obs.days_in_period,
                                "business_name": input_data.business_name,
                            },
                        },
                        branch_id=obs.branch_id,
                        product_id=obs.product_id,
                    )
                )

            # Rule INV-003: High Damage Rate
            disposition_damage = obs.total_sold + obs.total_damaged
            if (
                obs.total_damaged > 3
                and disposition_damage > 0
                and float(obs.total_damaged / disposition_damage) > 0.05
            ):
                damage_rate = float(obs.total_damaged / disposition_damage)
                urgency = "high" if obs.total_damaged > 10 else "medium"
                score = Decimal(str(round(60.0 + min(20.0, float(obs.total_damaged) * 2.0), 2)))

                candidates.append(
                    ActionCandidate(
                        action_type="INV-003",
                        category="inventory",
                        rule_label="high_damage",
                        urgency=urgency,
                        expected_impact="medium",
                        priority_score=score,
                        evidence_quality="measured",
                        supporting_data={
                            "total_damaged": float(obs.total_damaged),
                            "total_sold": float(obs.total_sold),
                            "damage_rate": round(damage_rate, 4),
                            "observation_count": obs.observation_count,
                            "context": {
                                "product_name": obs.product_name,
                                "branch_name": obs.branch_name,
                                "days_in_period": obs.days_in_period,
                                "business_name": input_data.business_name,
                            },
                        },
                        branch_id=obs.branch_id,
                        product_id=obs.product_id,
                    )
                )

            # Rule SAL-001: Zero Sales / Dead Product
            if obs.days_in_period >= 14 and obs.total_sold == 0 and obs.observation_count >= 3:
                candidates.append(
                    ActionCandidate(
                        action_type="SAL-001",
                        category="sales",
                        rule_label="zero_sales",
                        urgency="low",
                        expected_impact="low",
                        priority_score=Decimal("35.00"),
                        evidence_quality="measured",
                        supporting_data={
                            "days_in_period": obs.days_in_period,
                            "observation_count": obs.observation_count,
                            "total_sold": 0.0,
                            "context": {
                                "product_name": obs.product_name,
                                "branch_name": obs.branch_name,
                                "days_in_period": obs.days_in_period,
                                "business_name": input_data.business_name,
                            },
                        },
                        branch_id=obs.branch_id,
                        product_id=obs.product_id,
                    )
                )

            # Rule SAL-002: High-Volume Revenue Driver
            is_top_rev = float(obs.total_revenue) >= top_20_rev_threshold and top_20_rev_threshold > 0
            is_high_velocity = obs.daily_sales_velocity >= 10.0 and obs.total_sold >= 50
            if obs.total_sold > 0 and (is_top_rev or is_high_velocity):
                score = Decimal(str(round(65.0 + min(20.0, obs.daily_sales_velocity * 2.0), 2)))

                candidates.append(
                    ActionCandidate(
                        action_type="SAL-002",
                        category="sales",
                        rule_label="revenue_driver",
                        urgency="medium",
                        expected_impact="high",
                        priority_score=score,
                        evidence_quality="measured",
                        supporting_data={
                            "total_sold": float(obs.total_sold),
                            "daily_sales_velocity": round(obs.daily_sales_velocity, 2),
                            "total_revenue": float(obs.total_revenue),
                            "revenue_per_unit": round(obs.revenue_per_unit, 2),
                            "context": {
                                "product_name": obs.product_name,
                                "branch_name": obs.branch_name,
                                "days_in_period": obs.days_in_period,
                                "business_name": input_data.business_name,
                            },
                        },
                        branch_id=obs.branch_id,
                        product_id=obs.product_id,
                    )
                )

        return candidates

    def _evaluate_forecasts(self, input_data: EngineInput) -> List[ActionCandidate]:
        candidates: List[ActionCandidate] = []

        for fc in input_data.forecasts:
            # Rule FC-001: Impending Demand Surge
            if fc.is_reliable and fc.projected_change_pct >= 0.25 and fc.predicted_total_qty >= 20:
                score = Decimal(str(round(78.0 + min(15.0, fc.projected_change_pct * 30.0), 2)))

                candidates.append(
                    ActionCandidate(
                        action_type="FC-001",
                        category="demand_forecasting",
                        rule_label="demand_surge",
                        urgency="high",
                        expected_impact="high",
                        priority_score=score,
                        evidence_quality="estimated",
                        supporting_data={
                            "forecast_run_id": fc.forecast_run_id,
                            "horizon_days": fc.horizon_days,
                            "predicted_total_qty": float(fc.predicted_total_qty),
                            "historical_recent_qty": float(fc.historical_recent_qty),
                            "projected_change_pct": round(fc.projected_change_pct, 4),
                            "mae": float(fc.mae) if fc.mae is not None else None,
                            "wape": float(fc.wape) if fc.wape is not None else None,
                            "context": {
                                "product_name": fc.product_name,
                                "branch_name": fc.branch_name,
                                "horizon_days": fc.horizon_days,
                                "business_name": input_data.business_name,
                            },
                        },
                        branch_id=fc.branch_id,
                        product_id=fc.product_id,
                        forecast_run_id=fc.forecast_run_id,
                    )
                )

            # Rule FC-002: Projected Demand Drop
            if fc.is_reliable and fc.projected_change_pct <= -0.25 and fc.historical_recent_qty >= 20:
                score = Decimal(str(round(62.0 + min(15.0, abs(fc.projected_change_pct) * 25.0), 2)))

                candidates.append(
                    ActionCandidate(
                        action_type="FC-002",
                        category="demand_forecasting",
                        rule_label="demand_drop",
                        urgency="medium",
                        expected_impact="medium",
                        priority_score=score,
                        evidence_quality="estimated",
                        supporting_data={
                            "forecast_run_id": fc.forecast_run_id,
                            "horizon_days": fc.horizon_days,
                            "predicted_total_qty": float(fc.predicted_total_qty),
                            "historical_recent_qty": float(fc.historical_recent_qty),
                            "projected_change_pct": round(fc.projected_change_pct, 4),
                            "context": {
                                "product_name": fc.product_name,
                                "branch_name": fc.branch_name,
                                "horizon_days": fc.horizon_days,
                                "business_name": input_data.business_name,
                            },
                        },
                        branch_id=fc.branch_id,
                        product_id=fc.product_id,
                        forecast_run_id=fc.forecast_run_id,
                    )
                )

            # Rule FC-003: Unreliable Forecast / High Error
            wape_val = float(fc.wape) if fc.wape is not None else None
            if not fc.is_reliable or (wape_val is not None and wape_val > 0.40):
                candidates.append(
                    ActionCandidate(
                        action_type="FC-003",
                        category="demand_forecasting",
                        rule_label="unreliable_forecast",
                        urgency="low",
                        expected_impact="low",
                        priority_score=Decimal("40.00"),
                        evidence_quality="estimated",
                        supporting_data={
                            "forecast_run_id": fc.forecast_run_id,
                            "is_reliable": fc.is_reliable,
                            "wape": round(wape_val, 4) if wape_val is not None else None,
                            "mae": float(fc.mae) if fc.mae is not None else None,
                            "context": {
                                "product_name": fc.product_name,
                                "branch_name": fc.branch_name,
                                "horizon_days": fc.horizon_days,
                                "business_name": input_data.business_name,
                            },
                        },
                        branch_id=fc.branch_id,
                        product_id=fc.product_id,
                        forecast_run_id=fc.forecast_run_id,
                    )
                )

        return candidates

    def _evaluate_expenses(self, input_data: EngineInput) -> List[ActionCandidate]:
        candidates: List[ActionCandidate] = []
        total_biz_expenses = sum([exp.total_amount for exp in input_data.expenses], Decimal(0))

        for exp in input_data.expenses:
            # Rule EXP-001: Expense Surge in Category
            if (
                exp.growth_rate is not None
                and exp.growth_rate >= 0.30
                and exp.total_amount >= Decimal("500000")
            ):
                urgency = "high" if exp.growth_rate >= 0.50 else "medium"
                expected_impact = "high" if exp.total_amount >= Decimal("2000000") else "medium"
                score = Decimal(str(round(70.0 + min(20.0, exp.growth_rate * 30.0), 2)))

                candidates.append(
                    ActionCandidate(
                        action_type="EXP-001",
                        category="expenses",
                        rule_label="expense_surge",
                        urgency=urgency,
                        expected_impact=expected_impact,
                        priority_score=score,
                        evidence_quality="measured",
                        supporting_data={
                            "category": exp.category,
                            "branch_id": exp.branch_id,
                            "branch_name": exp.branch_name,
                            "total_amount": float(exp.total_amount),
                            "prior_amount": float(exp.period_amount_prior),
                            "growth_rate": round(exp.growth_rate, 4),
                            "expense_count": exp.expense_count,
                            "context": {
                                "category_name": exp.category,
                                "branch_name": exp.branch_name,
                                "business_name": input_data.business_name,
                            },
                        },
                        branch_id=exp.branch_id,
                    )
                )

            # Rule EXP-002: High Expense Concentration
            if (
                total_biz_expenses >= Decimal("1000000")
                and exp.total_amount > 0
                and float(exp.total_amount / total_biz_expenses) >= 0.40
            ):
                concentration_ratio = float(exp.total_amount / total_biz_expenses)
                score = Decimal(str(round(60.0 + min(20.0, concentration_ratio * 30.0), 2)))

                candidates.append(
                    ActionCandidate(
                        action_type="EXP-002",
                        category="expenses",
                        rule_label="expense_concentration",
                        urgency="medium",
                        expected_impact="high",
                        priority_score=score,
                        evidence_quality="measured",
                        supporting_data={
                            "category": exp.category,
                            "total_amount": float(exp.total_amount),
                            "total_business_expenses": float(total_biz_expenses),
                            "concentration_pct": round(concentration_ratio, 4),
                            "context": {
                                "category_name": exp.category,
                                "branch_name": exp.branch_name if exp.branch_name else None,
                                "business_name": input_data.business_name,
                            },
                        },
                        branch_id=exp.branch_id,
                    )
                )

        return candidates

    def _apply_modifiers(self, candidates: List[ActionCandidate]) -> List[ActionCandidate]:
        # Identify cross-validation: products with BOTH inventory action and forecasting action
        products_with_inventory = {
            c.product_id for c in candidates if c.product_id and c.category == "inventory"
        }
        products_with_forecast = {
            c.product_id for c in candidates if c.product_id and c.category == "demand_forecasting"
        }
        cross_validated_products = products_with_inventory.intersection(products_with_forecast)

        # Count critical/high actions per branch
        branch_high_actions: Dict[int, int] = {}
        for c in candidates:
            if c.branch_id and c.urgency in ("critical", "high"):
                branch_high_actions[c.branch_id] = branch_high_actions.get(c.branch_id, 0) + 1

        systemic_branches = {b_id for b_id, count in branch_high_actions.items() if count > 3}

        for c in candidates:
            bonus = Decimal("0.00")

            # Cross-validation modifier: +5 points, evidence becomes "mixed"
            if c.product_id in cross_validated_products and c.category in (
                "inventory",
                "demand_forecasting",
            ):
                bonus += Decimal("5.00")
                c.evidence_quality = "mixed"

            # Branch impact modifier: +3 points if systemic issues at branch
            if c.branch_id in systemic_branches:
                bonus += Decimal("3.00")

            new_score = c.priority_score + bonus
            # Clamp between 10.00 and 99.00
            if new_score < Decimal("10.00"):
                new_score = Decimal("10.00")
            elif new_score > Decimal("99.00"):
                new_score = Decimal("99.00")

            c.priority_score = Decimal(str(round(new_score, 2)))

        return candidates
