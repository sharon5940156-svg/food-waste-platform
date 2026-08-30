from datetime import date, datetime, timezone
from typing import Optional, Sequence

import pandas as pd
from statsmodels.tsa.holtwinters import SimpleExpSmoothing

Q10 = 2.5
MOVING_AVERAGE_WINDOW = 5


def compute_spoilage_risk(
    temperature_c: float,
    humidity: float,
    optimal_temp_c: float,
) -> float:
    """Instant 0–1 risk from temperature abuse and elevated humidity."""
    temp_deviation = max(0.0, temperature_c - optimal_temp_c)
    temp_risk = min(1.0, temp_deviation / 12.0)
    humidity_risk = min(1.0, max(0.0, humidity - 75.0) / 25.0)
    return round(min(1.0, 0.75 * temp_risk + 0.25 * humidity_risk), 4)


def _q10_rate(temperature_c: float, optimal_temp_c: float) -> float:
    return Q10 ** ((temperature_c - optimal_temp_c) / 10.0)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _telemetry_frame(rows: Sequence) -> pd.DataFrame:
    records = [
        {
            "time": _to_utc(row.time),
            "temperature_c": row.temperature_c,
            "humidity": row.humidity,
        }
        for row in rows
        if row.temperature_c is not None
    ]
    if not records:
        return pd.DataFrame(columns=["time", "temperature_c", "humidity"])
    return pd.DataFrame(records).sort_values("time").reset_index(drop=True)


def _predict_temperature(df: pd.DataFrame, fallback: float) -> tuple[float, str]:
    if df.empty:
        return fallback, "optimal_fallback"

    series = df.set_index("time")["temperature_c"].astype(float)
    if len(series) >= 2:
        series = series.resample("15min").mean().interpolate(limit_direction="both")

    if len(series) >= 3:
        try:
            fitted = SimpleExpSmoothing(series, initialization_method="estimated").fit(
                optimized=True
            )
            predicted = float(fitted.forecast(1).iloc[0])
            return predicted, "exponential_smoothing"
        except (ValueError, IndexError):
            pass

    window = min(MOVING_AVERAGE_WINDOW, len(series))
    predicted = float(series.tail(window).mean())
    return predicted, "moving_average"


def _consumed_equivalent_hours(
    df: pd.DataFrame,
    now: datetime,
    production: datetime,
    optimal_temp_c: float,
) -> float:
    if df.empty:
        elapsed_hours = max(0.0, (now - production).total_seconds() / 3600.0)
        return elapsed_hours

    consumed = 0.0
    times = df["time"]
    temps = df["temperature_c"]

    first_time = times.iloc[0]
    if first_time > production:
        pre_hours = (first_time - production).total_seconds() / 3600.0
        consumed += max(0.0, pre_hours)

    for i in range(len(df)):
        temp = float(temps.iloc[i])
        start = times.iloc[i]
        end = times.iloc[i + 1] if i + 1 < len(df) else now
        dt_hours = max(0.0, (end - start).total_seconds() / 3600.0)
        consumed += dt_hours * _q10_rate(temp, optimal_temp_c)

    return consumed


def forecast_shelf_life(
    telemetry_rows: Sequence,
    base_shelf_life_days: int,
    optimal_temp_c: float,
    production_date: date,
    expiry_date: date,
    now: Optional[datetime] = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    production = datetime.combine(production_date, datetime.min.time(), tzinfo=timezone.utc)
    df = _telemetry_frame(telemetry_rows)

    predicted_temp, method = _predict_temperature(df, fallback=optimal_temp_c)
    consumed_hours = _consumed_equivalent_hours(df, now, production, optimal_temp_c)

    budget_hours = max(1.0, base_shelf_life_days * 24.0)
    remaining_hours = max(0.0, budget_hours - consumed_hours)
    future_rate = max(0.15, _q10_rate(predicted_temp, optimal_temp_c))
    remaining_days = remaining_hours / (24.0 * future_rate)

    calendar_remaining = max(0, (expiry_date - now.date()).days)
    remaining_days = round(min(remaining_days, float(calendar_remaining)), 2)

    latest_humidity = 60.0
    if not df.empty and df["humidity"].notna().any():
        latest_humidity = float(df["humidity"].dropna().iloc[-1])
    instant_risk = compute_spoilage_risk(predicted_temp, latest_humidity, optimal_temp_c)
    budget_risk = 1.0 - min(1.0, remaining_days / max(base_shelf_life_days, 1))
    spoilage_risk = round(min(1.0, 0.5 * instant_risk + 0.5 * budget_risk), 4)

    return {
        "remaining_shelf_life_days": remaining_days,
        "spoilage_risk_score": spoilage_risk,
        "predicted_temperature_c": round(predicted_temp, 2),
        "forecast_method": method,
        "sample_count": int(len(df)),
    }
