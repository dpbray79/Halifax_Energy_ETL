"""
seed_synthetic_data.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Area Energy Demand Forecasting — Synthetic Data Generation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PURPOSE
    Populates stg_nsp_load and stg_weather with realistic, synthesized data
    to allow the XGBoost models to train and the dashboard to show charts.
    Useful for demonstration when Electricity Maps CSVs are unavailable.

    Generates:
    - 90 days of hourly data (~2,160 rows)
    - Realistic load patterns (daily peaks, weekend dips)
    - Realistic weather patterns (seasonal temp, wind speed)

USAGE
    python scripts/seed_synthetic_data.py

Author : Dylan Bray · March 2026
"""

import os, sys, logging, random, math
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import create_engine, text

# Load environment variables
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("synthetic_seed")

DB_URL = os.getenv("DATABASE_URL")

def generate_synthetic_data():
    if not DB_URL:
        log.error("DATABASE_URL not set")
        return

    log.info("Generating Synthetic Halifax Energy Data …")
    engine = create_engine(DB_URL)
    
    end_date = datetime.now().replace(minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=90)
    
    dates = pd.date_range(start=start_date, end=end_date, freq="h")
    
    load_rows = []
    weather_rows = []
    
    for dt in dates:
        # 1. Base Load: ~1000 MW
        # Diurnal pattern (peak at 8am and 6pm)
        hour = dt.hour
        hour_factor = 1.0 + 0.2 * math.sin((hour - 4) * math.pi / 10) # rough peak
        
        # Day of week pattern (lower on weekends)
        dow_factor = 0.9 if dt.weekday() >= 5 else 1.0
        
        # Random noise
        noise = random.uniform(0.95, 1.05)
        
        load = 1000 * hour_factor * dow_factor * noise
        
        load_rows.append({
            "datetime": dt,
            "load_mw": round(load, 2),
            "source": "Synthetic_Generator_v1",
            "is_processed": False,
            "inserted_at": datetime.now()
        })
        
        # 2. Weather: ~5°C average for March
        temp = 5 + 5 * math.sin((hour - 12) * math.pi / 12) + random.uniform(-2, 2)
        wind = random.uniform(5, 30)
        precip = 0 if random.random() > 0.1 else random.uniform(0, 10)
        
        weather_rows.append({
            "datetime": dt,
            "temp_c": round(temp, 1),
            "windspeed_kmh": round(wind, 1),
            "precip_mm": round(precip, 1),
            "humidity_pct": random.uniform(40, 90),
            "source": "Synthetic_Generator_v1",
            "inserted_at": datetime.now()
        })

    # Upload to DB
    log.info(f"Uploading {len(load_rows)} load rows …")
    pd.DataFrame(load_rows).to_sql("stg_nsp_load", engine, if_exists="append", index=False)
    
    log.info(f"Uploading {len(weather_rows)} weather rows …")
    pd.DataFrame(weather_rows).to_sql("stg_weather", engine, if_exists="append", index=False)

    log.info("✅ Synthetic Seeding Complete")
    log.info("Now run: python scripts/transform_gold.py")

if __name__ == "__main__":
    generate_synthetic_data()
