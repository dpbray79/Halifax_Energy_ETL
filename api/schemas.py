"""
schemas.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Energy Forecasting API — Pydantic Schemas
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Request/response schemas for API validation and serialization
"""

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List, Any, Dict


# ── Load Data Schemas ─────────────────────────────────────────────────────────

class LoadDataPoint(BaseModel):
    """Single load data point (actual)"""
    datetime: datetime
    load_mw: float
    source: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LoadDataResponse(BaseModel):
    """Response for actual load data endpoint"""
    count: int
    data: List[LoadDataPoint]
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# ── Prediction Schemas ────────────────────────────────────────────────────────

class PredictionPoint(BaseModel):
    """Single prediction data point"""
    datetime: datetime
    predicted_load_mw: float
    forecast_horizon: str
    rmse: Optional[float] = None
    si_pct: Optional[float] = None
    model_version: Optional[str] = None
    model_run_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PredictionResponse(BaseModel):
    """Response for predictions endpoint"""
    count: int
    data: List[PredictionPoint]
    horizon: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# ── Zone/GeoJSON Schemas ──────────────────────────────────────────────────────

class ZoneLoadData(BaseModel):
    """Load data for a specific zone"""
    zone_id: str
    zone_name: str
    predicted_load_mw: Optional[float] = None
    actual_load_mw: Optional[float] = None
    residual_mw: Optional[float] = None
    timestamp: datetime


class ZoneFeature(BaseModel):
    """GeoJSON Feature for a zone"""
    type: str = "Feature"
    id: str
    geometry: Dict[str, Any]
    properties: Dict[str, Any]


class ZoneCollection(BaseModel):
    """GeoJSON FeatureCollection for all zones"""
    type: str = "FeatureCollection"
    features: List[ZoneFeature]


# ── Model Run Schemas ─────────────────────────────────────────────────────────

class ModelRunRequest(BaseModel):
    """Request to trigger model training"""
    horizon: Optional[str] = Field(
        default=None,
        description="Forecast horizon (H1, H2, H3) or None for all"
    )
    backtest: bool = Field(default=False, description="Run in backtest mode")


class ModelRunResponse(BaseModel):
    """Response from model training trigger"""
    status: str
    message: str
    horizon: Optional[str] = None
    started_at: datetime
    details: Optional[Dict[str, Any]] = None


# ── Weather Schemas ───────────────────────────────────────────────────────────

class WeatherPoint(BaseModel):
    """Single weather observation"""
    datetime: datetime
    temp_c: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    precip_mm: Optional[float] = None
    humidity_pct: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


# ── Health Check Schema ───────────────────────────────────────────────────────

class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    database: str
    timestamp: datetime
    version: str


# ── WebSocket Schemas ─────────────────────────────────────────────────────────

class LiveActualMessage(BaseModel):
    """WebSocket message for live actual data"""
    type: str = "live_actual"
    datetime: datetime
    load_mw: float
    source: str
    timestamp: datetime  # Message timestamp


# ── Error Schema ──────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime
