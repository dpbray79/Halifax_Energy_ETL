"""
nsp_extract.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Area Energy Demand Forecasting — Daily CCEI HFED Load Data Extraction
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PURPOSE
    Daily incremental extraction of Nova Scotia load data from CCEI HFED
    (Canadian Centre for Energy Information - High Frequency Electricity Data)

    Designed to run via:
    • APScheduler (from FastAPI backend)
    • Cron job (standalone)
    • Manual execution for backfills

DATA SOURCE
    CCEI HFED API (via OASIS AWS endpoint)
    URL:      https://resourcesprd-nspower.aws.silvertech.net/oasis/current_report.shtml
    Auth:     None
    Format:   HTML table → parsed to DataFrame
    Coverage: Real-time NS grid demand (hourly intervals)

USAGE
    # Extract yesterday's data
    python nsp_extract.py

    # Extract specific date range
    python nsp_extract.py --start 2026-03-01 --end 2026-03-14

    # Dry run (no database writes)
    python nsp_extract.py --dry-run

OUTPUT
    ✓ stg_NSP_Load populated with new hourly load rows (Source='CCEI_HFED')
    ✓ ETL_Watermark updated with LastExtracted timestamp
    ✓ Logs written to ../logs/nsp_extract.log

NOTES
    - Uses ETL_Watermark to track last successful extraction
    - Skips duplicate rows based on DateTime (INSERT WHERE NOT EXISTS)
    - Handles OASIS report format variations gracefully
    - Retries on network failures (max 3 attempts)

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

import requests
import pandas as pd
from sqlalchemy import create_engine, text

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

# Database connection (override with env var DATABASE_URL)
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/halifaxenergy"
)

# CCEI HFED endpoint (OASIS current report)
CCEI_OASIS_URL = "https://resourcesprd-nspower.aws.silvertech.net/oasis/current_report.shtml"

# Request settings
TIMEOUT = 45
MAX_RETRIES = 3
RETRY_DELAY = 5

# Logging
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "nsp_extract.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a"),
    ],
)
log = logging.getLogger("nsp_extract")

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_engine():
    """Connect to PostgreSQL (Supabase)."""
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


def get_last_extracted(engine, source_name="CCEI_HFED") -> datetime:
    """Get last extraction timestamp from ETL_Watermark."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT LastExtracted FROM ETL_Watermark WHERE SourceName = :src"),
            {"src": source_name}
        ).fetchone()

        if result:
            return result[0]
        else:
            # If watermark doesn't exist, default to yesterday
            return datetime.now() - timedelta(days=1)


def update_watermark(engine, source_name: str, timestamp: datetime, rows_inserted: int):
    """Update ETL_Watermark with new extraction timestamp (PostgreSQL upsert)."""
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO etl_watermark (sourcename, lastextracted, rowsinserted, status, updatedat)
            VALUES (:src, :ts, :rows, 'OK', NOW())
            ON CONFLICT (sourcename) DO UPDATE
                SET lastextracted = EXCLUDED.lastextracted,
                    rowsinserted  = EXCLUDED.rowsinserted,
                    status        = 'OK',
                    updatedat     = NOW();
        """), {"src": source_name, "ts": timestamp, "rows": rows_inserted})
    log.info(f"  ✓ Watermark updated: {source_name} → {timestamp}")


def insert_load_data(engine, df: pd.DataFrame, source: str = "CCEI_HFED") -> int:
    """
    Insert load data into stg_nsp_load, skipping duplicates.
    Uses PostgreSQL ON CONFLICT DO NOTHING for idempotency.
    Returns count of new rows inserted.
    """
    if df.empty:
        log.warning("  No data to insert (empty DataFrame)")
        return 0

    df = df.copy()
    df["Source"] = source
    df["InsertedAt"] = datetime.now()
    df["IsProcessed"] = 0

    # Validate required columns
    if not {"DateTime", "Load_MW"}.issubset(df.columns):
        log.error(f"  ✗ Missing required columns. Got: {list(df.columns)}")
        return 0

    # Clean and validate data
    df["DateTime"] = pd.to_datetime(df["DateTime"], errors="coerce")
    df = df.dropna(subset=["DateTime"])

    df["Load_MW"] = pd.to_numeric(df["Load_MW"], errors="coerce")
    df = df.dropna(subset=["Load_MW"])

    # Filter reasonable NS load range (300-3000 MW)
    df = df[(df["Load_MW"] >= 300) & (df["Load_MW"] <= 3000)]

    if df.empty:
        log.warning("  No valid rows after cleaning")
        return 0

    # Get row count before insert
    before = _count_rows(engine)

    # PostgreSQL ON CONFLICT DO NOTHING (requires unique constraint on datetime)
    rows = df[["DateTime", "Load_MW", "Source", "InsertedAt", "IsProcessed"]].to_dict(orient="records")
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO stg_nsp_load (datetime, load_mw, source, insertedat, isprocessed)
                VALUES (:DateTime, :Load_MW, :Source, :InsertedAt, :IsProcessed)
                ON CONFLICT (datetime) DO NOTHING
            """),
            rows
        )

    after = _count_rows(engine)
    inserted = after - before

    log.info(f"  ✓ Inserted {inserted:,} new rows (skipped {len(df) - inserted:,} duplicates)")
    return inserted


def _count_rows(engine) -> int:
    """Count total rows in stg_nsp_load."""
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM stg_nsp_load")).scalar()


# ─────────────────────────────────────────────────────────────────────────────
# CCEI HFED EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def fetch_ccei_hfed(start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """
    Fetch NS load data from CCEI HFED (via OASIS endpoint).

    Args:
        start_dt: Start datetime (inclusive)
        end_dt: End datetime (inclusive)

    Returns:
        DataFrame with columns: DateTime, Load_MW
    """
    log.info(f"Fetching CCEI HFED data: {start_dt.date()} → {end_dt.date()}")

    params = {
        "start": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "end":   end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info(f"  Attempt {attempt}/{MAX_RETRIES}...")
            response = requests.get(CCEI_OASIS_URL, params=params, timeout=TIMEOUT)
            response.raise_for_status()

            # Parse HTML tables
            tables = pd.read_html(StringIO(response.text))

            if not tables:
                log.warning(f"  ⚠ No tables found in OASIS response")
                return pd.DataFrame()

            # OASIS report contains the load data in the first table
            df_raw = tables[0]

            # Normalize column names
            df_raw.columns = [str(c).strip() for c in df_raw.columns]

            # Find datetime column (flexible matching)
            dt_col = None
            for col in df_raw.columns:
                if any(keyword in col.lower() for keyword in ["date", "time", "hour", "datetime"]):
                    dt_col = col
                    break

            # Find load/demand column (flexible matching)
            load_col = None
            for col in df_raw.columns:
                if any(keyword in col.lower() for keyword in ["load", "mw", "demand", "net", "total"]):
                    load_col = col
                    break

            if not dt_col or not load_col:
                log.error(f"  ✗ Could not identify columns. Available: {list(df_raw.columns)}")
                return pd.DataFrame()

            log.info(f"  ✓ Using columns: DateTime='{dt_col}', Load_MW='{load_col}'")

            # Build result DataFrame
            df = pd.DataFrame({
                "DateTime": pd.to_datetime(df_raw[dt_col], errors="coerce"),
                "Load_MW":  pd.to_numeric(df_raw[load_col], errors="coerce"),
            })

            # Filter to requested date range
            df = df.dropna()
            df = df[(df["DateTime"] >= start_dt) & (df["DateTime"] <= end_dt)]

            log.info(f"  ✓ Fetched {len(df):,} rows")
            return df

        except requests.exceptions.RequestException as e:
            log.warning(f"  ⚠ Request failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
        except Exception as e:
            log.error(f"  ✗ Unexpected error: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)

    log.error(f"  ✗ All {MAX_RETRIES} attempts failed")
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract NS load data from CCEI HFED (daily incremental)"
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
    log.info("  CCEI HFED Load Data Extraction — nsp_extract.py")
    log.info("=" * 70)

    # Connect to database
    engine = get_engine()

    # Determine date range
    if args.start:
        start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    else:
        # Use last watermark + 1 hour
        last_extracted = get_last_extracted(engine)
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
    df = fetch_ccei_hfed(start_dt, end_dt)

    if df.empty:
        log.warning("  No data retrieved")
        return

    # Insert into database
    if args.dry_run:
        log.info(f"  DRY RUN: Would insert {len(df):,} rows")
        log.info(f"  Sample data:\n{df.head()}")
    else:
        inserted = insert_load_data(engine, df, source="CCEI_HFED")

        if inserted > 0:
            # Update watermark to the latest timestamp in the data
            max_dt = df["DateTime"].max()
            update_watermark(engine, "CCEI_HFED", max_dt, inserted)

    log.info("=" * 70)
    log.info("  ✅ Extraction complete")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
