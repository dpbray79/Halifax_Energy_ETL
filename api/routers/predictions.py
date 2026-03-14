"""
predictions.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Energy API — Model Predictions Router
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GET /api/predictions — Retrieve model predictions
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
from typing import Optional

from ..database import get_db
from ..models import ModelPrediction
from ..schemas import PredictionResponse, PredictionPoint

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.get("", response_model=PredictionResponse)
def get_predictions(
    horizon: Optional[str] = Query(
        default=None,
        description="Forecast horizon filter (H1, H2, or H3)"
    ),
    start: Optional[str] = Query(
        default=None,
        description="Start datetime (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"
    ),
    end: Optional[str] = Query(
        default=None,
        description="End datetime (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"
    ),
    limit: int = Query(default=1000, le=10000, description="Max rows to return"),
    latest_run_only: bool = Query(
        default=True,
        description="Only return predictions from the most recent model run"
    ),
    db: Session = Depends(get_db)
):
    """
    Get model predictions.

    Query parameters:
    - horizon: Forecast horizon (H1, H2, H3) - optional
    - start: Start datetime (default: 7 days ago)
    - end: End datetime (default: 7 days from now)
    - limit: Maximum rows to return (default: 1000, max: 10000)
    - latest_run_only: Only show most recent model run (default: true)

    Returns:
    - PredictionResponse with prediction data points
    """

    # Parse date range
    if end:
        try:
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid end date format: {end}")
    else:
        end_dt = datetime.now() + timedelta(days=7)

    if start:
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid start date format: {start}")
    else:
        start_dt = datetime.now() - timedelta(days=7)

    # Build query
    query = db.query(ModelPrediction)

    # Filter by horizon
    if horizon:
        if horizon.upper() not in ["H1", "H2", "H3"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid horizon: {horizon}. Must be H1, H2, or H3"
            )
        query = query.filter(ModelPrediction.ForecastHorizon == horizon.upper())

    # Filter by date range
    query = query.filter(
        and_(
            ModelPrediction.DateTime >= start_dt,
            ModelPrediction.DateTime <= end_dt
        )
    )

    # Latest run only
    if latest_run_only and horizon:
        # Get most recent ModelRunAt for this horizon
        latest_run = db.query(ModelPrediction.ModelRunAt).filter(
            ModelPrediction.ForecastHorizon == horizon.upper()
        ).order_by(ModelPrediction.ModelRunAt.desc()).first()

        if latest_run:
            query = query.filter(ModelPrediction.ModelRunAt == latest_run[0])

    # Order and limit
    query = query.order_by(ModelPrediction.DateTime.desc()).limit(limit)

    results = query.all()

    # Convert to response schema
    data_points = [
        PredictionPoint(
            datetime=row.DateTime,
            predicted_load_mw=row.Predicted_Load_MW,
            forecast_horizon=row.ForecastHorizon,
            rmse=row.Run_RMSE,
            si_pct=row.Run_SI_Pct,
            model_version=row.ModelVersion,
            model_run_at=row.ModelRunAt
        )
        for row in results
    ]

    return PredictionResponse(
        count=len(data_points),
        data=data_points,
        horizon=horizon,
        start_date=start_dt,
        end_date=end_dt
    )


@router.get("/latest/{horizon}", response_model=PredictionPoint)
def get_latest_prediction(
    horizon: str,
    db: Session = Depends(get_db)
):
    """
    Get the most recent prediction for a specific horizon.

    Path parameters:
    - horizon: Forecast horizon (H1, H2, or H3)

    Returns:
    - Single PredictionPoint with latest prediction
    """
    if horizon.upper() not in ["H1", "H2", "H3"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid horizon: {horizon}. Must be H1, H2, or H3"
        )

    latest = db.query(ModelPrediction).filter(
        ModelPrediction.ForecastHorizon == horizon.upper()
    ).order_by(ModelPrediction.DateTime.desc()).first()

    if not latest:
        raise HTTPException(
            status_code=404,
            detail=f"No predictions found for horizon {horizon}"
        )

    return PredictionPoint(
        datetime=latest.DateTime,
        predicted_load_mw=latest.Predicted_Load_MW,
        forecast_horizon=latest.ForecastHorizon,
        rmse=latest.Run_RMSE,
        si_pct=latest.Run_SI_Pct,
        model_version=latest.ModelVersion,
        model_run_at=latest.ModelRunAt
    )


@router.get("/performance")
def get_model_performance(
    horizon: Optional[str] = Query(default=None, description="Filter by horizon"),
    db: Session = Depends(get_db)
):
    """
    Get model performance metrics (RMSE, SI%) for each horizon.

    Query parameters:
    - horizon: Optional filter by horizon (H1, H2, H3)

    Returns:
    - Dictionary with performance metrics per horizon
    """
    from sqlalchemy import func

    query = db.query(
        ModelPrediction.ForecastHorizon,
        ModelPrediction.ModelRunAt,
        func.avg(ModelPrediction.Run_RMSE).label("avg_rmse"),
        func.avg(ModelPrediction.Run_SI_Pct).label("avg_si_pct"),
        func.count(ModelPrediction.PredID).label("prediction_count")
    ).group_by(
        ModelPrediction.ForecastHorizon,
        ModelPrediction.ModelRunAt
    )

    if horizon:
        if horizon.upper() not in ["H1", "H2", "H3"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid horizon: {horizon}. Must be H1, H2, or H3"
            )
        query = query.filter(ModelPrediction.ForecastHorizon == horizon.upper())

    query = query.order_by(
        ModelPrediction.ForecastHorizon,
        ModelPrediction.ModelRunAt.desc()
    )

    results = query.all()

    if not results:
        raise HTTPException(status_code=404, detail="No model performance data found")

    # Group by horizon, showing latest run for each
    performance = {}
    for row in results:
        if row.ForecastHorizon not in performance:
            performance[row.ForecastHorizon] = {
                "horizon": row.ForecastHorizon,
                "latest_run_at": row.ModelRunAt,
                "rmse": round(row.avg_rmse, 2) if row.avg_rmse else None,
                "si_pct": round(row.avg_si_pct, 2) if row.avg_si_pct else None,
                "prediction_count": row.prediction_count,
                # Performance targets
                "rmse_target": 50 if row.ForecastHorizon == "H1" else (75 if row.ForecastHorizon == "H2" else 100),
                "si_target_pct": 5 if row.ForecastHorizon == "H1" else (7 if row.ForecastHorizon == "H2" else 10)
            }

    return {
        "horizons": list(performance.values())
    }
