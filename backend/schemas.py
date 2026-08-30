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
