"""
zones.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Energy API — Geographic Zones Router
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GET /api/zones — Return GeoJSON with predicted/actual load per zone
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
import json
from pathlib import Path

from ..database import get_db
from ..models import ModelPrediction, FactEnergyWeather
from ..config import settings, get_project_root
from ..schemas import ZoneCollection

router = APIRouter(prefix="/api/zones", tags=["zones"])


@router.get("", response_model=ZoneCollection)
def get_zones(
    horizon: str = Query(default="H1", description="Forecast horizon (H1, H2, H3)"),
    timestamp: Optional[str] = Query(
        default=None,
        description="Specific timestamp for predictions (default: latest)"
    ),
    db: Session = Depends(get_db)
):
    """
    Get Halifax zones as GeoJSON with predicted and actual load data.

    Query parameters:
    - horizon: Forecast horizon (H1, H2, H3) - default: H1
    - timestamp: Specific timestamp for data (default: latest available)

    Returns:
    - GeoJSON FeatureCollection with zone geometries and load properties
    """

    # Validate horizon
    if horizon.upper() not in ["H1", "H2", "H3"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid horizon: {horizon}. Must be H1, H2, or H3"
        )

    # Parse timestamp
    if timestamp:
        try:
            target_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timestamp format: {timestamp}"
            )
    else:
        # Get latest prediction timestamp for this horizon
        latest = db.query(ModelPrediction.DateTime).filter(
            ModelPrediction.ForecastHorizon == horizon.upper()
        ).order_by(ModelPrediction.DateTime.desc()).first()

        if not latest:
            raise HTTPException(
                status_code=404,
                detail=f"No predictions found for horizon {horizon}"
            )
        target_dt = latest[0]

    # Load GeoJSON base file (Halifax zone boundaries)
    geojson_path = get_project_root() / settings.geojson_zones_path

    if not geojson_path.exists():
        # Return placeholder GeoJSON if file doesn't exist
        # In production, this file should be created with actual Halifax zone boundaries
        return _get_placeholder_zones()

    with open(geojson_path, 'r') as f:
        geojson_data = json.load(f)

    # Get predictions for this timestamp
    predictions = db.query(ModelPrediction).filter(
        ModelPrediction.ForecastHorizon == horizon.upper(),
        ModelPrediction.DateTime == target_dt
    ).all()

    # Get actual load (if available)
    actuals = db.query(FactEnergyWeather).filter(
        FactEnergyWeather.DateTime == target_dt
    ).first()

    # Map predictions to zones
    # NOTE: In production, you'd have a proper zone mapping table
    # For now, distribute total predicted load evenly across zones
    total_predicted = sum(p.Predicted_Load_MW for p in predictions if p.Predicted_Load_MW) if predictions else 0
    num_zones = len(geojson_data.get("features", []))

    # Enrich GeoJSON features with load data
    for i, feature in enumerate(geojson_data.get("features", [])):
        zone_id = feature.get("id", f"zone_{i}")

        # Distribute load (simplified - in production, use actual zone load data)
        zone_predicted = total_predicted / num_zones if num_zones > 0 else 0
        zone_actual = actuals.Load_MW / num_zones if actuals and num_zones > 0 else None

        feature["properties"].update({
            "zone_id": zone_id,
            "predicted_load_mw": round(zone_predicted, 2),
            "actual_load_mw": round(zone_actual, 2) if zone_actual else None,
            "residual_mw": round(zone_actual - zone_predicted, 2) if zone_actual else None,
            "timestamp": target_dt.isoformat(),
            "horizon": horizon.upper()
        })

    return geojson_data


def _get_placeholder_zones() -> dict:
    """
    Return placeholder GeoJSON for Halifax zones.

    In production, replace this with actual Halifax geographic zone boundaries.
    """
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "halifax_central",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-63.575, 44.645],
                        [-63.575, 44.665],
                        [-63.555, 44.665],
                        [-63.555, 44.645],
                        [-63.575, 44.645]
                    ]]
                },
                "properties": {
                    "zone_name": "Halifax Central",
                    "zone_id": "halifax_central",
                    "predicted_load_mw": 0,
                    "actual_load_mw": None,
                    "residual_mw": None,
                    "timestamp": datetime.now().isoformat(),
                    "horizon": "H1"
                }
            },
            {
                "type": "Feature",
                "id": "dartmouth",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-63.555, 44.645],
                        [-63.555, 44.665],
                        [-63.535, 44.665],
                        [-63.535, 44.645],
                        [-63.555, 44.645]
                    ]]
                },
                "properties": {
                    "zone_name": "Dartmouth",
                    "zone_id": "dartmouth",
                    "predicted_load_mw": 0,
                    "actual_load_mw": None,
                    "residual_mw": None,
                    "timestamp": datetime.now().isoformat(),
                    "horizon": "H1"
                }
            },
            {
                "type": "Feature",
                "id": "bedford",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-63.645, 44.725],
                        [-63.645, 44.745],
                        [-63.625, 44.745],
                        [-63.625, 44.725],
                        [-63.645, 44.725]
                    ]]
                },
                "properties": {
                    "zone_name": "Bedford",
                    "zone_id": "bedford",
                    "predicted_load_mw": 0,
                    "actual_load_mw": None,
                    "residual_mw": None,
                    "timestamp": datetime.now().isoformat(),
                    "horizon": "H1"
                }
            }
        ]
    }
