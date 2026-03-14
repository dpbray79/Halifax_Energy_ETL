# Halifax Area Energy Demand Forecasting

Live web dashboard showing XGBoost energy demand predictions on a map of Halifax, with model comparison (H1/H2/H3 horizons) and real-time CCEI energy data integration.

**Author:** Dylan Bray
**Institution:** NSCC DBAS 3090
**Date:** March 2026

## 📋 Project Overview

This system provides:
- **Live Dashboard:** Interactive map of Halifax showing predicted vs actual energy demand by zone
- **ML Models:** XGBoost regression with three forecast horizons (H1: 24h, H2: 48h, H3: 7d)
- **Real-time Data:** Daily CCEI HFED load data and Environment Canada weather integration
- **Historical Analysis:** 2023-2026 historical training data from Electricity Maps, CCEI, NB Power, and Environment Canada

## 🏗️ Architecture

```
┌─────────────────┐
│  React Frontend │ (Leaflet map, Recharts, WebSocket)
│  (Port 5173)    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  FastAPI Backend│ (REST + WebSocket, APScheduler)
│  (Port 8000)    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐        ┌──────────────┐
│  SQL Server 2022│ ←────→ │  R XGBoost   │
│  (Docker 1433)  │        │  Model       │
└─────────────────┘        └──────────────┘
         │
         ↓
┌─────────────────────────────────────┐
│  External Data Sources:             │
│  • CCEI HFED (NS load)              │
│  • Environment Canada (weather)     │
│  • Electricity Maps (historical)    │
│  • NB Power Archive (validation)    │
└─────────────────────────────────────┘
```

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Database** | SQL Server 2022 (Docker, linux/amd64 for Apple Silicon) |
| **Backend** | FastAPI, Python 3.11+, SQLAlchemy, APScheduler |
| **Frontend** | React, Vite, Leaflet, react-leaflet, Recharts, React Router |
| **ML Model** | R, XGBoost, tidymodels |
| **ETL** | Python (pandas, requests), SSIS (optional) |

## 📊 Database Schema

### Staging Tables
- `stg_NSP_Load` — Hourly load data from all sources
- `stg_Weather` — Hourly weather observations (Temp, Wind, Precip, Humidity)
- `ETL_Watermark` — Tracks last extraction timestamp per source

### Gold Tables
- `Fact_Energy_Weather` — Merged hourly energy + weather with engineered features
- `Dim_Date` — Date dimension (hour, day, week, holidays, season)
- `Model_Predictions` — XGBoost predictions with RMSE, SI%, horizon metadata

### Geo Tables (Future)
- `Geo_LandUse` — Halifax land use classification
- `Geo_EnergyByZone` — Predicted/actual load per geographic zone

## 🚀 Quick Start

### 1. Prerequisites

- **Docker Desktop** (for SQL Server)
- **Python 3.11+** with pip
- **R 4.x+** with XGBoost package
- **Node.js 18+** and npm (for React dashboard)
- **ODBC Driver 17 for SQL Server**

### 2. Clone and Setup

```bash
cd ~/Desktop/HalifaxEnergy_ETL

# Copy environment template
cp .env.example .env

# Edit .env with your configuration (SA password, API keys, etc.)
nano .env
```

### 3. Start Database

```bash
# Make init script executable
chmod +x init_database.sh

# Start SQL Server and create database
./init_database.sh
```

This will:
- Start SQL Server 2022 in Docker (port 1433)
- Create `HalifaxEnergyProject` database
- Run `sql/create_seed_tables.sql` to create all tables

### 4. Seed Historical Data

```bash
# Install Python dependencies
pip install -r requirements.txt

# (Optional) Download Electricity Maps CSVs manually
# Place in ./data/electricitymaps/
# See: https://app.electricitymaps.com/datasets/CA-NS

# Run seed script (2023-present)
python seed_historical_data.py --start 2023-01-01
```

### 5. Start Backend API

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API will be available at: http://localhost:8000
API docs: http://localhost:8000/docs

### 6. Start Frontend Dashboard

```bash
cd dashboard
npm install
npm run dev
```

Dashboard will be available at: http://localhost:5173

## 📁 Project Structure

```
HalifaxEnergy_ETL/
├── docker-compose.yml          # SQL Server container
├── .env                        # Environment configuration (DO NOT COMMIT)
├── .env.example                # Template for .env
├── init_database.sh            # Database initialization script
├── README.md                   # This file
│
├── sql/
│   └── create_seed_tables.sql  # Complete database schema
│
├── scripts/
│   ├── seed_historical_data.py      # Historical data seeding (2023-2026)
│   ├── nsp_extract.py               # Daily CCEI HFED extraction
│   ├── weather_extract.py           # Daily weather extraction
│   └── download_electricitymaps.py  # Electricity Maps CSV downloader
│
├── model/
│   └── HalifaxEnergy_Model.R   # XGBoost regression model
│
├── api/
│   ├── main.py                 # FastAPI app entry point
│   ├── requirements.txt        # Python dependencies
│   ├── database.py             # SQLAlchemy connection
│   ├── models.py               # Database ORM models
│   ├── schemas.py              # Pydantic schemas
│   ├── config.py               # Configuration loader
│   ├── scheduler.py            # APScheduler tasks
│   └── routers/
│       ├── zones.py            # GET /api/zones (GeoJSON + load)
│       ├── predictions.py      # GET /api/predictions
│       ├── actuals.py          # GET /api/actuals
│       ├── model.py            # POST /api/run-model
│       └── websocket.py        # WS /ws/live-actuals
│
├── dashboard/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   ├── public/
│   └── src/
│       ├── App.jsx             # Main app component
│       ├── main.jsx            # React entry point
│       ├── components/
│       │   ├── Map.jsx         # Leaflet map (zones + predictions)
│       │   ├── ForecastChart.jsx    # Recharts forecast viz
│       │   ├── ResidualMap.jsx      # Residual error map
│       │   └── Sidebar.jsx          # Navigation sidebar
│       └── pages/
│           ├── Dashboard.jsx   # Main dashboard page
│           ├── Models.jsx      # Model comparison page
│           └── Data.jsx        # Data explorer page
│
├── data/
│   ├── electricitymaps/        # Electricity Maps CSV downloads
│   └── geojson/                # Halifax zone boundaries
│
├── logs/
│   └── halifaxenergy.log       # Application logs
│
└── backups/                    # Database backups
```

## 🔌 API Endpoints

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/zones` | GeoJSON of Halifax zones with predicted/actual load |
| GET | `/api/predictions?horizon=H1&start=2026-01-01` | Model predictions with filters |
| GET | `/api/actuals?start=2026-01-01` | Actual load data from CCEI |
| POST | `/api/run-model` | Trigger R XGBoost model run |
| GET | `/health` | Health check |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `WS /ws/live-actuals` | Live stream of incoming CCEI load data |

## 📅 Scheduled Tasks (APScheduler)

| Task | Schedule | Description |
|------|----------|-------------|
| CCEI HFED Poll | Daily 6:00 AM | Fetch latest NS load data from CCEI |
| Weather Extract | Daily 6:30 AM | Fetch weather from Environment Canada Geomet |
| Model Retrain | Daily 4:00 AM | Run XGBoost model with latest data |

## 🗺️ Data Sources

### Load Data
1. **Electricity Maps CA-NS** (2021-2024, free tier)
   - https://app.electricitymaps.com/datasets/CA-NS
   - License: ODbL (Open Data Commons)
   - Coverage: Hourly consumption, generation, carbon intensity

2. **CCEI HFED** (2023-present)
   - https://energy-information.canada.ca/en/resources/high-frequency-electricity-data
   - No authentication required
   - Real-time NS grid demand

3. **NB Power Archive** (2019-present)
   - https://tso.nbpower.com/Public/en/system_information_archive.aspx
   - NS interconnect flow (validation feature)

### Weather Data
4. **Environment Canada** (1950s-present)
   - https://climate.weather.gc.ca/climate_data/bulk_data_e.html
   - Station: Halifax Stanfield Intl (50620)
   - Hourly: Temp, Wind, Precip, Humidity

## 🧪 Testing

```bash
# Run all backend tests
cd api
pytest

# Check database connection
python -c "from database import engine; print(engine.connect())"

# Verify tables exist
docker-compose exec sqlserver /opt/mssql-tools/bin/sqlcmd \
  -S localhost -U sa -P 'Halifax@Energy2026!' \
  -d HalifaxEnergyProject \
  -Q "SELECT name FROM sys.tables ORDER BY name"
```

## 📈 Model Performance Targets

| Horizon | RMSE Target | SI% Target | Description |
|---------|-------------|------------|-------------|
| H1 (24h) | < 50 MW | < 5% | Next-day forecast |
| H2 (48h) | < 75 MW | < 7% | 2-day forecast |
| H3 (7d) | < 100 MW | < 10% | Week-ahead forecast |

SI% = Scatter Index = (RMSE / mean_actual_load) × 100

## 🔒 Security Notes

- **DO NOT COMMIT .env** to version control
- SQL Server SA password should be strong (min 8 chars, upper/lower/digit/symbol)
- In production, use Azure Key Vault or AWS Secrets Manager
- Enable TLS for API in production
- Restrict CORS origins in production

## 📝 License

Educational project for NSCC DBAS 3090. Data sources have their own licenses:
- Electricity Maps: ODbL (attribution required)
- Environment Canada: Open Government License - Canada
- CCEI HFED: Open Government License - Canada

## 🤝 Contributing

This is an academic project (NSCC DBAS 3090). For questions:
- Dylan Bray
- NSCC — Database Administration & Security 3090
- March 2026

## 🐛 Troubleshooting

### SQL Server won't start
```bash
# Check Docker logs
docker-compose logs sqlserver

# Restart container
docker-compose restart sqlserver

# Verify Rosetta is enabled on Apple Silicon
softwareupdate --install-rosetta
```

### ODBC Driver not found
```bash
# macOS
brew install msodbcsql17

# Ubuntu/Debian
sudo apt-get install msodbcsql17

# Check driver installation
odbcinst -q -d
```

### Python package conflicts
```bash
# Use virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

---

**Last Updated:** March 14, 2026
**Version:** 1.0.0
