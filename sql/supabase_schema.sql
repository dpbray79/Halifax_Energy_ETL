-- ═══════════════════════════════════════════════════════════════════════════════
-- supabase_schema.sql
-- Halifax Area Energy Demand Forecasting — PostgreSQL Schema for Supabase
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- USAGE:
--   1. Create Supabase project at https://supabase.com
--   2. Go to SQL Editor in Supabase Dashboard
--   3. Paste and run this entire script
--
-- CHANGES FROM SQL SERVER:
--   • IDENTITY(1,1) → SERIAL or GENERATED ALWAYS AS IDENTITY
--   • DATETIME → TIMESTAMPTZ (timezone-aware timestamps)
--   • BIT → BOOLEAN
--   • FLOAT → DOUBLE PRECISION
--   • VARCHAR → TEXT (PostgreSQL preferred)
--   • GETDATE() → NOW()
--   • Removed SQL Server-specific syntax (GO, sys.tables)
--
-- ═══════════════════════════════════════════════════════════════════════════════

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── 1. stg_NSP_Load (Staging: Nova Scotia Power Load Data) ────────────────────

CREATE TABLE IF NOT EXISTS stg_nsp_load (
    load_id      SERIAL PRIMARY KEY,
    datetime     TIMESTAMPTZ NOT NULL,
    load_mw      DOUBLE PRECISION NOT NULL,
    source       TEXT,                      -- e.g. 'ElectricityMaps_CA-NS', 'CCEI_HFED'
    inserted_at  TIMESTAMPTZ DEFAULT NOW(),
    is_processed BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_stg_nsp_load_datetime ON stg_nsp_load(datetime);

COMMENT ON TABLE stg_nsp_load IS 'Staging table for Nova Scotia electricity load data from multiple sources';

-- ── 2. stg_Weather (Staging: Weather Observations) ────────────────────────────

CREATE TABLE IF NOT EXISTS stg_weather (
    weather_id     SERIAL PRIMARY KEY,
    datetime       TIMESTAMPTZ NOT NULL,
    temp_c         DOUBLE PRECISION,
    windspeed_kmh  DOUBLE PRECISION,
    precip_mm      DOUBLE PRECISION,
    humidity_pct   DOUBLE PRECISION,
    source         TEXT,                    -- e.g. 'Environment_Canada_CYHZ'
    inserted_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stg_weather_datetime ON stg_weather(datetime);

COMMENT ON TABLE stg_weather IS 'Staging table for Halifax Stanfield weather observations';

-- ── 3. ETL_Watermark (Incremental Load Tracking) ──────────────────────────────

CREATE TABLE IF NOT EXISTS etl_watermark (
    watermark_id   SERIAL PRIMARY KEY,
    source_name    TEXT NOT NULL UNIQUE,
    last_extracted TIMESTAMPTZ NOT NULL DEFAULT '2023-01-01'::TIMESTAMPTZ,
    rows_inserted  INTEGER DEFAULT 0,
    status         TEXT DEFAULT 'OK',      -- OK, ERROR, PENDING
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Pre-seed watermark rows for all data sources
INSERT INTO etl_watermark (source_name, last_extracted, status)
VALUES
    ('CCEI_HFED',               '2023-01-01', 'PENDING'),
    ('ElectricityMaps_CA-NS',   '2023-01-01', 'PENDING'),
    ('NBPower_NS_Interconnect', '2023-01-01', 'PENDING'),
    ('Environment_Canada_CYHZ', '2023-01-01', 'PENDING'),
    ('OASIS_AWS',               '2023-01-01', 'PENDING')
ON CONFLICT (source_name) DO NOTHING;

COMMENT ON TABLE etl_watermark IS 'Tracks last successful extraction timestamp per data source';

-- ── 4. Fact_Energy_Weather (Gold Table: Merged Energy + Weather) ──────────────

CREATE TABLE IF NOT EXISTS fact_energy_weather (
    fact_id              SERIAL PRIMARY KEY,
    date_id              INTEGER,              -- FK to dim_date (optional)
    datetime             TIMESTAMPTZ NOT NULL UNIQUE,
    load_mw              DOUBLE PRECISION NOT NULL,
    temp_c               DOUBLE PRECISION,
    windspeed_kmh        DOUBLE PRECISION,
    precip_mm            DOUBLE PRECISION,
    hdd_flag             BOOLEAN,              -- Heating degree day (temp_c < 18)
    cdd_flag             BOOLEAN,              -- Cooling degree day (temp_c > 22)
    lag_load_24h         DOUBLE PRECISION,     -- Load 24 hours ago
    lag_load_168h        DOUBLE PRECISION,     -- Load 168 hours ago (1 week)
    windchill            DOUBLE PRECISION,     -- temp_c * windspeed_kmh
    commercial_area_pct  DOUBLE PRECISION,
    industrial_area_pct  DOUBLE PRECISION,
    is_holiday           BOOLEAN DEFAULT FALSE,
    hour                 INTEGER,              -- Extracted from datetime
    day_of_week          INTEGER,              -- 0 = Sunday, 6 = Saturday
    month                INTEGER
);

CREATE INDEX IF NOT EXISTS idx_fact_energy_weather_datetime ON fact_energy_weather(datetime);
CREATE INDEX IF NOT EXISTS idx_fact_energy_weather_date_id ON fact_energy_weather(date_id);

COMMENT ON TABLE fact_energy_weather IS 'Gold table merging load data with weather features for ML training';

-- ── 5. Dim_Date (Date Dimension Table) ────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dim_date (
    date_id      SERIAL PRIMARY KEY,
    datetime     TIMESTAMPTZ NOT NULL UNIQUE,
    hour         INTEGER NOT NULL,
    day_of_week  INTEGER NOT NULL,           -- 0 = Sunday
    month        INTEGER NOT NULL,
    year         INTEGER NOT NULL,
    is_holiday   BOOLEAN DEFAULT FALSE,
    holiday_name TEXT,
    season       TEXT                        -- Spring, Summer, Fall, Winter
);

CREATE INDEX IF NOT EXISTS idx_dim_date_datetime ON dim_date(datetime);
CREATE INDEX IF NOT EXISTS idx_dim_date_is_holiday ON dim_date(is_holiday);

COMMENT ON TABLE dim_date IS 'Date dimension with holidays, seasons, and temporal features';

-- ── 6. Model_Predictions (XGBoost Forecast Results) ───────────────────────────

CREATE TABLE IF NOT EXISTS model_predictions (
    pred_id            SERIAL PRIMARY KEY,
    date_id            INTEGER,
    datetime           TIMESTAMPTZ NOT NULL,
    predicted_load_mw  DOUBLE PRECISION,
    run_rmse           DOUBLE PRECISION,      -- Root Mean Squared Error
    run_si_pct         DOUBLE PRECISION,      -- Scatter Index %
    forecast_horizon   TEXT,                  -- H1, H2, H3
    model_version      TEXT,
    model_run_at       TIMESTAMPTZ DEFAULT NOW(),
    is_backtest        BOOLEAN DEFAULT FALSE,
    residual_mw        DOUBLE PRECISION       -- Actual - Predicted (computed later)
);

CREATE INDEX IF NOT EXISTS idx_model_predictions_datetime ON model_predictions(datetime);
CREATE INDEX IF NOT EXISTS idx_model_predictions_horizon ON model_predictions(forecast_horizon);

COMMENT ON TABLE model_predictions IS 'XGBoost model predictions with performance metrics';

-- ═══════════════════════════════════════════════════════════════════════════════
-- Row-Level Security (RLS) Policies
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Enable RLS if you want to add authentication later
-- For now, we'll keep tables public for the dashboard

-- Example: Enable RLS on predictions table
-- ALTER TABLE model_predictions ENABLE ROW LEVEL SECURITY;

-- Allow public read access (you can restrict this later)
-- CREATE POLICY "Allow public read access" ON model_predictions
--     FOR SELECT USING (true);

-- ═══════════════════════════════════════════════════════════════════════════════
-- Useful Validation Queries
-- ═══════════════════════════════════════════════════════════════════════════════

-- Row counts by source
-- SELECT source, COUNT(*) AS rows,
--        MIN(datetime) AS earliest,
--        MAX(datetime) AS latest
-- FROM   stg_nsp_load
-- GROUP  BY source
-- ORDER  BY rows DESC;

-- Monthly coverage check
-- SELECT TO_CHAR(datetime, 'YYYY-MM') AS year_month,
--        COUNT(*) AS hourly_rows,
--        ROUND(AVG(load_mw)::NUMERIC, 2) AS avg_load_mw,
--        MIN(load_mw) AS min_load_mw,
--        MAX(load_mw) AS max_load_mw
-- FROM   stg_nsp_load
-- GROUP  BY TO_CHAR(datetime, 'YYYY-MM')
-- ORDER  BY year_month;

-- Weather coverage
-- SELECT TO_CHAR(datetime, 'YYYY-MM') AS year_month,
--        COUNT(*) AS rows,
--        ROUND(AVG(temp_c)::NUMERIC, 2) AS avg_temp,
--        MIN(temp_c) AS min_temp,
--        MAX(temp_c) AS max_temp
-- FROM   stg_weather
-- GROUP  BY TO_CHAR(datetime, 'YYYY-MM')
-- ORDER  BY year_month;

-- Gap detection (missing hours in load data)
-- WITH hours AS (
--     SELECT generate_series(
--         '2023-01-01'::TIMESTAMPTZ,
--         NOW(),
--         INTERVAL '1 hour'
--     ) AS hr
-- )
-- SELECT h.hr AS missing_hour
-- FROM   hours h
-- LEFT   JOIN stg_nsp_load l ON l.datetime = h.hr
-- WHERE  l.load_id IS NULL
-- ORDER  BY h.hr
-- LIMIT 100;

-- ═══════════════════════════════════════════════════════════════════════════════
-- Schema Created Successfully!
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Next Steps:
--   1. Run Python seed script: python scripts/seed_historical_data.py
--   2. Verify data: SELECT COUNT(*) FROM stg_nsp_load;
--   3. Set up Supabase API: Auto-generated REST endpoints ready!
--
-- ═══════════════════════════════════════════════════════════════════════════════
