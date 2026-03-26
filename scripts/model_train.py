"""
model_train.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Area Energy Demand Forecasting — XGBoost Regression Model (Python)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PURPOSE
    Replaces legacy R model (HalifaxEnergy_Model.R) for better performance
    in CI/CD. Trains XGBoost models for three forecast horizons:
    • H1 (24h): Next-day forecast
    • H2 (48h): 2-day forecast
    • H3 (7d):  Week-ahead forecast

FEATURES
    - Temporal: Hour, DayOfWeek, Month, Is_Holiday (Cyclic encoding)
    - Weather: Temp_C, WindSpeed_kmh, Precip_mm, WindChill, Temp_Squared
    - Lags: 24h, 168h, and Horizon-specific lag

AUTHOR : Dylan Bray · March 2026
"""

import os, sys, logging, json, math
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sqlalchemy import create_engine, text

# Load environment variables
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("model")

DB_URL = os.getenv("DATABASE_URL")
MODEL_VERSION = "v2.0-py"
MIN_TRAINING_ROWS = 1000

HORIZONS = {
    "H1": 24,
    "H2": 48,
    "H3": 168
}

def connect_db():
    if not DB_URL:
        raise ValueError("DATABASE_URL not set")
    return create_engine(DB_URL)

def load_training_data(engine):
    log.info("Loading training data from fact_energy_weather...")
    query = """
    SELECT 
        datetime, load_mw, temp_c, windspeed_kmh, precip_mm,
        hdd_flag, cdd_flag, windchill, lag_load_24h, lag_load_168h,
        commercial_area_pct, industrial_area_pct, is_holiday,
        hour, day_of_week, month
    FROM fact_energy_weather
    WHERE load_mw IS NOT NULL
      AND datetime >= NOW() - INTERVAL '2 years'
    ORDER BY datetime
    """
    df = pd.read_sql(text(query), engine)
    
    if len(df) < MIN_TRAINING_ROWS:
        raise ValueError(f"Insufficient training data: {len(df)} rows (min {MIN_TRAINING_ROWS})")
        
    log.info(f"  ✓ Loaded {len(df)} rows")
    return df

def engineer_features(df):
    log.info("Engineering features...")
    df = df.copy()
    
    # Cyclic encoding for temporal features
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
    df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
    df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
    
    # Derived features
    df['temp_squared'] = df['temp_c'] ** 2
    df['is_weekend'] = df['day_of_week'].isin([0, 6]).astype(int)
    df['is_peak_hour'] = df['hour'].isin([7, 8, 9, 17, 18, 19]).astype(int)
    
    # Season mapping
    def get_season(m):
        if m in [12, 1, 2]: return 1 # Winter
        if m in [3, 4, 5]: return 2  # Spring
        if m in [6, 7, 8]: return 3  # Summer
        return 4                     # Fall
    df['season'] = df['month'].apply(get_season)
    
    # One-hot encoding for season
    season_dummies = pd.get_dummies(df['season'], prefix='season').astype(int)
    df = pd.concat([df, season_dummies], axis=1)
    
    # Fill NAs
    df['temp_c'].fillna(10, inplace=True)
    df['windspeed_kmh'].fillna(15, inplace=True)
    df['precip_mm'].fillna(0, inplace=True)
    df['commercial_area_pct'].fillna(0, inplace=True)
    df['industrial_area_pct'].fillna(0, inplace=True)
    df['windchill'].fillna(df['temp_c'] * df['windspeed_kmh'], inplace=True)
    
    log.info("  ✓ Features engineered")
    return df

def train_and_predict(df, horizon_name, horizon_hours):
    log.info(f"Training {horizon_name} model ({horizon_hours}h)...")
    
    # Prepare target: shift load by horizon into the future (lead)
    df_model = df.copy().sort_values('datetime')
    df_model['target_load'] = df_model['load_mw'].shift(-horizon_hours)
    df_model['lag_horizon'] = df_model['load_mw'].shift(horizon_hours)
    
    # Drop rows where target is NA (last few rows of the dataset)
    df_full = df_model.dropna(subset=['target_load']).copy()
    
    # Features to use for training
    features = [
        'temp_c', 'windspeed_kmh', 'precip_mm', 'hdd_flag', 'cdd_flag', 
        'windchill', 'lag_load_24h', 'lag_load_168h', 'lag_horizon',
        'commercial_area_pct', 'industrial_area_pct', 'is_holiday',
        'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos', 'month_sin', 'month_cos',
        'temp_squared', 'is_weekend', 'is_peak_hour'
    ]
    # Add season dummies if they exist
    features += [c for c in df_full.columns if c.startswith('season_')]
    
    X = df_full[features]
    y = df_full['target_load']
    
    # Split
    split_idx = int(len(df_full) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # Train XGBoost
    model = xgb.XGBRegressor(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective='reg:squarederror',
        random_state=42
    )
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    si_pct = (rmse / y_test.mean()) * 100
    
    log.info(f"  ✓ {horizon_name} Performance: RMSE={rmse:.2f}, MAE={mae:.2f}, R²={r2:.4f}, SI={si_pct:.2f}%")
    
    # Predictions for the whole set (for saving to DB)
    all_preds = model.predict(X)
    pred_df = pd.DataFrame({
        'datetime': df_full['datetime'].values,
        'predicted_load_mw': all_preds,
        'run_rmse': rmse,
        'run_si_pct': si_pct,
        'forecast_horizon': horizon_name,
        'model_version': MODEL_VERSION,
        'model_run_at': datetime.now(),
        'is_backtest': 0
    })
    
    return pred_df

def save_to_db(engine, pred_df):
    log.info(f"Saving {len(pred_df)} predictions to model_predictions...")
    pred_df.to_sql("model_predictions", engine, if_exists="append", index=False)
    log.info("  ✓ Saved")

def main():
    log.info("=" * 60)
    log.info("  Halifax Energy — Python Model Training Runner")
    log.info("=" * 60)
    
    try:
        engine = connect_db()
        raw_df = load_training_data(engine)
        df = engineer_features(raw_df)
        
        for name, hours in HORIZONS.items():
            pred_df = train_and_predict(df, name, hours)
            save_to_db(engine, pred_df)
            
        log.info("✅ All models trained and predictions saved.")
        
    except Exception as e:
        log.error(f"FATAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
