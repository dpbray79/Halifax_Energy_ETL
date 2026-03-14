"""
model.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Energy API — Model Training Router
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POST /api/run-model — Trigger R XGBoost model training
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from datetime import datetime
import subprocess
import logging
from pathlib import Path

from ..config import settings, get_project_root
from ..schemas import ModelRunRequest, ModelRunResponse

router = APIRouter(prefix="/api", tags=["model"])
logger = logging.getLogger(__name__)


def run_r_model(horizon: str = None, backtest: bool = False):
    """
    Execute R model script via subprocess.

    Args:
        horizon: Optional horizon filter (H1, H2, H3)
        backtest: Whether to run in backtest mode
    """
    try:
        # Build command
        r_script = get_project_root() / settings.r_script_path
        cmd = [settings.rscript_bin, str(r_script)]

        if horizon:
            cmd.extend(["--horizon", horizon])

        if backtest:
            cmd.append("--backtest")

        logger.info(f"Running R model: {' '.join(cmd)}")

        # Execute R script
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10-minute timeout
        )

        if result.returncode == 0:
            logger.info(f"Model training completed successfully")
            logger.info(f"Output: {result.stdout}")
        else:
            logger.error(f"Model training failed with code {result.returncode}")
            logger.error(f"Error: {result.stderr}")
            raise RuntimeError(f"R model failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        logger.error("Model training timed out after 10 minutes")
        raise RuntimeError("Model training timeout")
    except Exception as e:
        logger.error(f"Model training error: {e}")
        raise


@router.post("/run-model", response_model=ModelRunResponse)
async def trigger_model_run(
    request: ModelRunRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger XGBoost model training.

    Request body:
    - horizon: Optional horizon to train (H1, H2, H3). If omitted, trains all.
    - backtest: Whether to run in backtest mode (default: false)

    Returns:
    - ModelRunResponse with status and details

    Note: Model training runs in background. Check logs for completion.
    """

    # Validate horizon if provided
    if request.horizon and request.horizon.upper() not in ["H1", "H2", "H3"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid horizon: {request.horizon}. Must be H1, H2, or H3"
        )

    # Check R script exists
    r_script = get_project_root() / settings.r_script_path
    if not r_script.exists():
        raise HTTPException(
            status_code=500,
            detail=f"R model script not found: {r_script}"
        )

    # Add to background tasks
    started_at = datetime.now()
    background_tasks.add_task(
        run_r_model,
        horizon=request.horizon.upper() if request.horizon else None,
        backtest=request.backtest
    )

    return ModelRunResponse(
        status="started",
        message=f"Model training started in background",
        horizon=request.horizon.upper() if request.horizon else "all",
        started_at=started_at,
        details={
            "script": str(r_script),
            "backtest": request.backtest,
            "estimated_duration": "5-10 minutes"
        }
    )


@router.get("/model-status")
def get_model_status():
    """
    Get information about the R model script and artifacts.

    Returns:
    - Dictionary with model script info and artifact status
    """
    r_script = get_project_root() / settings.r_script_path
    artifacts_dir = get_project_root() / "model" / "model_artifacts"

    # Check for model artifacts
    artifacts = []
    if artifacts_dir.exists():
        for horizon in ["H1", "H2", "H3"]:
            artifact_file = artifacts_dir / f"{horizon}_model.rds"
            if artifact_file.exists():
                artifacts.append({
                    "horizon": horizon,
                    "file": artifact_file.name,
                    "size_bytes": artifact_file.stat().st_size,
                    "modified_at": datetime.fromtimestamp(artifact_file.stat().st_mtime)
                })

    return {
        "r_script": {
            "path": str(r_script),
            "exists": r_script.exists(),
            "rscript_bin": settings.rscript_bin
        },
        "artifacts": {
            "directory": str(artifacts_dir),
            "models": artifacts,
            "count": len(artifacts)
        }
    }
