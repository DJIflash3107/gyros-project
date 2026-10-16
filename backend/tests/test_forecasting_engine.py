from datetime import date, timedelta
from decimal import Decimal
import pandas as pd
import pytest

from app.services.forecasting_engine import (
    forecast,
    backtest,
    check_sufficiency,
    prepare_daily_series,
    ForecastOutput,
    BacktestOutput,
)


def _make_daily_data(start_date: date, values: list[float], granularity: str = "daily"):
    data = []
    for i, val in enumerate(values):
        data.append({
            "date": start_date + timedelta(days=i),
            "sold_qty": val,
            "granularity": granularity,
            "record_status": "active",
        })
    return data


def test_sma_basic():
    """SMA on a clean 14-day series produces correct values."""
    start = date(2026, 1, 1)
    values = [10.0] * 14
    data = _make_daily_data(start, values)

    out: ForecastOutput = forecast(data, horizon_days=7, window_size=7)

    assert out.is_reliable is True
    assert out.method == "moving_average"
    assert out.observations_used == 14
    assert len(out.predictions) == 7
    for pt in out.predictions:
        assert pt.predicted_qty == Decimal("10.000")
        assert pt.forecast_date > start + timedelta(days=13)


def test_wsma_with_weekday_pattern():
    """WSMA detects and applies Mon-Sun pattern correctly on 35+ days with >=5 weekdays."""
    # 2026-01-05 is a Monday
    start = date(2026, 1, 5)
    # 5 full weeks (35 days) with clear weekday demand:
    # Mon=10, Tue=20, Wed=30, Thu=40, Fri=50, Sat=60, Sun=70
    weekday_pattern = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0]
    values = weekday_pattern * 5  # 35 days
    data = _make_daily_data(start, values)

    out: ForecastOutput = forecast(data, horizon_days=7, window_size=7)

    assert out.is_reliable is True
    assert out.method == "weekday_seasonal"
    assert out.observations_used == 35
    assert len(out.predictions) == 7

    # The 7 forecast days should exactly follow Monday to Sunday pattern
    expected = [Decimal(f"{v:.3f}") for v in weekday_pattern]
    actual = [pt.predicted_qty for pt in out.predictions]
    assert actual == expected


def test_insufficient_data_below_14():
    """Returns insufficient flag and empty predictions with <14 observations."""
    start = date(2026, 1, 1)
    for count in [0, 1, 7, 13]:
        data = _make_daily_data(start, [5.0] * count)
        out = forecast(data, horizon_days=7, window_size=7)
        assert out.is_reliable is False
        assert out.method == "none"
        assert len(out.predictions) == 0
        assert "Insufficient" in out.reliability_note or "No daily" in out.reliability_note

        suff = check_sufficiency(data)
        assert suff["supports_baseline"] is False
        assert suff["supports_weekday"] is False


def test_zero_demand_all_zeros():
    """All sold_qty=0 produces forecast of 0.0 with reliability note and handles metrics gracefully."""
    start = date(2026, 1, 1)
    values = [0.0] * 20
    data = _make_daily_data(start, values)

    out = forecast(data, horizon_days=5, window_size=7)
    assert out.is_reliable is True
    assert out.reliability_note == "All historical sales are zero"
    assert len(out.predictions) == 5
    for pt in out.predictions:
        assert pt.predicted_qty == Decimal("0.000")

    # Backtest with all zeros
    bt: BacktestOutput = backtest(data, window_size=7, test_days=5)
    assert bt.is_reliable is True
    assert bt.mae == Decimal("0.0000")
    assert bt.forecast_bias == Decimal("0.0000")
    assert bt.wape is None  # Undefined when sum(actuals) == 0


def test_mixed_granularity_filtering():
    """Only daily observations used, weekly/monthly ignored."""
    start = date(2026, 1, 1)
    data = _make_daily_data(start, [10.0] * 14, granularity="daily")
    # Add weekly and monthly rows that would skew results if included
    data.append({"date": date(2026, 1, 20), "sold_qty": 500.0, "granularity": "weekly", "record_status": "active"})
    data.append({"date": date(2026, 1, 31), "sold_qty": 2000.0, "granularity": "monthly", "record_status": "active"})

    out = forecast(data, horizon_days=3, window_size=7)
    assert out.is_reliable is True
    assert out.observations_used == 14  # Only 14 daily rows used
    for pt in out.predictions:
        assert pt.predicted_qty == Decimal("10.000")


def test_backtest_mae_calculation():
    """MAE matches exact hand-calculated value."""
    # 14 training days + 3 test days = 17 days
    # Training days: all 10.0 (so SMA forecast = 10.0)
    # Test days: 12.0, 15.0, 7.0
    # Errors: pred - act -> (10 - 12) = -2, (10 - 15) = -5, (10 - 7) = 3
    # Absolute errors: 2, 5, 3 -> sum = 10 -> MAE = 10 / 3 = 3.3333...
    # WAPE: sum(|errors|) / sum(actuals) = 10 / 34 = 0.294117... -> 0.2941
    # Bias: (-2 + -5 + 3) / 3 = -4 / 3 = -1.3333...
    start = date(2026, 1, 1)
    train_vals = [10.0] * 14
    test_vals = [12.0, 15.0, 7.0]
    data = _make_daily_data(start, train_vals + test_vals)

    bt: BacktestOutput = backtest(data, window_size=7, test_days=3)
    assert bt.is_reliable is True
    assert bt.observations_used == 14
    assert bt.test_days == 3
    assert bt.mae == Decimal("3.3333")
    assert bt.wape == Decimal("0.2941")
    assert bt.forecast_bias == Decimal("-1.3333")


def test_backtest_wape_zero_actuals():
    """WAPE is None when sum(actuals) = 0 in test set."""
    start = date(2026, 1, 1)
    train_vals = [10.0] * 14
    test_vals = [0.0, 0.0, 0.0]
    data = _make_daily_data(start, train_vals + test_vals)

    bt: BacktestOutput = backtest(data, window_size=7, test_days=3)
    assert bt.is_reliable is True
    assert bt.wape is None
    assert bt.mae == Decimal("10.0000")
    assert bt.forecast_bias == Decimal("10.0000")


def test_backtest_bias_positive_negative():
    """Bias correctly reflects over-prediction (positive) and under-prediction (negative)."""
    start = date(2026, 1, 1)
    train_vals = [10.0] * 14

    # Over-prediction test: actuals are 6.0, predicted is 10.0 -> bias = +4.0
    test_over = [6.0, 6.0]
    bt_over = backtest(_make_daily_data(start, train_vals + test_over), window_size=7, test_days=2)
    assert bt_over.forecast_bias == Decimal("4.0000")

    # Under-prediction test: actuals are 15.0, predicted is 10.0 -> bias = -5.0
    test_under = [15.0, 15.0]
    bt_under = backtest(_make_daily_data(start, train_vals + test_under), window_size=7, test_days=2)
    assert bt_under.forecast_bias == Decimal("-5.0000")


def test_reproducibility():
    """Same input produces identical output on repeated calls."""
    start = date(2026, 2, 1)
    values = [12.5, 14.0, 11.2, 18.9, 21.0, 16.5, 9.8] * 5  # 35 days
    data = _make_daily_data(start, values)

    out1 = forecast(data, horizon_days=14, window_size=7)
    out2 = forecast(data, horizon_days=14, window_size=7)

    assert out1.method == out2.method
    assert out1.observations_used == out2.observations_used
    assert len(out1.predictions) == len(out2.predictions)
    for p1, p2 in zip(out1.predictions, out2.predictions):
        assert p1.forecast_date == p2.forecast_date
        assert p1.predicted_qty == p2.predicted_qty
        assert p1.weekday == p2.weekday


def test_gaps_in_series():
    """Missing dates don't cause crash or fabrication; only available observations are used."""
    # 14 observations with date jumps
    dates = [
        date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6),
        date(2026, 1, 10), date(2026, 1, 12), date(2026, 1, 15), date(2026, 1, 18),
        date(2026, 1, 20), date(2026, 1, 22), date(2026, 1, 25), date(2026, 1, 28),
        date(2026, 2, 1), date(2026, 2, 5),
    ]
    data = [{"date": d, "sold_qty": 20.0, "granularity": "daily"} for d in dates]

    out = forecast(data, horizon_days=7, window_size=7)
    assert out.is_reliable is True
    assert out.observations_used == 14
    assert out.training_end == date(2026, 2, 5)
    # First forecast day starts after the last observed date
    assert out.predictions[0].forecast_date == date(2026, 2, 6)
    assert out.predictions[0].predicted_qty == Decimal("20.000")


def test_weekday_fallback_to_sma():
    """When >=35 observations but <5 distinct weekdays (e.g., weekend-only pop-up store), falls back to SMA."""
    # 36 observations, but only on Saturdays and Sundays (2 distinct weekdays)
    start = date(2026, 1, 3)  # Saturday
    data = []
    current = start
    while len(data) < 36:
        if current.weekday() in (5, 6):
            data.append({"date": current, "sold_qty": 50.0, "granularity": "daily"})
        current += timedelta(days=1)

    suff = check_sufficiency(data)
    assert suff["daily_observations"] == 36
    assert suff["distinct_weekdays"] == 2
    assert suff["supports_baseline"] is True
    assert suff["supports_weekday"] is False

    out = forecast(data, horizon_days=7, window_size=7)
    assert out.is_reliable is True
    assert out.method == "moving_average"
    assert out.observations_used == 36


def test_method_selection_logic():
    """Correct method chosen at 13 (none), 14 (SMA), 34 (SMA), 35 (WSMA)."""
    start = date(2026, 1, 5)  # Monday

    # 13 observations -> none
    out13 = forecast(_make_daily_data(start, [10.0] * 13))
    assert out13.method == "none"
    assert out13.is_reliable is False

    # 14 observations across 7 weekdays -> moving_average
    out14 = forecast(_make_daily_data(start, [10.0] * 14))
    assert out14.method == "moving_average"
    assert out14.is_reliable is True

    # 34 observations across 7 weekdays -> moving_average
    out34 = forecast(_make_daily_data(start, [10.0] * 34))
    assert out34.method == "moving_average"
    assert out34.is_reliable is True

    # 35 observations across 7 weekdays -> weekday_seasonal
    out35 = forecast(_make_daily_data(start, [10.0] * 35))
    assert out35.method == "weekday_seasonal"
    assert out35.is_reliable is True
