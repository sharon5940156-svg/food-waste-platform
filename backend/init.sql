CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    base_shelf_life_days INTEGER NOT NULL,
    optimal_temp_c DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS batches (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity_kg DOUBLE PRECISION NOT NULL,
    production_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    current_status VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry (
    time TIMESTAMPTZ NOT NULL,
    batch_id INTEGER REFERENCES batches(id),
    temperature_c DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    spoilage_risk_score DOUBLE PRECISION
);

SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE);

INSERT INTO products (name, base_shelf_life_days, optimal_temp_c)
VALUES
    ('Milk', 10, 4.0),
    ('Fresh Berries', 5, 2.0),
    ('Raw Poultry', 3, 1.0);

INSERT INTO batches (product_id, quantity_kg, production_date, expiry_date, current_status)
VALUES
    (1, 250.0, CURRENT_DATE - INTERVAL '2 days', CURRENT_DATE + INTERVAL '8 days', 'in_storage'),
    (2, 80.5, CURRENT_DATE - INTERVAL '1 day', CURRENT_DATE + INTERVAL '4 days', 'in_transit'),
    (3, 120.0, CURRENT_DATE, CURRENT_DATE + INTERVAL '3 days', 'in_storage');
