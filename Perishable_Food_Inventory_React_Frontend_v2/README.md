# Perishable Food Inventory & Demand Forecasting — React Frontend

This frontend is matched to the uploaded FastAPI backend.

## Verified backend routes used

- GET `/health`
- GET `/products`
- GET `/batches`
- GET `/batches/fefo`
- POST `/telemetry`
- GET `/batches/{batch_id}/telemetry`
- POST `/sales`
- GET `/products/{product_id}/sales`
- GET `/batches/{batch_id}/forecast`

The frontend does NOT call `/kpis` or `/telemetry` as global GET endpoints because those routes do not exist in the supplied backend.

## Verified data model

Product:
`id`, `name`, `base_shelf_life_days`, `optimal_temp_c`

Batch:
`id`, `product_id`, `quantity_kg`, `production_date`, `expiry_date`, `current_status`

Telemetry:
`time`, `batch_id`, `temperature_c`, `humidity`, `spoilage_risk_score`

Forecast:
shelf-life, spoilage risk, predicted temperature, demand forecast, model evaluation, burnout timeline, predicted waste, production recommendation, lead time and dynamic ROP.

## Run

```bash
npm install
copy .env.example .env
npm run dev
```

Linux/macOS:
```bash
cp .env.example .env
npm install
npm run dev
```

Default API URL:
`http://localhost:8000`

Change `VITE_API_BASE_URL` if your FastAPI service uses another address.

## Important

The backend CORS configuration currently allows all origins, so the Vite development server can call the API during development.

The frontend expects the FastAPI backend to be running and the database to contain products/batches. It does not fabricate batch data.
