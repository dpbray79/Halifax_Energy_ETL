# Halifax Energy Forecasting — Quick Start Guide

This guide will get your system up and running in under 10 minutes.

## Prerequisites Checklist

- [ ] **Docker Desktop** installed and running
- [ ] **Python 3.11+** installed
- [ ] **R 4.x+** installed (for model training)
- [ ] **Node.js 18+** and npm installed (for React dashboard)
- [ ] **ODBC Driver 17 for SQL Server** installed

### Install ODBC Driver (if needed)

**macOS:**
```bash
brew install msodbcsql17 mssql-tools
```

**Ubuntu/Debian:**
```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | \
  sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17 mssql-tools
```

**Windows:**
Download from: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

---

## Step 1: Database Setup (5 minutes)

### 1.1 Start SQL Server

```bash
cd ~/Desktop/HalifaxEnergy_ETL

# Make init script executable
chmod +x init_database.sh

# Start SQL Server and create database
./init_database.sh
```

**Expected output:**
```
✓ Docker is running
✓ SQL Server is ready!
✓ Database created (or already exists)
✓ Table creation script executed
```

### 1.2 Verify Database

```bash
docker-compose exec sqlserver /opt/mssql-tools/bin/sqlcmd \
  -S localhost -U sa -P 'Halifax@Energy2026!' \
  -d HalifaxEnergyProject \
  -Q "SELECT name FROM sys.tables ORDER BY name"
```

**Expected:** You should see tables: `Dim_Date`, `ETL_Watermark`, `Fact_Energy_Weather`, `Model_Predictions`, `stg_NSP_Load`, `stg_Weather`

---

## Step 2: Seed Historical Data (10-15 minutes)

### 2.1 Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2.2 Run Historical Data Seed

```bash
# Seed 2023-2026 data (can take 10-15 minutes)
python scripts/seed_historical_data.py --start 2023-01-01
```

**Expected output:**
```
  ✓ Connected to SQL Server
  ✓ Inserted X,XXX new rows from Electricity Maps
  ✓ Inserted X,XXX new rows from CCEI HFED
  ✓ Total EC weather rows inserted: X,XXX
  Coverage: XX.X%
```

**Note:** If you don't have Electricity Maps CSV files, the script will skip that source and use CCEI HFED only. To download Electricity Maps data:

1. Go to: https://app.electricitymaps.com/datasets/CA-NS
2. Create free account
3. Download CA-NS hourly CSV for 2023, 2024
4. Place in `./data/electricitymaps/`
5. Re-run seed script

---

## Step 3: Install R Dependencies (5 minutes)

### 3.1 Install R Packages

```R
# Open R console
R

# Install required packages
install.packages(c(
  "tidyverse",
  "tidymodels",
  "xgboost",
  "DBI",
  "odbc",
  "lubridate",
  "glue",
  "here"
))

# Quit R
quit()
```

### 3.2 Test R Model (Optional - takes 5-10 minutes)

```bash
# Run model training (optional - will run automatically via API)
Rscript model/HalifaxEnergy_Model.R
```

---

## Step 4: Start FastAPI Backend (2 minutes)

### 4.1 Install API Dependencies

```bash
cd api
pip install -r requirements.txt
```

### 4.2 Start API Server

```bash
# Development mode (auto-reload)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Database connection OK
INFO:     APScheduler started
```

### 4.3 Verify API

Open browser: http://localhost:8000/docs

You should see the FastAPI interactive documentation (Swagger UI).

**Test endpoints:**
- GET `/health` — Should return `{"status": "ok", "database": "ok"}`
- GET `/api/actuals` — Should return actual load data
- GET `/api/zones` — Should return GeoJSON with Halifax zones

---

## Step 5: Start React Dashboard (2 minutes)

### 5.1 Open New Terminal (keep API running)

```bash
cd ~/Desktop/HalifaxEnergy_ETL/dashboard
```

### 5.2 Install Dependencies

```bash
npm install
```

**Note:** This may take 2-3 minutes on first run.

### 5.3 Start Development Server

```bash
npm run dev
```

**Expected output:**
```
  VITE v5.x.x  ready in XXX ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### 5.4 Open Dashboard

Open browser: **http://localhost:5173**

You should see the Halifax Energy Forecasting Dashboard!

---

## Step 6: Verify Everything Works

### 6.1 Dashboard Page
- You should see the Halifax map with 5 zones
- Select different horizons (H1, H2, H3) from dropdown
- Toggle "Show Residuals" checkbox

### 6.2 Models Page
- Click "Models" in sidebar
- You should see model artifacts (if you ran training)
- Try clicking "Run Training" to trigger model

### 6.3 Data Page
- Click "Data" in sidebar
- You should see latest reading, 30-day summary, and recent data table

---

## Troubleshooting

### Database Connection Issues

**Problem:** API can't connect to database
```
Database connection failed: Login timeout expired
```

**Solution:**
```bash
# Check if SQL Server is running
docker ps

# If not running, start it
docker-compose up -d sqlserver

# Check logs
docker-compose logs sqlserver
```

---

### API Not Responding

**Problem:** Dashboard can't reach API
```
Failed to load zones: Network Error
```

**Solution:**
```bash
# Check API is running
curl http://localhost:8000/health

# If not running, start it
cd api
uvicorn main:app --reload
```

---

### Missing Data

**Problem:** Charts show "No data available"

**Solution:**
```bash
# Check if data was seeded
python -c "from api.database import engine; from sqlalchemy import text; \
  print(engine.connect().execute(text('SELECT COUNT(*) FROM stg_NSP_Load')).scalar())"

# If 0, re-run seed script
python scripts/seed_historical_data.py --start 2023-01-01
```

---

### R Model Issues

**Problem:** Model training fails
```
Error: package 'xgboost' is not available
```

**Solution:**
```R
# Re-install packages in R
install.packages("xgboost", dependencies = TRUE)
```

---

## Daily Operation

Once set up, the system runs automatically:

1. **6:00 AM** — CCEI HFED data extraction (APScheduler)
2. **6:30 AM** — Weather data extraction (APScheduler)
3. **4:00 AM** — Model retraining (APScheduler)

You can also trigger manual operations:
- **Extract data:** `python scripts/nsp_extract.py`
- **Train model:** `Rscript model/HalifaxEnergy_Model.R`
- **Trigger via API:** POST to `/api/run-model` from Models page

---

## Next Steps

1. **Customize GeoJSON:** Replace placeholder Halifax zones with actual boundaries
   - Edit: `data/geojson/halifax_zones.geojson`

2. **Add Authentication:** Secure the API with JWT or API keys

3. **Deploy to Production:**
   - Use PM2 or systemd for API
   - Build React for production: `npm run build`
   - Use Nginx as reverse proxy

4. **Set up Monitoring:**
   - Add logging aggregation (ELK stack)
   - Set up alerts for model performance degradation

---

## Useful Commands

### Docker
```bash
# Stop SQL Server
docker-compose stop sqlserver

# Restart SQL Server
docker-compose restart sqlserver

# View logs
docker-compose logs -f sqlserver

# Remove all containers (WARNING: deletes data)
docker-compose down -v
```

### Database
```bash
# Connect to SQL Server
docker-compose exec sqlserver /opt/mssql-tools/bin/sqlcmd \
  -S localhost -U sa -P 'Halifax@Energy2026!'

# Backup database
docker-compose exec sqlserver /opt/mssql-tools/bin/sqlcmd \
  -S localhost -U sa -P 'Halifax@Energy2026!' \
  -Q "BACKUP DATABASE HalifaxEnergyProject TO DISK='/backups/HalifaxEnergy.bak'"
```

### API
```bash
# Check scheduled jobs
curl http://localhost:8000/api/scheduler/jobs

# Trigger model run
curl -X POST http://localhost:8000/api/run-model \
  -H "Content-Type: application/json" \
  -d '{"horizon": "H1"}'
```

---

## Support

For issues or questions:
- Check logs: `./logs/halifaxenergy.log`
- Review API docs: http://localhost:8000/docs
- Check database tables with Azure Data Studio or SQL Server Management Studio

---

**Author:** Dylan Bray
**Course:** NSCC DBAS 3090
**Date:** March 2026

**Happy Forecasting!** ⚡📊
