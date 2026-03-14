"""
actuals.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Energy API — Actual Load Data Router
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GET /api/actuals — Retrieve actual load data from Fact_Energy_Weather
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
from typing import Optional

from ..database import get_db
from ..models import FactEnergyWeather
from ..schemas import LoadDataResponse, LoadDataPoint

router = APIRouter(prefix="/api/actuals", tags=["actuals"])


@router.get("", response_model=LoadDataResponse)
def get_actuals(
    start: Optional[str] = Query(
        default=None,
        description="Start datetime (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"
    ),
    end: Optional[str] = Query(
        default=None,
        description="End datetime (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"
    ),
    limit: int = Query(default=1000, le=10000, description="Max rows to return"),
    db: Session = Depends(get_db)
):
    """
    Get actual load data from Fact_Energy_Weather.

    Query parameters:
    - start: Start datetime (default: 7 days ago)
    - end: End datetime (default: now)
    - limit: Maximum rows to return (default: 1000, max: 10000)

    Returns:
    - LoadDataResponse with actual load data points
    """

    # Parse date range
    if end:
        try:
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid end date format: {end}")
    else:
        end_dt = datetime.now()

    if start:
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid start date format: {start}")
    else:
        start_dt = end_dt - timedelta(days=7)

    # Query database
    query = db.query(FactEnergyWeather).filter(
        and_(
            FactEnergyWeather.DateTime >= start_dt,
            FactEnergyWeather.DateTime <= end_dt
        )
    ).order_by(FactEnergyWeather.DateTime.desc()).limit(limit)

    results = query.all()

    # Convert to response schema
    data_points = [
        LoadDataPoint(
            datetime=row.DateTime,
            load_mw=row.Load_MW,
            source="Fact_Energy_Weather"
        )
        for row in results
    ]

    return LoadDataResponse(
        count=len(data_points),
        data=data_points,
        start_date=start_dt,
        end_date=end_dt
    )


@router.get("/latest", response_model=LoadDataPoint)
def get_latest_actual(db: Session = Depends(get_db)):
    """
    Get the most recent actual load data point.

    Returns:
    - Single LoadDataPoint with latest actual load
    """
    latest = db.query(FactEnergyWeather).order_by(
        FactEnergyWeather.DateTime.desc()
    ).first()

    if not latest:
        raise HTTPException(status_code=404, detail="No actual data found")

    return LoadDataPoint(
        datetime=latest.DateTime,
        load_mw=latest.Load_MW,
        source="Fact_Energy_Weather"
    )


@router.get("/summary")
def get_actuals_summary(
    days: int = Query(default=30, le=365, description="Number of days to summarize"),
    db: Session = Depends(get_db)
):
    """
    Get summary statistics for actual load data.

    Query parameters:
    - days: Number of days to include (default: 30, max: 365)

    Returns:
    - Dictionary with summary statistics (min, max, avg, count)
    """
    from sqlalchemy import func

    start_dt = datetime.now() - timedelta(days=days)

    stats = db.query(
        func.count(FactEnergyWeather.Load_MW).label("count"),
        func.min(FactEnergyWeather.Load_MW).label("min_load"),
        func.max(FactEnergyWeather.Load_MW).label("max_load"),
        func.avg(FactEnergyWeather.Load_MW).label("avg_load")
    ).filter(
        FactEnergyWeather.DateTime >= start_dt
    ).first()

    if stats.count == 0:
        raise HTTPException(status_code=404, detail=f"No data found in last {days} days")

    return {
        "period_days": days,
        "start_date": start_dt,
        "end_date": datetime.now(),
        "count": stats.count,
        "min_load_mw": round(stats.min_load, 2) if stats.min_load else None,
        "max_load_mw": round(stats.max_load, 2) if stats.max_load else None,
        "avg_load_mw": round(stats.avg_load, 2) if stats.avg_load else None
    }
