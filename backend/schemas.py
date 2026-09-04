from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Product(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_shelf_life_days: int
    optimal_temp_c: float


class Batch(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity_kg: float
    production_date: date
    expiry_date: date
    current_status: str


class TelemetryData(BaseModel):
    batch_id: int
    temperature_c: float
    humidity: float = Field(ge=0, le=100)
    time: Optional[datetime] = None


class TelemetryReading(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    time: datetime
    batch_id: Optional[int]
    temperature_c: Optional[float]
    humidity: Optional[float]
    spoilage_risk_score: Optional[float]


class SalesCreate(BaseModel):
    product_id: int
    date: date
    units_sold: float = Field(ge=0)


class SalesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    date: date
    units_sold: float


class DemandEvaluation(BaseModel):
    mae: float
    wmape: float
    forecast_bias: float
    pinball_loss_q10: float
    pinball_loss_q50: float
    pinball_loss_q90: float
    asymmetric_loss: float
    test_period_days: int

class BurnoutPoint(BaseModel):
    day: int
    predicted_demand: float
    dynamic_spoilage: float
    remaining_stock: float


class ForecastResponse(BaseModel):
    batch_id: int
    product_id: int
    product_name: str
    remaining_shelf_life_days: float
    spoilage_risk_score: float
    predicted_temperature_c: float
    forecast_method: str
    sample_count: int
    current_status: str

    demand_forecast_7d: list[float] = Field(default_factory=list)
    model_evaluation: Optional[DemandEvaluation] = None
    burnout_timeline: list[BurnoutPoint] = Field(default_factory=list)
    predicted_waste_units: float = 0
    production_recommendation: float = 0
    lead_time_days: int = 2
    dynamic_rop: float = 0
   