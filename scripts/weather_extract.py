"""
weather_extract.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Area Energy Demand Forecasting — Daily Weather Data Extraction
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PURPOSE
    Daily incremental extraction of weather observations from Environment Canada
    for Halifax Stanfield International Airport (Station 50620 / 8202200)

    Designed to run via:
    • APScheduler (from FastAPI backend)
    • Cron job (standalone)
    • Manual execution for backfills

DATA SOURCE
    Environment Canada — MSC Geomet Web Services & Bulk Climate Download
    Station:  Halifax Stanfield Intl (50620 / 8202200)
    URL:      https://climate.weather.gc.ca/climate_data/bulk_data_e.html
    Auth:     None (open data)
    Format:   CSV (hourly observations)
    License:  Open Government License - Canada
    Coverage: Temp (°C), Wind (km/h), Precip (mm), Humidity (%)

USAGE
    # Extract yesterday's weather
    python weather_extract.py

    # Extract specific date range
    python weather_extract.py --start 2026-03-01 --end 2026-03-14

    # Dry run (no database writes)
    python weather_extract.py --dry-run

OUTPUT
    ✓ stg_Weather populated with new hourly weather rows (Source='EnvCanada_Stn50620')
    ✓ ETL_Watermark updated with LastExtracted timestamp
    ✓ Logs written to ../logs/weather_extract.log

NOTES
    - Uses ETL_Watermark to track last successful extraction
    - Handles EC CSV format variations (column name changes across years)
    - Retries on network failures (max 3 attempts)
    - Extracts month-by-month to stay within EC download limits

Author : Dylan Bray · NSCC DBAS 3090 · March 2026
"""

import os
import sys
import logging
import argparse
import time
from pathlib import Path
from datetime import datetime, timedelta
from io import StringIO
import warnings
warnings.filterwarnings("ignore")

from dotenv import load_dotenv
import requests
import pandas as pd
from sqlalchemy import create_engine, text

# Load environment variables from root .env
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

# Database connection
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:HalifaxEnergyETL@localhost:5432/halifaxenergy"
)

# Environment Canada bulk climate download endpoint
EC_BASE_URL = "https://climate.weather.gc.ca/climate_data/bulk_data_e.html"

# Halifax Stanfield Intl — Station IDs
EC_STATION_ID = "50620"      # Climate ID
EC_STATION_NUM = "8202200"   # Station number (used in API)

# Request settings
TIMEOUT = 45
MAX_RETRIES = 3
RETRY_DELAY = 5

# Logging
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "weather_extract.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a"),
    ],
)
log = logging.getLogger("weather_extract")

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_engine():
    """Connect to PostgreSQL."""
    log.info("Connecting to PostgreSQL...")
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        log.info("  ✓ Connected")
        return engine
    except Exception as e:
        log.error(f"  ✗ Database connection failed: {e}")
        sys.exit(1)


def get_last_extracted(engine, source_name="Geomet") -> datetime:
    """Get last extraction timestamp from etl_watermark."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT last_extracted FROM etl_watermark WHERE source_name = :src"),
            {"src": source_name}
        ).fetchone()

        if result:
            dt = result[0]
            if dt and hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return dt
        else:
            # Default to yesterday if no watermark exists
            return datetime.now() - timedelta(days=1)


def update_watermark(engine, source_name: str, timestamp: datetime, rows_inserted: int):
    """Update etl_watermark with new extraction timestamp."""
    # Ensure timestamp is naive
    if timestamp and hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
        timestamp = timestamp.replace(tzinfo=None)

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO etl_watermark (source_name, last_extracted, rows_inserted, status, updated_at)
            VALUES (:src, :ts, :rows, 'OK', NOW())
            ON CONFLICT (source_name) DO UPDATE SET
                last_extracted = EXCLUDED.last_extracted,
                rows_inserted = EXCLUDED.rows_inserted,
                status = 'OK',
                updated_at = NOW();
        """), {"src": source_name, "ts": timestamp, "rows": rows_inserted})
    log.info(f"  ✓ Watermark updated: {source_name} → {timestamp}")


def insert_weather_data(engine, df: pd.DataFrame, source: str = "EnvCanada_Stn50620") -> int:
    """
    Insert weather data into stg_weather, skipping duplicates.
    Returns count of new rows inserted.
    """
    if df.empty:
        log.warning("  No data to insert (empty DataFrame)")
        return 0

    df = df.copy()
    df["source"] = source
    df["inserted_at"] = datetime.now()

    # Validate required columns
    if "DateTime" not in df.columns:
        log.error(f"  ✗ Missing DateTime column. Got: {list(df.columns)}")
        return 0

    # Clean and validate
    df["datetime"] = pd.to_datetime(df["DateTime"], errors="coerce")
    df = df.dropna(subset=["datetime"])

    # Map columns to lowercase for Postgres
    col_map = {
        "Temp_C": "temp_c",
        "WindSpeed_kmh": "windspeed_kmh",
        "Precip_mm": "precip_mm",
        "Humidity_Pct": "humidity_pct"
    }
    
    # Ensure weather columns exist (fill with None if missing)
    for orig, target in col_map.items():
        if orig in df.columns:
            df[target] = pd.to_numeric(df[orig], errors="coerce")
        else:
            df[target] = None

    if df.empty:
        log.warning("  No valid rows after cleaning")
        return 0

    # Get row count before insert
    before = _count_rows(engine)

    # Temp table + on conflict pattern
    df[["datetime", "temp_c", "windspeed_kmh", "precip_mm", "humidity_pct", "source", "inserted_at"]].to_sql(
        "__tmp_weather", engine, if_exists="replace", index=False
    )

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO stg_weather
                (datetime, temp_c, windspeed_kmh, precip_mm, humidity_pct, source, inserted_at)
            SELECT t.datetime, t.temp_c, t.windspeed_kmh, t.precip_mm, t.humidity_pct,
                   t.source, t.inserted_at
            FROM   __tmp_weather t
            ON CONFLICT (datetime) DO NOTHING;
        """))
        conn.execute(text("DROP TABLE IF EXISTS __tmp_weather"))

    after = _count_rows(engine)
    inserted = after - before

    log.info(f"  ✓ Inserted {inserted:,} new rows (skipped {len(df) - inserted:,} duplicates)")
    return inserted


def _count_rows(engine) -> int:
    """Count total rows in stg_Weather."""
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM stg_Weather")).scalar()


# ─────────────────────────────────────────────────────────────────────────────
# ENVIRONMENT CANADA EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def fetch_ec_weather_month(year: int, month: int) -> pd.DataFrame:
    """
    Fetch one month of hourly weather data from Environment Canada.

    Args:
        year: Year (e.g., 2026)
        month: Month (1-12)

    Returns:
        DataFrame with columns: DateTime, Temp_C, WindSpeed_kmh, Precip_mm, Humidity_Pct
    """
    log.info(f"  Fetching EC weather: {year}-{month:02d}")

    params = {
        "format":    "csv",
        "stationID": EC_STATION_NUM,
        "Year":      year,
        "Month":     month,
        "Day":       14,        # Dummy day (EC ignores for hourly data)
        "timeframe": 1,         # 1 = hourly
        "submit":    "Download+Data",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info(f"    Attempt {attempt}/{MAX_RETRIES}...")
            response = requests.get(EC_BASE_URL, params=params, timeout=TIMEOUT)
            response.raise_for_status()

            content = response.content.decode("latin-1")
            lines = content.splitlines()

            # EC CSVs have metadata header — find data start
            data_start = 0
            for i, line in enumerate(lines):
                if "Date/Time" in line or (i > 0 and lines[i-1].strip() == "" and "," in line):
                    data_start = i
                    break

            # Parse CSV
            df_raw = pd.read_csv(
                StringIO("\n".join(lines[data_start:])),
                encoding="latin-1",
                low_memory=False
            )
            df_raw.columns = [str(c).strip() for c in df_raw.columns]

            # Build DateTime from available columns
            dt_col = None
            for col in df_raw.columns:
                if "Date/Time" in col or col.startswith("Date"):
                    dt_col = col
                    break

            if dt_col is None:
                # Try building from Year/Month/Day/Hour columns
                time_cols_candidates = [
                    ["Year", "Month", "Day", "Time"],
                    ["Year", "Month", "Day", "Hour (LST)"],
                    ["Year", "Month", "Day", "Hour"]
                ]
                for cols in time_cols_candidates:
                    if all(c in df_raw.columns for c in cols):
                        df_raw["_dt"] = pd.to_datetime(
                            df_raw[cols[0]].astype(str) + "-" +
                            df_raw[cols[1]].astype(str).str.zfill(2) + "-" +
                            df_raw[cols[2]].astype(str).str.zfill(2) + " " +
                            df_raw[cols[3]].astype(str).str.split(":").str[0].str.zfill(2) + ":00",
                            errors="coerce"
                        )
                        dt_col = "_dt"
                        break

            if dt_col is None:
                log.error(f"    ✗ No datetime column found. Columns: {list(df_raw.columns)[:10]}")
                return pd.DataFrame()

            # Map EC column names to our schema
            col_map = {
                "Temp (°C)":           "Temp_C",
                "Temp (C)":            "Temp_C",
                "Wind Spd (km/h)":     "WindSpeed_kmh",
                "Wind Speed (km/h)":   "WindSpeed_kmh",
                "Precip. Amount (mm)": "Precip_mm",
                "Total Precip (mm)":   "Precip_mm",
                "Rel Hum (%)":         "Humidity_Pct",
                "Relative Humidity (%)": "Humidity_Pct",
            }

            df = pd.DataFrame({"DateTime": pd.to_datetime(df_raw[dt_col], errors="coerce")})

            for ec_col, our_col in col_map.items():
                matched = next((c for c in df_raw.columns if ec_col in c), None)
                if matched:
                    df[our_col] = pd.to_numeric(df_raw[matched], errors="coerce")

            df = df.dropna(subset=["DateTime"])

            log.info(f"    ✓ Retrieved {len(df):,} rows")
            return df

        except requests.exceptions.RequestException as e:
            log.warning(f"    ⚠ Request failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
        except Exception as e:
            log.error(f"    ✗ Unexpected error: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)

    log.error(f"    ✗ All {MAX_RETRIES} attempts failed")
    return pd.DataFrame()


def fetch_ec_weather(start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """
    Fetch weather data for a date range (month-by-month).

    Args:
        start_dt: Start datetime
        end_dt: End datetime

    Returns:
        Combined DataFrame with all months
    """
    log.info(f"Fetching EC weather: {start_dt.date()} → {end_dt.date()}")

    frames = []
    current = start_dt.replace(day=1)

    while current <= end_dt:
        df_month = fetch_ec_weather_month(current.year, current.month)

        if not df_month.empty:
            # Filter to requested range
            month_end = (current + timedelta(days=32)).replace(day=1) - timedelta(hours=1)
            df_month = df_month[
                (df_month["DateTime"] >= start_dt) &
                (df_month["DateTime"] <= min(month_end, end_dt))
            ]
            frames.append(df_month)

        # Move to next month
        current = (current + timedelta(days=32)).replace(day=1)
        time.sleep(1)  # Be polite to EC servers

    if not frames:
        log.warning("  No data retrieved")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates("DateTime").sort_values("DateTime")

    log.info(f"  ✓ Total weather rows: {len(combined):,}")
    return combined


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract weather data from Environment Canada (daily incremental)"
    )
    parser.add_argument(
        "--start",
        type=str,
        help="Start date (YYYY-MM-DD). Default: last watermark or yesterday"
    )
    parser.add_argument(
        "--end",
        type=str,
        help="End date (YYYY-MM-DD). Default: yesterday"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch data but don't write to database"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    log.info("=" * 70)
    log.info("  Environment Canada Weather Extraction — weather_extract.py")
    log.info("=" * 70)

    # Connect to database
    engine = get_engine()

    # Determine date range
    if args.start:
        start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    else:
        # Use last watermark + 1 hour
        last_extracted = get_last_extracted(engine, source_name="Geomet")
        start_dt = last_extracted + timedelta(hours=1)

    if args.end:
        end_dt = datetime.strptime(args.end, "%Y-%m-%d").replace(hour=23, minute=59)
    else:
        # Default: up to yesterday 23:59
        end_dt = (datetime.now() - timedelta(days=1)).replace(hour=23, minute=59, second=59)

    log.info(f"Date range: {start_dt} → {end_dt}")

    if start_dt > end_dt:
        log.warning("  Start date is after end date — nothing to extract")
        log.info("  (This is normal if extraction is already up-to-date)")
        return

    # Fetch data
    df = fetch_ec_weather(start_dt, end_dt)

    if df.empty:
        log.warning("  No data retrieved")
        return

    # Insert into database
    if args.dry_run:
        log.info(f"  DRY RUN: Would insert {len(df):,} rows")
        log.info(f"  Sample data:\n{df.head()}")
    else:
        inserted = insert_weather_data(engine, df, source="EnvCanada_Stn50620")

        if inserted > 0:
            # Update watermark to the latest timestamp
            max_dt = df["DateTime"].max()
            update_watermark(engine, "Geomet", max_dt, inserted)

    log.info("=" * 70)
    log.info("  ✅ Extraction complete")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
