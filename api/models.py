"""
models.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Energy Forecasting API — SQLAlchemy ORM Models
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ORM models mapping to Supabase PostgreSQL tables

UPDATED FOR SUPABASE:
  - Table names changed to lowercase (PostgreSQL convention)
  - DateTime → use func.now() instead of func.getdate()
  - Column types updated for PostgreSQL
"""

from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from datetime import datetime

from .database import Base


class StgNSPLoad(Base):
    """Staging table for NS Power load data from CCEI HFED"""
    __tablename__ = "stg_nsp_load"

    load_id = Column(Integer, primary_key=True, autoincrement=True)
    datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    load_mw = Column(Float, nullable=False)
    source = Column(Text, nullable=True)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())
    is_processed = Column(Boolean, default=False)


class StgWeather(Base):
    """Staging table for Halifax Stanfield weather observations"""
    __tablename__ = "stg_weather"

    weather_id = Column(Integer, primary_key=True, autoincrement=True)
    datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    temp_c = Column(Float, nullable=True)
    windspeed_kmh = Column(Float, nullable=True)
    precip_mm = Column(Float, nullable=True)
    humidity_pct = Column(Float, nullable=True)
    source = Column(Text, nullable=True)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())


class FactEnergyWeather(Base):
    """Gold table: merged energy + weather features for ML"""
    __tablename__ = "fact_energy_weather"

    fact_id = Column(Integer, primary_key=True, autoincrement=True)
    date_id = Column(Integer, nullable=True)
    datetime = Column(DateTime(timezone=True), nullable=False, unique=True, index=True)
    load_mw = Column(Float, nullable=False)
    temp_c = Column(Float, nullable=True)
    windspeed_kmh = Column(Float, nullable=True)
    precip_mm = Column(Float, nullable=True)
    hdd_flag = Column(Boolean, nullable=True)  # Heating degree day
    cdd_flag = Column(Boolean, nullable=True)  # Cooling degree day
    lag_load_24h = Column(Float, nullable=True)
    lag_load_168h = Column(Float, nullable=True)
    windchill = Column(Float, nullable=True)
    commercial_area_pct = Column(Float, nullable=True)
    industrial_area_pct = Column(Float, nullable=True)
    is_holiday = Column(Boolean, default=False)
    hour = Column(Integer, nullable=True)
    day_of_week = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)


class ModelPrediction(Base):
    """XGBoost model predictions with performance metrics"""
    __tablename__ = "model_predictions"

    pred_id = Column(Integer, primary_key=True, autoincrement=True)
    date_id = Column(Integer, nullable=True)
    datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    predicted_load_mw = Column(Float, nullable=True)
    run_rmse = Column(Float, nullable=True)
    run_si_pct = Column(Float, nullable=True)
    forecast_horizon = Column(Text, nullable=True)  # H1, H2, H3
    model_version = Column(Text, nullable=True)
    model_run_at = Column(DateTime(timezone=True), server_default=func.now())
    is_backtest = Column(Boolean, default=False)
    residual_mw = Column(Float, nullable=True)  # Actual - Predicted


class DimDate(Base):
    """Date dimension table with holidays and seasons"""
    __tablename__ = "dim_date"

    date_id = Column(Integer, primary_key=True, autoincrement=True)
    datetime = Column(DateTime(timezone=True), nullable=False, unique=True)
    hour = Column(Integer, nullable=False)
    day_of_week = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    is_holiday = Column(Boolean, default=False)
    holiday_name = Column(Text, nullable=True)
    season = Column(Text, nullable=True)


class ETLWatermark(Base):
    """ETL watermark tracking for incremental loads"""
    __tablename__ = "etl_watermark"

    watermark_id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(Text, nullable=False, unique=True)
    last_extracted = Column(DateTime(timezone=True), nullable=False,
                          server_default='2023-01-01')
    rows_inserted = Column(Integer, default=0)
    status = Column(Text, default='OK')
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                       onupdate=func.now())
