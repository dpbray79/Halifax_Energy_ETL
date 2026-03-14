"""
download_electricitymaps.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Electricity Maps CA-NS — Free Tier Dataset Downloader
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHAT THIS DOES
    Attempts to download the free CA-NS hourly CSVs from Electricity Maps
    for 2021–2024 using their public dataset API endpoint.

    The free tier at app.electricitymaps.com/datasets/CA-NS provides:
    ✓ 2021 hourly CSV (~8,760 rows)
    ✓ 2022 hourly CSV (~8,760 rows)
    ✓ 2023 hourly CSV (~8,760 rows)
    ✓ 2024 hourly CSV (~8,784 rows — leap year)

    License: ODbL — free to use, attribute the source.

HOW TO USE
    Option 1 — Manual (most reliable):
        1. Go to https://app.electricitymaps.com/datasets/CA-NS
        2. Create a free account (5 free datasets)
        3. Select Zone = CA-NS (Nova Scotia)
        4. Select Year = 2023, Granularity = Hourly → Download CSV
        5. Repeat for 2024, 2025 (if available)
        6. Save files to ./data/electricitymaps/
        7. Then run: python seed_historical_data.py

    Option 2 — API (requires free account token):
        Set env var: ELEC_MAPS_TOKEN=your_token_here
        Then run:    python download_electricitymaps.py

Author: Dylan Bray · NSCC DBAS 3090 · March 2026
"""

import os, sys, time
from pathlib import Path
from datetime import datetime
import requests

OUT_DIR = Path("./data/electricitymaps")
TOKEN   = os.getenv("ELEC_MAPS_TOKEN", "")

# Electricity Maps public dataset API
# Documented at: https://static.electricitymaps.com/api/docs/index.html
API_BASE = "https://api.electricitymap.org/v3"

ZONE   = "CA-NS"
YEARS  = [2021, 2022, 2023, 2024]   # free tier coverage


def download_with_token(year: int) -> bool:
    """Download via Electricity Maps API using a free account token."""
    url = f"{API_BASE}/carbon-intensity/history"  # or /power-breakdown
    headers = {"auth-token": TOKEN}

    # Use the dataset download endpoint
    dataset_url = f"https://app.electricitymaps.com/api/datasets/{ZONE}/hourly/{year}"
    print(f"  Trying API download for {year} …")
    try:
        r = requests.get(dataset_url, headers=headers, timeout=60)
        if r.status_code == 401:
            print("  → 401 Unauthorized: token required or invalid")
            return False
        if r.status_code == 403:
            print("  → 403 Forbidden: free tier limit reached (5 datasets)")
            return False
        r.raise_for_status()
        out = OUT_DIR / f"CA-NS_hourly_{year}.csv"
        out.write_bytes(r.content)
        print(f"  ✓ Saved {out.name} ({len(r.content):,} bytes)")
        return True
    except Exception as e:
        print(f"  ⚠ {e}")
        return False


def print_manual_instructions():
    print("""
╔══════════════════════════════════════════════════════════════════════════╗
║          Electricity Maps — Manual Download Instructions                ║
╚══════════════════════════════════════════════════════════════════════════╝

1. Open:  https://app.electricitymaps.com/datasets/CA-NS

2. Create a FREE account (email only — no credit card)
   You get 5 free historical dataset downloads.

3. On the CA-NS page:
   • Zone:        CA-NS (Nova Scotia)
   • Granularity: Hourly
   • Year:        2023  → click Download CSV → save as CA-NS_hourly_2023.csv
   • Year:        2024  → click Download CSV → save as CA-NS_hourly_2024.csv
   • Year:        2025  → if available on free tier, download it too

4. Place all CSV files in:
   {out_dir}

5. Run the seed script:
   python seed_historical_data.py --start 2023-01-01

CSV columns you'll see:
   datetime              (UTC — script converts to Atlantic time)
   consumption           (MW — total NS grid consumption)  ← this is Load_MW
   production            (MW — total generation)
   carbon_intensity      (gCO2eq/kWh)
   carbon_free_percentage(%)

License: Open Data Commons ODbL
Attribution: "Electricity Maps, CA-NS Hourly Data, {YEAR}"
""".format(out_dir=OUT_DIR.resolve()))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {OUT_DIR.resolve()}")
    print()

    if not TOKEN:
        print("No ELEC_MAPS_TOKEN environment variable set.")
        print("Showing manual download instructions instead.\n")
        print_manual_instructions()
        return

    print(f"Token found — attempting API downloads for zone {ZONE}")
    print()
    success = 0
    for year in YEARS:
        if download_with_token(year):
            success += 1
        time.sleep(1)

    print(f"\n{success}/{len(YEARS)} years downloaded via API.")
    if success < len(YEARS):
        print_manual_instructions()


if __name__ == "__main__":
    main()
