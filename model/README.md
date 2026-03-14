# Halifax Energy XGBoost Model

R-based XGBoost regression model for Nova Scotia energy demand forecasting.

## Features

- **Three Forecast Horizons:**
  - H1 (24h): Next-day forecast — Target RMSE < 50 MW, SI < 5%
  - H2 (48h): 2-day forecast — Target RMSE < 75 MW, SI < 7%
  - H3 (7d): Week-ahead forecast — Target RMSE < 100 MW, SI < 10%

- **Feature Engineering:**
  - Temporal: Cyclic hour/day/month encoding, holidays, weekends, peak hours
  - Weather: Temperature, wind speed, precipitation, wind chill
  - Lags: 24h and 168h (previous day/week)
  - Heating/Cooling degree flags
  - Land use percentages (commercial/industrial)

- **Performance Metrics:**
  - RMSE (Root Mean Squared Error)
  - SI% (Scatter Index) = (RMSE / mean_actual) × 100
  - MAE (Mean Absolute Error)
  - R² (Coefficient of Determination)

## Dependencies

### R Version
- R >= 4.2.0

### Required Packages

```r
install.packages(c(
  "tidyverse",      # Data manipulation
  "tidymodels",     # ML framework
  "xgboost",        # XGBoost algorithm
  "DBI",            # Database interface
  "odbc",           # ODBC driver for SQL Server
  "lubridate",      # Date/time handling
  "glue",           # String interpolation
  "here"            # Path management
))
```

### System Requirements

**ODBC Driver 17 for SQL Server** must be installed:

```bash
# macOS
brew install msodbcsql17 mssql-tools

# Ubuntu/Debian
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | \
  sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17 mssql-tools

# Windows
# Download from: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
```

## Usage

### Train All Models

```bash
Rscript HalifaxEnergy_Model.R
```

### Train Specific Horizon

```bash
# Train only H1 (24-hour)
Rscript HalifaxEnergy_Model.R --horizon H1

# Train only H3 (7-day)
Rscript HalifaxEnergy_Model.R --horizon H3
```

### Backtesting Mode

```bash
# Run in backtest mode (flags predictions as backtests)
Rscript HalifaxEnergy_Model.R --backtest
```

## Environment Variables

Configure database connection via environment variables:

```bash
export DB_SERVER=localhost
export DB_PORT=1433
export DB_NAME=HalifaxEnergyProject
export DB_USER=sa
export DB_PASSWORD=Halifax@Energy2026!
```

Or use the DATABASE_URL from `.env`:
```bash
# In .env file
DATABASE_URL=mssql+pyodbc://sa:Halifax@Energy2026!@localhost:1433/HalifaxEnergyProject?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes
```

## Outputs

### 1. Model Artifacts
- Saved to `model_artifacts/`
- Files: `H1_model.rds`, `H2_model.rds`, `H3_model.rds`
- Can be loaded for inference: `readRDS("model_artifacts/H1_model.rds")`

### 2. Database Predictions
- Written to `Model_Predictions` table
- Columns:
  - `DateTime`: Prediction timestamp
  - `Predicted_Load_MW`: Forecasted load
  - `Run_RMSE`: Model RMSE on test set
  - `Run_SI_Pct`: Scatter Index percentage
  - `ForecastHorizon`: H1/H2/H3
  - `ModelVersion`: Model version identifier
  - `ModelRunAt`: Training timestamp
  - `IsBackTest`: 0/1 flag

### 3. Logs
- Console output and log file: `../logs/model_run.log`
- Includes performance metrics, row counts, timing

## Data Requirements

### Minimum Training Data
- At least **1,000 rows** in `Fact_Energy_Weather`
- Recommended: **2 years** of hourly data (17,520 rows)

### Required Columns in Fact_Energy_Weather
```sql
DateTime, Load_MW, Temp_C, WindSpeed_kmh, Precip_mm,
HDD_Flag, CDD_Flag, Lag_Load_24h, Lag_Load_168h,
WindChill, CommercialAreaPct, IndustrialAreaPct,
Is_Holiday, Hour, DayOfWeek, Month
```

## Performance Targets

| Horizon | RMSE Target | SI% Target | Use Case |
|---------|-------------|------------|----------|
| **H1 (24h)** | < 50 MW | < 5% | Operational planning, next-day dispatch |
| **H2 (48h)** | < 75 MW | < 7% | Resource scheduling, 2-day outlook |
| **H3 (7d)** | < 100 MW | < 10% | Weekly capacity planning, maintenance scheduling |

SI% (Scatter Index) = (RMSE / mean_actual_load) × 100

Typical NS grid load: 800-1800 MW

## Troubleshooting

### ODBC Driver Not Found
```r
Error: nanodbc/nanodbc.cpp:1021: 00000: [unixODBC][Driver Manager]Can't open lib 'ODBC Driver 17 for SQL Server'
```
**Solution:** Install ODBC Driver 17 (see System Requirements above)

### Insufficient Training Data
```r
Error: Insufficient training data: 500 rows (minimum 1000)
```
**Solution:** Run `seed_historical_data.py` to populate Fact_Energy_Weather

### Database Connection Failed
```r
Error: Database connection failed: Login timeout expired
```
**Solution:**
1. Check SQL Server is running: `docker ps`
2. Verify credentials in .env
3. Test connection: `docker-compose exec sqlserver /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'Halifax@Energy2026!'`

### Package Installation Errors
```r
Error: package 'xgboost' is not available
```
**Solution:** Update R and retry installation
```r
# Update all packages
update.packages(ask = FALSE)

# Install with dependencies
install.packages("xgboost", dependencies = TRUE)
```

## Model Tuning

To improve performance, adjust hyperparameters in `HalifaxEnergy_Model.R`:

```r
xgb_spec <- boost_tree(
  trees = 500,              # Increase for more complex patterns
  tree_depth = 6,           # Increase for deeper trees (caution: overfitting)
  min_n = 10,               # Minimum observations per node
  loss_reduction = 0.01,    # Minimum improvement to split
  learn_rate = 0.05,        # Lower = slower learning, better generalization
  mtry = 0.8,               # Proportion of features per tree
  sample_size = 0.8         # Proportion of samples per tree
) %>%
  set_engine("xgboost", nthread = 4) %>%
  set_mode("regression")
```

Use cross-validation for hyperparameter tuning:
```r
# See tidymodels tune package documentation
library(tune)
```

## Integration with FastAPI

The FastAPI backend calls this script via subprocess:

```python
# api/routers/model.py
subprocess.run(["Rscript", "model/HalifaxEnergy_Model.R", "--horizon", "H1"])
```

The scheduler runs it daily:
```python
# api/scheduler.py
scheduler.add_job(run_model, 'cron', hour=4, minute=0)  # 4:00 AM daily
```

## License

Educational project for NSCC DBAS 3090.

## Author

Dylan Bray
NSCC — Database Administration & Security 3090
March 2026
