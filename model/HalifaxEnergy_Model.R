#!/usr/bin/env Rscript
# ══════════════════════════════════════════════════════════════════════════════
# HalifaxEnergy_Model.R
# Halifax Area Energy Demand Forecasting — XGBoost Regression Model
# ══════════════════════════════════════════════════════════════════════════════
#
# PURPOSE
#   Train XGBoost models for three forecast horizons:
#   • H1 (24h):  Next-day forecast  — target RMSE < 50 MW, SI < 5%
#   • H2 (48h):  2-day forecast     — target RMSE < 75 MW, SI < 7%
#   • H3 (7d):   Week-ahead         — target RMSE < 100 MW, SI < 10%
#
# DATA FLOW
#   SQL Server Fact_Energy_Weather → R feature engineering → XGBoost training
#   → Predictions written back to Model_Predictions table
#
# FEATURES
#   • Temporal: Hour, DayOfWeek, Month, Is_Holiday, Season
#   • Weather: Temp_C, WindSpeed_kmh, Precip_mm, WindChill
#   • Lags: Load_24h, Load_168h (previous day/week)
#   • Heating/Cooling: HDD_Flag, CDD_Flag
#   • Land Use: CommercialAreaPct, IndustrialAreaPct (if available)
#
# USAGE
#   # Train all horizons
#   Rscript HalifaxEnergy_Model.R
#
#   # Train specific horizon
#   Rscript HalifaxEnergy_Model.R --horizon H1
#
#   # Backtesting mode
#   Rscript HalifaxEnergy_Model.R --backtest --start-date 2025-01-01
#
# OUTPUTS
#   • Model_Predictions table populated with predictions + RMSE/SI%
#   • Model objects saved to ./model_artifacts/
#   • Performance metrics logged to stdout and ./logs/model_run.log
#
# DEPENDENCIES
#   install.packages(c("tidyverse", "tidymodels", "xgboost", "DBI", "odbc",
#                      "lubridate", "glue", "jsonlite", "here"))
#
# Author: Dylan Bray · NSCC DBAS 3090 · March 2026
# ══════════════════════════════════════════════════════════════════════════════

# ── Load Libraries ────────────────────────────────────────────────────────────
suppressPackageStartupMessages({
  library(tidyverse)
  library(tidymodels)
  library(xgboost)
  library(DBI)
  library(odbc)
  library(lubridate)
  library(glue)
})

# ── Configuration ─────────────────────────────────────────────────────────────

# Database connection (override with env var DATABASE_URL)
DB_SERVER   <- Sys.getenv("DB_SERVER", "localhost")
DB_PORT     <- Sys.getenv("DB_PORT", "1433")
DB_NAME     <- Sys.getenv("DB_NAME", "HalifaxEnergyProject")
DB_USER     <- Sys.getenv("DB_USER", "sa")
DB_PASSWORD <- Sys.getenv("DB_PASSWORD", "Halifax@Energy2026!")

# Model parameters
MODEL_VERSION <- "v1.0"
MIN_TRAINING_ROWS <- 1000  # Minimum rows required for training

# Forecast horizons (hours ahead)
HORIZONS <- list(
  H1 = 24,   # Next-day
  H2 = 48,   # 2-day ahead
  H3 = 168   # Week-ahead
)

# Model artifacts directory
ARTIFACTS_DIR <- here::here("model", "model_artifacts")
dir.create(ARTIFACTS_DIR, showWarnings = FALSE, recursive = TRUE)

# Logging
LOG_DIR <- here::here("logs")
dir.create(LOG_DIR, showWarnings = FALSE)
LOG_FILE <- file.path(LOG_DIR, "model_run.log")

log_message <- function(msg) {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  log_line <- glue("[{timestamp}] {msg}")
  cat(log_line, "\n", file = LOG_FILE, append = TRUE)
  cat(log_line, "\n")
}

# ── Database Connection ───────────────────────────────────────────────────────

connect_db <- function() {
  log_message("Connecting to SQL Server...")

  tryCatch({
    conn <- dbConnect(
      odbc::odbc(),
      Driver   = "ODBC Driver 17 for SQL Server",
      Server   = glue("{DB_SERVER},{DB_PORT}"),
      Database = DB_NAME,
      UID      = DB_USER,
      PWD      = DB_PASSWORD,
      TrustServerCertificate = "yes"
    )

    # Test connection
    dbGetQuery(conn, "SELECT 1")
    log_message("  ✓ Connected to SQL Server")

    return(conn)
  }, error = function(e) {
    log_message(glue("  ✗ Database connection failed: {e$message}"))
    stop(e)
  })
}

# ── Data Loading ──────────────────────────────────────────────────────────────

load_training_data <- function(conn) {
  log_message("Loading training data from Fact_Energy_Weather...")

  query <- "
    SELECT
      DateTime,
      Load_MW,
      Temp_C,
      WindSpeed_kmh,
      Precip_mm,
      HDD_Flag,
      CDD_Flag,
      Lag_Load_24h,
      Lag_Load_168h,
      WindChill,
      CommercialAreaPct,
      IndustrialAreaPct,
      Is_Holiday,
      Hour,
      DayOfWeek,
      Month
    FROM Fact_Energy_Weather
    WHERE Load_MW IS NOT NULL
      AND DateTime >= DATEADD(year, -2, GETDATE())  -- Last 2 years
    ORDER BY DateTime
  "

  data <- dbGetQuery(conn, query)

  if (nrow(data) < MIN_TRAINING_ROWS) {
    stop(glue("Insufficient training data: {nrow(data)} rows (minimum {MIN_TRAINING_ROWS})"))
  }

  log_message(glue("  ✓ Loaded {nrow(data):,} rows"))
  log_message(glue("  Date range: {min(data$DateTime)} → {max(data$DateTime)}"))

  return(data)
}

# ── Feature Engineering ───────────────────────────────────────────────────────

engineer_features <- function(data) {
  log_message("Engineering features...")

  data <- data %>%
    mutate(
      # Temporal features
      Hour = as.integer(Hour),
      DayOfWeek = as.integer(DayOfWeek),
      Month = as.integer(Month),
      Is_Holiday = as.integer(Is_Holiday),

      # Cyclic encoding for hour (24-hour cycle)
      Hour_sin = sin(2 * pi * Hour / 24),
      Hour_cos = cos(2 * pi * Hour / 24),

      # Cyclic encoding for day of week (7-day cycle)
      DayOfWeek_sin = sin(2 * pi * DayOfWeek / 7),
      DayOfWeek_cos = cos(2 * pi * DayOfWeek / 7),

      # Cyclic encoding for month (12-month cycle)
      Month_sin = sin(2 * pi * Month / 12),
      Month_cos = cos(2 * pi * Month / 12),

      # Derived weather features
      WindChill = coalesce(WindChill, Temp_C * WindSpeed_kmh),
      Temp_Squared = Temp_C^2,

      # Weekend flag
      Is_Weekend = as.integer(DayOfWeek %in% c(0, 6)),

      # Peak hour flag (7-9 AM, 5-7 PM)
      Is_PeakHour = as.integer(Hour %in% c(7, 8, 9, 17, 18, 19)),

      # Season (simplified)
      Season = case_when(
        Month %in% c(12, 1, 2) ~ "Winter",
        Month %in% c(3, 4, 5) ~ "Spring",
        Month %in% c(6, 7, 8) ~ "Summer",
        TRUE ~ "Fall"
      ),

      # Handle missing values
      Temp_C = coalesce(Temp_C, 10),  # Use mild default
      WindSpeed_kmh = coalesce(WindSpeed_kmh, 15),
      Precip_mm = coalesce(Precip_mm, 0),
      CommercialAreaPct = coalesce(CommercialAreaPct, 0),
      IndustrialAreaPct = coalesce(IndustrialAreaPct, 0)
    )

  log_message("  ✓ Features engineered")
  return(data)
}

# ── Model Training ────────────────────────────────────────────────────────────

train_horizon_model <- function(data, horizon_name, horizon_hours) {
  log_message(glue("Training {horizon_name} model (horizon: {horizon_hours}h)..."))

  # Create lagged target (shift load by horizon hours)
  data <- data %>%
    arrange(DateTime) %>%
    mutate(
      Target_Load = lead(Load_MW, n = horizon_hours),
      # Additional lag features specific to horizon
      Lag_Horizon = lag(Load_MW, n = horizon_hours)
    ) %>%
    filter(!is.na(Target_Load))  # Remove rows without target

  # Train/test split (80/20, chronological)
  split_idx <- floor(nrow(data) * 0.8)
  train_data <- data[1:split_idx, ]
  test_data  <- data[(split_idx + 1):nrow(data), ]

  log_message(glue("  Train: {nrow(train_data)} rows | Test: {nrow(test_data)} rows"))

  # Define recipe
  recipe_spec <- recipe(Target_Load ~ ., data = train_data) %>%
    update_role(DateTime, new_role = "ID") %>%
    update_role(Load_MW, new_role = "ID") %>%  # Original load (not predictor)
    step_dummy(Season, one_hot = TRUE) %>%
    step_zv(all_predictors()) %>%
    step_normalize(all_numeric_predictors())

  # XGBoost model specification
  xgb_spec <- boost_tree(
    trees = 500,
    tree_depth = 6,
    min_n = 10,
    loss_reduction = 0.01,
    learn_rate = 0.05,
    mtry = 0.8,
    sample_size = 0.8
  ) %>%
    set_engine("xgboost", nthread = 4) %>%
    set_mode("regression")

  # Workflow
  xgb_workflow <- workflow() %>%
    add_recipe(recipe_spec) %>%
    add_model(xgb_spec)

  # Train model
  log_message("  Training XGBoost...")
  xgb_fit <- xgb_workflow %>%
    fit(data = train_data)

  # Predictions on test set
  test_preds <- predict(xgb_fit, test_data) %>%
    bind_cols(test_data %>% select(DateTime, Target_Load, Load_MW))

  # Evaluate
  metrics <- test_preds %>%
    metrics(truth = Target_Load, estimate = .pred)

  rmse_val <- metrics %>% filter(.metric == "rmse") %>% pull(.estimate)
  mae_val  <- metrics %>% filter(.metric == "mae") %>% pull(.estimate)
  rsq_val  <- metrics %>% filter(.metric == "rsq") %>% pull(.estimate)

  # Scatter Index (SI%) = (RMSE / mean_actual) * 100
  mean_actual <- mean(test_data$Target_Load, na.rm = TRUE)
  si_pct <- (rmse_val / mean_actual) * 100

  log_message(glue("  ✓ {horizon_name} Model Performance:"))
  log_message(glue("    RMSE:  {round(rmse_val, 2)} MW"))
  log_message(glue("    MAE:   {round(mae_val, 2)} MW"))
  log_message(glue("    R²:    {round(rsq_val, 4)}"))
  log_message(glue("    SI%:   {round(si_pct, 2)}%"))

  # Save model artifact
  model_file <- file.path(ARTIFACTS_DIR, glue("{horizon_name}_model.rds"))
  saveRDS(xgb_fit, model_file)
  log_message(glue("  ✓ Model saved: {model_file}"))

  return(list(
    model = xgb_fit,
    predictions = test_preds,
    rmse = rmse_val,
    si_pct = si_pct,
    horizon_name = horizon_name
  ))
}

# ── Save Predictions to Database ──────────────────────────────────────────────

save_predictions <- function(conn, predictions, horizon_name, rmse, si_pct, is_backtest = FALSE) {
  log_message(glue("Saving {horizon_name} predictions to Model_Predictions..."))

  pred_df <- predictions %>%
    transmute(
      DateTime = DateTime,
      Predicted_Load_MW = .pred,
      Run_RMSE = rmse,
      Run_SI_Pct = si_pct,
      ForecastHorizon = horizon_name,
      ModelVersion = MODEL_VERSION,
      ModelRunAt = Sys.time(),
      IsBackTest = as.integer(is_backtest)
    )

  # Write to temp table then insert (avoids duplicates)
  dbWriteTable(conn, "__tmp_predictions", pred_df, overwrite = TRUE)

  dbExecute(conn, "
    INSERT INTO Model_Predictions
      (DateTime, Predicted_Load_MW, Run_RMSE, Run_SI_Pct, ForecastHorizon,
       ModelVersion, ModelRunAt, IsBackTest)
    SELECT DateTime, Predicted_Load_MW, Run_RMSE, Run_SI_Pct, ForecastHorizon,
           ModelVersion, ModelRunAt, IsBackTest
    FROM __tmp_predictions
    WHERE NOT EXISTS (
      SELECT 1 FROM Model_Predictions mp
      WHERE mp.DateTime = __tmp_predictions.DateTime
        AND mp.ForecastHorizon = __tmp_predictions.ForecastHorizon
        AND mp.ModelRunAt = __tmp_predictions.ModelRunAt
    )
  ")

  dbExecute(conn, "DROP TABLE __tmp_predictions")

  log_message(glue("  ✓ Saved {nrow(pred_df)} predictions"))
}

# ── Main Execution ────────────────────────────────────────────────────────────

main <- function() {
  log_message("══════════════════════════════════════════════════════════════════")
  log_message("  Halifax Energy Forecasting — XGBoost Model Training")
  log_message("══════════════════════════════════════════════════════════════════")

  # Parse command-line arguments
  args <- commandArgs(trailingOnly = TRUE)

  horizon_filter <- NULL
  is_backtest <- FALSE

  if ("--horizon" %in% args) {
    idx <- which(args == "--horizon")
    if (length(args) > idx) {
      horizon_filter <- args[idx + 1]
    }
  }

  if ("--backtest" %in% args) {
    is_backtest <- TRUE
    log_message("  Mode: BACKTEST")
  }

  # Connect to database
  conn <- connect_db()
  on.exit(dbDisconnect(conn))

  # Load and prepare data
  raw_data <- load_training_data(conn)
  data <- engineer_features(raw_data)

  # Train models
  results <- list()

  for (horizon_name in names(HORIZONS)) {
    # Skip if horizon filter is set and doesn't match
    if (!is.null(horizon_filter) && horizon_name != horizon_filter) {
      next
    }

    horizon_hours <- HORIZONS[[horizon_name]]

    result <- train_horizon_model(data, horizon_name, horizon_hours)
    results[[horizon_name]] <- result

    # Save predictions to database
    save_predictions(
      conn,
      result$predictions,
      horizon_name,
      result$rmse,
      result$si_pct,
      is_backtest
    )
  }

  log_message("══════════════════════════════════════════════════════════════════")
  log_message("  ✅ Model training complete!")
  log_message("══════════════════════════════════════════════════════════════════")
  log_message("")
  log_message("Performance Summary:")
  for (horizon_name in names(results)) {
    r <- results[[horizon_name]]
    log_message(glue("  {horizon_name}: RMSE = {round(r$rmse, 2)} MW, SI = {round(r$si_pct, 2)}%"))
  }
  log_message("")
  log_message("Next steps:")
  log_message("  1. Check predictions: SELECT TOP 10 * FROM Model_Predictions ORDER BY ModelRunAt DESC")
  log_message("  2. Start FastAPI: cd api && uvicorn main:app --reload")
  log_message("  3. View dashboard: http://localhost:5173")
  log_message("══════════════════════════════════════════════════════════════════")
}

# Run if script is executed directly
if (!interactive()) {
  main()
}
