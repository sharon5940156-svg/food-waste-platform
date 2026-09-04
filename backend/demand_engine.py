from typing import Sequence

import pandas as pd
from statsmodels.tsa.holtwinters import (
    ExponentialSmoothing,
    SimpleExpSmoothing,
)


def _prepare_series(historical_sales: Sequence) -> pd.Series:
    """Convert sales records into a clean daily demand series."""
    records = []

    for row in historical_sales:
        records.append(
            {
                "date": pd.to_datetime(row.date),
                "units_sold": float(row.units_sold),
            }
        )

    if not records:
        return pd.Series(dtype=float)

    df = pd.DataFrame(records).sort_values("date")

    series = df.groupby("date")["units_sold"].sum()

    # Ensure every calendar day exists.
    full_index = pd.date_range(
        start=series.index.min(),
        end=series.index.max(),
        freq="D",
    )

    series = series.reindex(full_index, fill_value=0.0)

    return series.astype(float)


def asymmetric_pinball_loss(
    actual: float,
    forecast: float,
    over_penalty: float = 2.5,
    under_penalty: float = 1.0,
) -> float:
    """
    Domain-specific asymmetric forecasting loss.

    Over-forecasting perishable food creates excess inventory
    and therefore receives a larger penalty than under-forecasting.
    """
    error = actual - forecast

    if error >= 0:
        # Under-forecasting.
        return under_penalty * error

    # Over-forecasting.
    return over_penalty * abs(error)


def calculate_wmape(
    actuals: Sequence[float],
    forecasts: Sequence[float],
) -> float:
    """
    Weighted Mean Absolute Percentage Error.

    WMAPE = sum(|actual - forecast|) / sum(actual)
    """
    actual = pd.Series(actuals, dtype=float)
    forecast = pd.Series(forecasts, dtype=float)

    denominator = float(actual.abs().sum())

    if denominator == 0:
        return 0.0

    numerator = float((actual - forecast).abs().sum())

    return round(numerator / denominator * 100.0, 2)


def calculate_forecast_bias(
    actuals: Sequence[float],
    forecasts: Sequence[float],
) -> float:
    """
    Forecast bias.

    Positive = model tends to under-forecast.
    Negative = model tends to over-forecast.
    """
    actual = pd.Series(actuals, dtype=float)
    forecast = pd.Series(forecasts, dtype=float)

    bias = float((actual - forecast).sum())

    return round(bias, 2)


def calculate_pinball_loss(
    actuals: Sequence[float],
    forecasts: Sequence[float],
    quantile: float = 0.5,
) -> float:
    """
    Standard quantile / pinball loss.

    quantile=0.5 corresponds to median forecasting.
    """
    if not 0 < quantile < 1:
        raise ValueError("quantile must be between 0 and 1")

    losses = []

    for actual, forecast in zip(actuals, forecasts):
        error = actual - forecast

        if error >= 0:
            loss = quantile * error
        else:
            loss = (quantile - 1.0) * error

        losses.append(loss)

    if not losses:
        return 0.0

    return round(float(sum(losses) / len(losses)), 2)


def _fit_model(series: pd.Series):
    """Choose a forecasting model based on available history."""
    if len(series) >= 14:
        return ExponentialSmoothing(
            series,
            trend="add",
            initialization_method="estimated",
        )

    return SimpleExpSmoothing(
        series,
        initialization_method="estimated",
    )


def forecast_daily_demand(
    historical_sales: Sequence,
    forecast_days: int = 7,
) -> list[float]:
    """
    Forecast future daily demand.

    Uses exponential smoothing for the operational forecast.
    The evaluation layer separately measures asymmetric business cost.
    """
    series = _prepare_series(historical_sales)

    if series.empty:
        return [0.0] * forecast_days

    if len(series) < 3:
        average_demand = float(series.mean())

        return [
            round(max(0.0, average_demand), 2)
            for _ in range(forecast_days)
        ]

    try:
        model = _fit_model(series)
        fitted = model.fit(optimized=True)
        forecast = fitted.forecast(forecast_days)

        return [
            round(max(0.0, float(value)), 2)
            for value in forecast
        ]

    except (ValueError, IndexError):
        average_demand = float(
            series.tail(min(7, len(series))).mean()
        )

        return [
            round(max(0.0, average_demand), 2)
            for _ in range(forecast_days)
        ]


def evaluate_demand_model(
    historical_sales: Sequence,
) -> dict:
    """
    Chronological holdout evaluation.

    Metrics:
    - MAE
    - WMAPE
    - Forecast bias
    - Pinball loss at q=0.1, 0.5 and 0.9
    - Domain-specific asymmetric loss

    The final 20% of observations form the test period.
    """
    series = _prepare_series(historical_sales)

    if len(series) < 5:
        return {
            "mae": 0.0,
            "wmape": 0.0,
            "forecast_bias": 0.0,
            "pinball_loss_q10": 0.0,
            "pinball_loss_q50": 0.0,
            "pinball_loss_q90": 0.0,
            "asymmetric_loss": 0.0,
            "test_period_days": 0,
        }

    test_size = max(1, int(len(series) * 0.2))

    train = series.iloc[:-test_size]
    test = series.iloc[-test_size:]

    try:
        model = _fit_model(train)
        fitted = model.fit(optimized=True)
        predictions = fitted.forecast(len(test))

    except (ValueError, IndexError):
        fallback = float(
            train.tail(min(7, len(train))).mean()
        )

        predictions = pd.Series(
            [fallback] * len(test),
            index=test.index,
        )

    actual_values = [
        float(value)
        for value in test.values
    ]

    predicted_values = [
        max(0.0, float(value))
        for value in predictions.values
    ]

    errors = [
        abs(actual - forecast)
        for actual, forecast in zip(
            actual_values,
            predicted_values,
        )
    ]

    mae = (
        sum(errors) / len(errors)
        if errors
        else 0.0
    )

    asymmetric_losses = [
        asymmetric_pinball_loss(
            actual=actual,
            forecast=forecast,
            over_penalty=2.5,
            under_penalty=1.0,
        )
        for actual, forecast in zip(
            actual_values,
            predicted_values,
        )
    ]

    return {
        "mae": round(max(0.0, mae), 2),
        "wmape": calculate_wmape(
            actual_values,
            predicted_values,
        ),
        "forecast_bias": calculate_forecast_bias(
            actual_values,
            predicted_values,
        ),
        "pinball_loss_q10": calculate_pinball_loss(
            actual_values,
            predicted_values,
            quantile=0.1,
        ),
        "pinball_loss_q50": calculate_pinball_loss(
            actual_values,
            predicted_values,
            quantile=0.5,
        ),
        "pinball_loss_q90": calculate_pinball_loss(
            actual_values,
            predicted_values,
            quantile=0.9,
        ),
        "asymmetric_loss": round(
            float(sum(asymmetric_losses)),
            2,
        ),
        "test_period_days": int(test_size),
    }

def calculate_dynamic_rop(
    demand_forecast: Sequence[float],
    mae: float,
    lead_time_days: int = 2,
) -> float:
    """
    Calculate Dynamic Reorder Point (ROP).

    ROP = expected demand during lead time + safety stock

    Safety stock is based on model error:
    safety_stock = MAE * sqrt(lead_time_days)
    """
    if lead_time_days <= 0:
        raise ValueError("lead_time_days must be greater than 0")

    if not demand_forecast:
        return 0.0

    lead_time_demand = sum(
        float(value)
        for value in demand_forecast[:lead_time_days]
    )

    safety_stock = max(0.0, float(mae)) * (lead_time_days ** 0.5)

    return round(
        max(0.0, lead_time_demand + safety_stock),
        2,
    )