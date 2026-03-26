"""
transform_gold.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Area Energy Demand Forecasting — Gold Layer Transformation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PURPOSE
    Replaces legacy SSIS package logic. Merges stg_nsp_load and stg_weather 
    into fact_energy_weather. Computes derived features (HDD/CDD, WindChill, 
    Lags, Temporal features) required for XGBoost training.

USAGE
    python scripts/transform_gold.py

Author : Dylan Bray · March 2026
"""

import os, sys, logging
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("transform")

DB_URL = os.getenv("DATABASE_URL")

def transform():
    if not DB_URL:
        log.error("DATABASE_URL not set")
        return

    log.info("Starting Gold Layer Transformation …")
    engine = create_engine(DB_URL)

    with engine.begin() as conn:
        log.info("  1. Clearing existing Fact_Energy_Weather (for full refresh or incremental) …")
        # In a production environment with millions of rows, you'd do incremental.
        # For this project, we'll do a robust upsert or direct join.
        
        log.info("  2. Merging Staging Data into FactTable …")
        
        # SQL Transformation logic:
        # - Join load and weather on datetime
        # - Compute flags and temporal features
        # - Compute lags (using window functions)
        
        sql = """
        INSERT INTO fact_energy_weather (
            datetime, load_mw, temp_c, windspeed_kmh, precip_mm,
            hdd_flag, cdd_flag, windchill,
            lag_load_24h, lag_load_168h,
            hour, day_of_week, month, is_holiday
        )
        WITH merged AS (
            SELECT 
                l.datetime,
                l.load_mw,
                w.temp_c,
                w.windspeed_kmh,
                w.precip_mm,
                (w.temp_c < 18) as hdd_flag,
                (w.temp_c > 22) as cdd_flag,
                (w.temp_c * COALESCE(w.windspeed_kmh, 1.0)) as windchill,
                LAG(l.load_mw, 24) OVER (ORDER BY l.datetime) as lag_load_24h,
                LAG(l.load_mw, 168) OVER (ORDER BY l.datetime) as lag_load_168h,
                EXTRACT(HOUR FROM l.datetime)::INT as hour,
                EXTRACT(DOW FROM l.datetime)::INT as day_of_week,
                EXTRACT(MONTH FROM l.datetime)::INT as month
            FROM stg_nsp_load l
            LEFT JOIN stg_weather w ON l.datetime = w.datetime
        )
        SELECT 
            datetime, load_mw, temp_c, windspeed_kmh, precip_mm,
            hdd_flag, cdd_flag, windchill,
            lag_load_24h, lag_load_168h,
            hour, day_of_week, month, FALSE as is_holiday
        FROM merged
        ON CONFLICT (datetime) DO UPDATE SET
            load_mw = EXCLUDED.load_mw,
            temp_c = EXCLUDED.temp_c,
            windspeed_kmh = EXCLUDED.windspeed_kmh,
            precip_mm = EXCLUDED.precip_mm,
            hdd_flag = EXCLUDED.hdd_flag,
            cdd_flag = EXCLUDED.cdd_flag,
            windchill = EXCLUDED.windchill,
            lag_load_24h = EXCLUDED.lag_load_24h,
            lag_load_168h = EXCLUDED.lag_load_168h,
            hour = EXCLUDED.hour,
            day_of_week = EXCLUDED.day_of_week,
            month = EXCLUDED.month;
        """
        
        result = conn.execute(text(sql))
        log.info(f"  ✓ Processed {result.rowcount} rows into fact_energy_weather")

    log.info("✅ Transformation Complete")

if __name__ == "__main__":
    transform()
