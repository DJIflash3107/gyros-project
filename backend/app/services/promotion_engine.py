from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any


DEFAULT_MIN_MARGIN_PCT = Decimal("15.00")
CENTS = Decimal("0.01")
PERCENT_PRECISION = Decimal("0.01")


def quantize_currency(value: Optional[Decimal]) -> Optional[Decimal]:
    """Round monetary Decimal to 2 decimal places using ROUND_HALF_UP."""
    if value is None:
        return None
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def quantize_pct(value: Optional[Decimal]) -> Optional[Decimal]:
    """Round percentage Decimal to 2 decimal places using ROUND_HALF_UP."""
    if value is None:
        return None
    return value.quantize(PERCENT_PRECISION, rounding=ROUND_HALF_UP)


@dataclass
class ItemInputData:
    product_id: int
    product_name: str
    discount_type: str
    discount_value: Decimal
    original_price: Optional[Decimal] = None
    unit_cost: Optional[Decimal] = None
    expected_qty: Optional[int] = None
    notes: Optional[str] = None


@dataclass
class ItemEvaluation:
    product_id: int
    product_name: str
    discount_type: str
    discount_value: Decimal
    original_price: Optional[Decimal]
    discounted_price: Optional[Decimal]
    unit_cost: Optional[Decimal]
    margin_per_unit: Optional[Decimal]
    margin_pct: Optional[Decimal]
    expected_qty: Optional[int]
    estimated_contribution: Optional[Decimal]
    cost_data_available: bool
    price_data_available: bool
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "discount_type": self.discount_type,
            "discount_value": str(self.discount_value) if self.discount_value is not None else None,
            "original_price": str(self.original_price) if self.original_price is not None else None,
            "discounted_price": str(self.discounted_price) if self.discounted_price is not None else None,
            "unit_cost": str(self.unit_cost) if self.unit_cost is not None else None,
            "margin_per_unit": str(self.margin_per_unit) if self.margin_per_unit is not None else None,
            "margin_pct": str(self.margin_pct) if self.margin_pct is not None else None,
            "expected_qty": self.expected_qty,
            "estimated_contribution": str(self.estimated_contribution) if self.estimated_contribution is not None else None,
            "cost_data_available": self.cost_data_available,
            "price_data_available": self.price_data_available,
            "warnings": self.warnings,
        }



@dataclass
class PlanEvaluation:
    items: List[ItemEvaluation]
    total_original_revenue: Optional[Decimal]
    total_discounted_revenue: Optional[Decimal]
    total_estimated_cost: Optional[Decimal]
    total_estimated_margin: Optional[Decimal]
    avg_margin_pct: Optional[Decimal]
    is_financially_validated: bool
    min_margin_pct: Optional[Decimal]
    warnings: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    missing_data: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)


class PromotionEngine:
    """
    Pure deterministic calculation engine for promotional offers.
    Never calls external services or LLM arithmetic.
    """

    @staticmethod
    def calculate_discount_price(
        original_price: Decimal,
        discount_type: str,
        discount_value: Decimal,
    ) -> Decimal:
        """
        Calculate discounted unit price.
        - percentage: original_price * (1 - discount_value / 100)
        - fixed_amount: original_price - discount_value
        - bundle_price: discount_value
        """
        if discount_value < Decimal("0"):
            raise ValueError(f"Discount value cannot be negative: {discount_value}")

        if discount_type == "percentage":
            if discount_value > Decimal("100.0"):
                raise ValueError(f"Percentage discount cannot exceed 100%: {discount_value}")
            discounted = original_price * (Decimal("1.0") - (discount_value / Decimal("100.0")))
        elif discount_type == "fixed_amount":
            discounted = original_price - discount_value
            if discounted < Decimal("0"):
                discounted = Decimal("0.00")
        elif discount_type == "bundle_price":
            discounted = discount_value
        else:
            raise ValueError(f"Unsupported discount type: {discount_type}")

        return quantize_currency(discounted)

    @staticmethod
    def calculate_margin(
        discounted_price: Decimal,
        unit_cost: Decimal,
    ) -> tuple[Decimal, Optional[Decimal]]:
        """
        Calculate unit margin and margin percentage.
        margin = discounted_price - unit_cost
        margin_pct = (margin / discounted_price) * 100 (if discounted_price > 0)
        """
        margin_per_unit = quantize_currency(discounted_price - unit_cost)
        if discounted_price > Decimal("0"):
            margin_pct = (margin_per_unit / discounted_price) * Decimal("100.0")
            margin_pct = quantize_pct(margin_pct)
        else:
            margin_pct = Decimal("0.00") if margin_per_unit >= Decimal("0") else Decimal("-100.00")
        return margin_per_unit, margin_pct

    @staticmethod
    def calculate_contribution(
        margin_per_unit: Decimal,
        expected_qty: int,
    ) -> Decimal:
        """Calculate total estimated contribution: margin_per_unit * expected_qty."""
        if expected_qty < 0:
            raise ValueError(f"Expected quantity cannot be negative: {expected_qty}")
        return quantize_currency(margin_per_unit * Decimal(expected_qty))

    @classmethod
    def evaluate_item(
        cls,
        item: ItemInputData,
        min_margin_pct: Decimal = DEFAULT_MIN_MARGIN_PCT,
    ) -> ItemEvaluation:
        """
        Evaluate a single promotion item: calculate prices, margins, contributions, and warnings.
        """
        warnings: List[str] = []
        cost_available = item.unit_cost is not None
        price_available = item.original_price is not None

        discounted_price: Optional[Decimal] = None
        margin_per_unit: Optional[Decimal] = None
        margin_pct: Optional[Decimal] = None
        estimated_contribution: Optional[Decimal] = None

        if not price_available:
            warnings.append(
                f"Original price not available for product '{item.product_name}' (ID: {item.product_id})"
            )
        else:
            try:
                discounted_price = cls.calculate_discount_price(
                    item.original_price, item.discount_type, item.discount_value
                )
            except ValueError as e:
                warnings.append(str(e))

        if price_available and discounted_price is not None:
            if not cost_available:
                warnings.append(
                    f"Cost data not available for '{item.product_name}'; margin cannot be validated"
                )
            else:
                margin_per_unit, margin_pct = cls.calculate_margin(
                    discounted_price, item.unit_cost
                )

                if margin_per_unit < Decimal("0"):
                    warnings.append(
                        f"High risk: Product '{item.product_name}' is being sold below cost "
                        f"(unit margin: {margin_per_unit:,.2f})"
                    )
                elif min_margin_pct is not None and margin_pct is not None and margin_pct < min_margin_pct:
                    warnings.append(
                        f"Margin for '{item.product_name}' ({margin_pct:.2f}%) is below the minimum "
                        f"threshold ({min_margin_pct:.2f}%)"
                    )

                if item.expected_qty is not None:
                    estimated_contribution = cls.calculate_contribution(
                        margin_per_unit, item.expected_qty
                    )

        return ItemEvaluation(
            product_id=item.product_id,
            product_name=item.product_name,
            discount_type=item.discount_type,
            discount_value=item.discount_value,
            original_price=quantize_currency(item.original_price),
            discounted_price=discounted_price,
            unit_cost=quantize_currency(item.unit_cost),
            margin_per_unit=margin_per_unit,
            margin_pct=margin_pct,
            expected_qty=item.expected_qty,
            estimated_contribution=estimated_contribution,
            cost_data_available=cost_available,
            price_data_available=price_available,
            warnings=warnings,
        )

    @classmethod
    def evaluate_plan(
        cls,
        items_data: List[ItemInputData],
        min_margin_pct: Optional[Decimal] = None,
    ) -> PlanEvaluation:
        """
        Evaluate full promotion plan across all items and aggregate totals.
        """
        effective_min_margin = min_margin_pct if min_margin_pct is not None else DEFAULT_MIN_MARGIN_PCT

        item_evaluations: List[ItemEvaluation] = []
        plan_warnings: List[str] = []
        assumptions: List[str] = [
            "Prices based on latest effective price history records",
            "Expected quantities are estimated promotional demand volumes",
        ]
        missing_data: List[str] = []
        risks: List[str] = []

        total_orig_rev = Decimal("0.00")
        total_disc_rev = Decimal("0.00")
        total_cost = Decimal("0.00")
        has_any_revenue = False
        all_costs_present = True
        all_prices_present = True
        has_negative_margin = False
        has_below_min_margin = False

        for item in items_data:
            eval_res = cls.evaluate_item(item, min_margin_pct=effective_min_margin)
            item_evaluations.append(eval_res)

            if not eval_res.price_data_available:
                all_prices_present = False
                missing_data.append(f"Price for product {item.product_id} ({item.product_name})")

            if not eval_res.cost_data_available:
                all_costs_present = False
                missing_data.append(f"Unit cost for product {item.product_id} ({item.product_name})")

            if eval_res.margin_per_unit is not None and eval_res.margin_per_unit < Decimal("0"):
                has_negative_margin = True

            if (
                eval_res.margin_pct is not None
                and effective_min_margin is not None
                and eval_res.margin_pct < effective_min_margin
            ):
                has_below_min_margin = True

            if eval_res.expected_qty is not None:
                if eval_res.original_price is not None:
                    total_orig_rev += eval_res.original_price * Decimal(eval_res.expected_qty)
                    has_any_revenue = True
                if eval_res.discounted_price is not None:
                    total_disc_rev += eval_res.discounted_price * Decimal(eval_res.expected_qty)
                if eval_res.unit_cost is not None:
                    total_cost += eval_res.unit_cost * Decimal(eval_res.expected_qty)
            else:
                missing_data.append(f"Expected sales quantity for product {item.product_id} ({item.product_name})")

        # Plan-level validations
        total_orig_revenue_final = quantize_currency(total_orig_rev) if has_any_revenue else None
        total_disc_revenue_final = quantize_currency(total_disc_rev) if has_any_revenue else None
        
        # Financial validation requires both prices and costs available for all items
        is_financially_validated = all_prices_present and all_costs_present and not has_negative_margin

        if not all_costs_present:
            plan_warnings.append(
                f"{sum(1 for e in item_evaluations if not e.cost_data_available)} of {len(item_evaluations)} "
                f"items missing cost data"
            )
            risks.append("Margin cannot be validated for all items due to missing cost history")

        if has_negative_margin:
            risks.append("One or more products have negative margins (selling below unit cost)")

        if has_below_min_margin:
            risks.append(
                f"One or more products fall below the target minimum margin of {effective_min_margin}%"
            )

        total_est_cost_final: Optional[Decimal] = None
        total_est_margin_final: Optional[Decimal] = None
        avg_margin_pct_final: Optional[Decimal] = None

        if all_costs_present and has_any_revenue:
            total_est_cost_final = quantize_currency(total_cost)
            if total_disc_revenue_final is not None:
                total_est_margin_final = quantize_currency(total_disc_revenue_final - total_est_cost_final)
                if total_disc_revenue_final > Decimal("0"):
                    avg_margin_pct_final = quantize_pct(
                        (total_est_margin_final / total_disc_revenue_final) * Decimal("100.0")
                    )

        return PlanEvaluation(
            items=item_evaluations,
            total_original_revenue=total_orig_revenue_final,
            total_discounted_revenue=total_disc_revenue_final,
            total_estimated_cost=total_est_cost_final,
            total_estimated_margin=total_est_margin_final,
            avg_margin_pct=avg_margin_pct_final,
            is_financially_validated=is_financially_validated,
            min_margin_pct=effective_min_margin,
            warnings=plan_warnings,
            assumptions=assumptions,
            missing_data=missing_data,
            risks=risks,
        )
