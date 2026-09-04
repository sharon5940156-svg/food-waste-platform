from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload

from database import get_db
from forecasting import compute_spoilage_risk, forecast_shelf_life
from demand_engine import (
    calculate_dynamic_rop,
    evaluate_demand_model,
    forecast_daily_demand,
)
from models import Batch, DailyDemand, Product, Telemetry
from schemas import Batch as BatchSchema
from schemas import (
    ForecastResponse,
    Product as ProductSchema,
    SalesCreate,
    SalesResponse,
    TelemetryData,
    TelemetryReading,
)

app = FastAPI(title="Perishable Food Inventory & Demand Forecasting")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/products", response_model=list[ProductSchema])
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).order_by(Product.id).all()


@app.get("/batches", response_model=list[BatchSchema])
def list_batches(db: Session = Depends(get_db)):
    return db.query(Batch).order_by(Batch.id).all()
@app.get("/batches/fefo", response_model=list[BatchSchema])
def list_batches_fefo(db: Session = Depends(get_db)):
    return (
        db.query(Batch)
        .filter(Batch.current_status.in_(["in_storage", "in_transit"]))
        .order_by(Batch.expiry_date.asc(), Batch.id.asc())
        .all()
    )

@app.post("/telemetry", response_model=TelemetryReading)
def ingest_telemetry(payload: TelemetryData, db: Session = Depends(get_db)):
    batch = (
        db.query(Batch)
        .options(joinedload(Batch.product))
        .filter(Batch.id == payload.batch_id)
        .first()
    )
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Batch {payload.batch_id} not found")

    recorded_at = payload.time or datetime.now(timezone.utc)
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=timezone.utc)

    risk = compute_spoilage_risk(
        payload.temperature_c,
        payload.humidity,
        batch.product.optimal_temp_c,
    )

    reading = Telemetry(
        time=recorded_at,
        batch_id=payload.batch_id,
        temperature_c=payload.temperature_c,
        humidity=payload.humidity,
        spoilage_risk_score=risk,
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


@app.get("/batches/{batch_id}/telemetry", response_model=list[TelemetryReading])
def list_batch_telemetry(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
    return (
        db.query(Telemetry)
        .filter(Telemetry.batch_id == batch_id)
        .order_by(Telemetry.time.asc())
        .all()
    )

@app.post("/sales", response_model=SalesResponse)
def create_sales(payload: SalesCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == payload.product_id).first()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail=f"Product {payload.product_id} not found",
        )

    existing = (
        db.query(DailyDemand)
        .filter(
            DailyDemand.product_id == payload.product_id,
            DailyDemand.date == payload.date,
        )
        .first()
    )

    if existing:
        existing.units_sold = payload.units_sold
        db.commit()
        db.refresh(existing)
        return existing

    sales = DailyDemand(
        product_id=payload.product_id,
        date=payload.date,
        units_sold=payload.units_sold,
    )

    db.add(sales)
    db.commit()
    db.refresh(sales)

    return sales


@app.get("/products/{product_id}/sales", response_model=list[SalesResponse])
def list_sales(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail=f"Product {product_id} not found",
        )

    return (
        db.query(DailyDemand)
        .filter(DailyDemand.product_id == product_id)
        .order_by(DailyDemand.date.asc())
        .all()
    )

@app.get("/batches/{batch_id}/forecast", response_model=ForecastResponse)
def forecast_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = (
        db.query(Batch)
        .options(joinedload(Batch.product))
        .filter(Batch.id == batch_id)
        .first()
    )

    if batch is None:
        raise HTTPException(
            status_code=404,
            detail=f"Batch {batch_id} not found",
        )

    # Existing telemetry / spoilage forecast
    readings = (
        db.query(Telemetry)
        .filter(Telemetry.batch_id == batch_id)
        .order_by(Telemetry.time.asc())
        .all()
    )

    forecast = forecast_shelf_life(
        telemetry_rows=readings,
        base_shelf_life_days=batch.product.base_shelf_life_days,
        optimal_temp_c=batch.product.optimal_temp_c,
        production_date=batch.production_date,
        expiry_date=batch.expiry_date,
    )

    # Historical demand for this product
    historical_sales = (
        db.query(DailyDemand)
        .filter(DailyDemand.product_id == batch.product_id)
        .order_by(DailyDemand.date.asc())
        .all()
    )

    # Demand forecast + model evaluation
    demand_forecast = forecast_daily_demand(
        historical_sales,
        forecast_days=7,
    )

    model_evaluation = evaluate_demand_model(
        historical_sales,
    )
    lead_time_days = 2

    dynamic_rop = calculate_dynamic_rop(
        demand_forecast=demand_forecast,
        mae=model_evaluation["mae"],
        lead_time_days=lead_time_days,
    )

    # Combined stock burnout
    current_stock = float(batch.quantity_kg)
    remaining_shelf_life = float(forecast["remaining_shelf_life_days"])

    if remaining_shelf_life > 0:
        dynamic_spoilage_per_day = current_stock / remaining_shelf_life
    else:
        dynamic_spoilage_per_day = current_stock

    burnout_timeline = []

    for day, demand in enumerate(demand_forecast, start=1):
        spoilage = min(
            dynamic_spoilage_per_day,
            current_stock,
        )

        total_loss = demand + spoilage
        current_stock = max(0.0, current_stock - total_loss)

        burnout_timeline.append(
            {
                "day": day,
                "predicted_demand": round(demand, 2),
                "dynamic_spoilage": round(spoilage, 2),
                "remaining_stock": round(current_stock, 2),
            }
        )

    # Predicted waste:
    # stock remaining after the usable shelf-life window
    predicted_waste_units = 0.0

    if remaining_shelf_life <= 7:
        expiry_day = max(1, int(round(remaining_shelf_life)))

        if expiry_day <= len(burnout_timeline):
            predicted_waste_units = burnout_timeline[expiry_day - 1][
                "remaining_stock"
            ]

    # Production recommendation:
    # amount needed if 7-day demand exceeds current usable stock
    total_forecasted_demand = sum(demand_forecast)

    usable_inventory = max(
        0.0,
        float(batch.quantity_kg) - predicted_waste_units,
    )

    production_recommendation = max(
        0.0,
        total_forecasted_demand - usable_inventory,
    )

    return ForecastResponse(
        batch_id=batch.id,
        product_id=batch.product_id,
        product_name=batch.product.name,
        current_status=batch.current_status,
        demand_forecast_7d=demand_forecast,
        model_evaluation=model_evaluation,
        burnout_timeline=burnout_timeline,
        predicted_waste_units=round(predicted_waste_units, 2),
        production_recommendation=round(production_recommendation, 2),
        lead_time_days=lead_time_days,
        dynamic_rop=dynamic_rop,
        **forecast,
    )
