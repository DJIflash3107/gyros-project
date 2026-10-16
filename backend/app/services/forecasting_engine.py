"""
Forecasting Engine — Pure Statistical Computation Module.

Zero external DB, HTTP, or LLM dependencies.
Implements Simple Moving Average (SMA), Weekday-Seasonal Moving Average (WSMA),
data sufficiency evaluation, time-ordered backtesting, and forecast accuracy metrics (MAE, WAPE, Bias).
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


# Constants for data sufficiency thresholds
MIN_BASELINE_OBSERVATIONS = 14
MIN_WEEKDAY_OBSERVATIONS = 35
MIN_DISTINCT_WEEKDAYS = 5


@dataclass
class ForecastPoint:
    forecast_date: date
    predicted_qty: Decimal
    weekday: int  # 0=Monday, 6=Sunday


@dataclass
class ForecastOutput:
    method: str  # "moving_average", "weekday_seasonal", or "none"
    horizon_days: int
    window_size: int
    training_start: Optional[date]
    training_end: Optional[date]
    observations_used: int
    is_reliable: bool
    reliability_note: Optional[str]
    predictions: List[ForecastPoint] = field(default_factory=list)


@dataclass
class BacktestPoint:
    date: date
    actual: Decimal
    predicted: Decimal


@dataclass
class BacktestOutput:
    method: str
    window_size: int
    test_days: int
    training_start: Optional[date]
    training_end: Optional[date]
    test_start: Optional[date]
    test_end: Optional[date]
    observations_used: int
    mae: Optional[Decimal]
    wape: Optional[Decimal]
    forecast_bias: Optional[Decimal]
    is_reliable: bool
    reliability_note: Optional[str]
    actuals_vs_predicted: List[Dict[str, Any]] = field(default_factory=list)


def prepare_daily_series(data: Any) -> pd.DataFrame:
    """
    Normalizes raw data into a clean, time-ordered pandas DataFrame.
    Expected columns: 'date' (or 'period_start'), 'sold_qty'.
    Filters out non-daily granularities, missing values, and ensures ascending date order.
    """
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    elif isinstance(data, list):
        if not data:
            return pd.DataFrame(columns=["date", "sold_qty", "weekday"])
        df = pd.DataFrame(data)
    else:
        df = pd.DataFrame(data)

    if df.empty:
        return pd.DataFrame(columns=["date", "sold_qty", "weekday"])

    # If column is period_start, map to date
    if "date" not in df.columns and "period_start" in df.columns:
        df["date"] = df["period_start"]

    # Filter out non-daily granularity if granularity column exists
    if "granularity" in df.columns:
        df = df[df["granularity"] == "daily"].copy()

    # Filter out non-active records if record_status column exists
    if "record_status" in df.columns:
        df = df[df["record_status"] == "active"].copy()

    if "date" not in df.columns or "sold_qty" not in df.columns:
        return pd.DataFrame(columns=["date", "sold_qty", "weekday"])

    # Convert date to python datetime.date
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["sold_qty"] = pd.to_numeric(df["sold_qty"], errors="coerce")

    # Drop NaNs
    df = df.dropna(subset=["date", "sold_qty"]).copy()

    # Sort by date ascending
    df = df.sort_values(by="date", ascending=True)

    # If duplicate dates exist, keep the last observation
    df = df.drop_duplicates(subset=["date"], keep="last")

    # Add weekday column (0=Mon, 6=Sun)
    df["weekday"] = df["date"].apply(lambda d: d.weekday())

    return df.reset_index(drop=True)


def check_sufficiency(data: Any, total_raw_count: Optional[int] = None) -> Dict[str, Any]:
    """
    Validates observation sufficiency for forecasting.
    Returns metadata and flags indicating whether baseline or weekday forecasting is supported.
    """
    df = prepare_daily_series(data)
    daily_count = len(df)
    total_count = total_raw_count if total_raw_count is not None else daily_count

    if daily_count == 0:
        if total_count > 0:
            msg = "Only non-daily observations found. Confirmed daily granularity is required for forecasting."
        else:
            msg = "No daily sales observations found for this product and branch."
        return {
            "total_observations": total_count,
            "daily_observations": 0,
            "distinct_weekdays": 0,
            "date_range_start": None,
            "date_range_end": None,
            "supports_baseline": False,
            "supports_weekday": False,
            "message": msg,
        }

    distinct_weekdays = int(df["weekday"].nunique())
    start_date = df["date"].min()
    end_date = df["date"].max()

    supports_baseline = daily_count >= MIN_BASELINE_OBSERVATIONS
    supports_weekday = daily_count >= MIN_WEEKDAY_OBSERVATIONS and distinct_weekdays >= MIN_DISTINCT_WEEKDAYS

    if not supports_baseline:
        message = (
            f"Insufficient daily observations (found {daily_count}, need {MIN_BASELINE_OBSERVATIONS} minimum). "
            f"Forecast unavailable."
        )
    elif not supports_weekday:
        message = (
            f"Sufficient data for baseline moving average forecast ({daily_count} daily observations). "
            f"Need {MIN_WEEKDAY_OBSERVATIONS}+ observations across {MIN_DISTINCT_WEEKDAYS}+ distinct weekdays "
            f"for weekday-seasonal forecasting (found {distinct_weekdays} weekdays)."
        )
    else:
        message = (
            f"Sufficient data for weekday-seasonal forecast ({daily_count} daily observations "
            f"across {distinct_weekdays} weekdays)."
        )

    return {
        "total_observations": total_count,
        "daily_observations": daily_count,
        "distinct_weekdays": distinct_weekdays,
        "date_range_start": start_date,
        "date_range_end": end_date,
        "supports_baseline": supports_baseline,
        "supports_weekday": supports_weekday,
        "message": message,
    }


def forecast(
    daily_series: Any,
    horizon_days: int = 7,
    window_size: int = 7,
    total_raw_count: Optional[int] = None,
) -> ForecastOutput:
    """
    Generates demand forecast for horizon_days into the future.
    Uses Weekday-Seasonal Moving Average (WSMA) when sufficient data exists,
    otherwise Simple Moving Average (SMA), or flags insufficient data.
    """
    df = prepare_daily_series(daily_series)
    sufficiency = check_sufficiency(df, total_raw_count=total_raw_count)

    obs_count = sufficiency["daily_observations"]
    start_date = sufficiency["date_range_start"]
    end_date = sufficiency["date_range_end"]

    # Insufficient data
    if not sufficiency["supports_baseline"]:
        return ForecastOutput(
            method="none",
            horizon_days=horizon_days,
            window_size=window_size,
            training_start=start_date,
            training_end=end_date,
            observations_used=obs_count,
            is_reliable=False,
            reliability_note=sufficiency["message"],
            predictions=[],
        )

    # Check for zero-demand historical series
    all_zeros = bool((df["sold_qty"] == 0).all())
    reliability_note = "All historical sales are zero" if all_zeros else None

    # Algorithm selection
    if sufficiency["supports_weekday"]:
        method = "weekday_seasonal"
    else:
        method = "moving_average"

    predictions: List[ForecastPoint] = []
    effective_window = max(1, min(window_size, obs_count))
    overall_sma = float(df["sold_qty"].tail(effective_window).mean())

    for step in range(1, horizon_days + 1):
        target_date = end_date + timedelta(days=step)
        target_weekday = target_date.weekday()

        if method == "weekday_seasonal":
            weekday_rows = df[df["weekday"] == target_weekday]
            if len(weekday_rows) > 0:
                # Use up to the last window_size occurrences of this weekday
                pred_qty = float(weekday_rows["sold_qty"].tail(window_size).mean())
            else:
                pred_qty = overall_sma
        else:
            pred_qty = overall_sma

        # Demand cannot be negative
        pred_qty = max(0.0, pred_qty)
        qty_dec = Decimal(f"{pred_qty:.3f}")

        predictions.append(
            ForecastPoint(
                forecast_date=target_date,
                predicted_qty=qty_dec,
                weekday=target_weekday,
            )
        )

    return ForecastOutput(
        method=method,
        horizon_days=horizon_days,
        window_size=window_size,
        training_start=start_date,
        training_end=end_date,
        observations_used=obs_count,
        is_reliable=True,
        reliability_note=reliability_note,
        predictions=predictions,
    )


def backtest(
    daily_series: Any,
    window_size: int = 7,
    test_days: int = 7,
) -> BacktestOutput:
    """
    Performs time-ordered out-of-sample backtesting.
    Training set = historical series excluding the last test_days.
    Test set = last test_days observations.
    Computes MAE, WAPE, and Forecast Bias where mathematically valid.
    """
    df = prepare_daily_series(daily_series)
    total_obs = len(df)

    # Check minimum observations required: at least 14 training days + test_days
    min_required = MIN_BASELINE_OBSERVATIONS + test_days
    if total_obs < min_required:
        return BacktestOutput(
            method="none",
            window_size=window_size,
            test_days=test_days,
            training_start=df["date"].min() if total_obs > 0 else None,
            training_end=df["date"].max() if total_obs > 0 else None,
            test_start=None,
            test_end=None,
            observations_used=total_obs,
            mae=None,
            wape=None,
            forecast_bias=None,
            is_reliable=False,
            reliability_note=(
                f"Insufficient observations for backtesting with test_days={test_days}. "
                f"Requires at least {min_required} daily observations, found {total_obs}."
            ),
            actuals_vs_predicted=[],
        )

    # Time-ordered train/test split
    train_df = df.iloc[:-test_days].copy()
    test_df = df.iloc[-test_days:].copy()

    train_sufficiency = check_sufficiency(train_df)
    train_count = len(train_df)
    training_start = train_df["date"].min()
    training_end = train_df["date"].max()
    test_start = test_df["date"].min()
    test_end = test_df["date"].max()

    if train_sufficiency["supports_weekday"]:
        method = "weekday_seasonal"
    else:
        method = "moving_average"

    effective_window = max(1, min(window_size, train_count))
    overall_sma = float(train_df["sold_qty"].tail(effective_window).mean())

    actuals: List[float] = []
    predictions: List[float] = []
    actuals_vs_predicted: List[Dict[str, Any]] = []

    for _, row in test_df.iterrows():
        t_date = row["date"]
        actual_val = float(row["sold_qty"])
        t_weekday = row["weekday"]

        if method == "weekday_seasonal":
            weekday_rows = train_df[train_df["weekday"] == t_weekday]
            if len(weekday_rows) > 0:
                pred_val = float(weekday_rows["sold_qty"].tail(window_size).mean())
            else:
                pred_val = overall_sma
        else:
            pred_val = overall_sma

        pred_val = max(0.0, pred_val)

        actuals.append(actual_val)
        predictions.append(pred_val)

        actuals_vs_predicted.append(
            {
                "date": t_date,
                "actual": Decimal(f"{actual_val:.3f}"),
                "predicted": Decimal(f"{pred_val:.3f}"),
            }
        )

    # Compute evaluation metrics
    errors = np.array(predictions) - np.array(actuals)
    abs_errors = np.abs(errors)

    mae_val = float(np.mean(abs_errors))
    mae = Decimal(f"{mae_val:.4f}")

    bias_val = float(np.mean(errors))
    bias = Decimal(f"{bias_val:.4f}")

    sum_actuals = float(np.sum(actuals))
    if sum_actuals > 0:
        wape_val = float(np.sum(abs_errors) / sum_actuals)
        wape = Decimal(f"{wape_val:.4f}")
    else:
        # WAPE undefined when sum of actuals is 0
        wape = None

    all_train_zeros = bool((train_df["sold_qty"] == 0).all())
    all_test_zeros = bool((test_df["sold_qty"] == 0).all())
    if all_train_zeros and all_test_zeros:
        reliability_note = "All historical and test sales are zero"
    elif all_train_zeros:
        reliability_note = "All training sales are zero"
    else:
        reliability_note = None

    return BacktestOutput(
        method=method,
        window_size=window_size,
        test_days=test_days,
        training_start=training_start,
        training_end=training_end,
        test_start=test_start,
        test_end=test_end,
        observations_used=train_count,
        mae=mae,
        wape=wape,
        forecast_bias=bias,
        is_reliable=True,
        reliability_note=reliability_note,
        actuals_vs_predicted=actuals_vs_predicted,
    )
