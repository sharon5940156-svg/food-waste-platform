from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload

from database import get_db
from forecasting import compute_spoilage_risk, forecast_shelf_life
from models import Batch, Product, Telemetry
from schemas import Batch as BatchSchema
from schemas import ForecastResponse, Product as ProductSchema, TelemetryData, TelemetryReading

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


@app.get("/batches/{batch_id}/forecast", response_model=ForecastResponse)
def forecast_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = (
        db.query(Batch)
        .options(joinedload(Batch.product))
        .filter(Batch.id == batch_id)
        .first()
    )
    if batch is None:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")

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
    return ForecastResponse(
        batch_id=batch.id,
        product_id=batch.product_id,
        product_name=batch.product.name,
        current_status=batch.current_status,
        **forecast,
    )
