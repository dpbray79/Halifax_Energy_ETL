"""
websocket.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Energy API — WebSocket Router
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WS /ws/live-actuals — Stream live actual load data to connected clients
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
import asyncio
import json
import logging

from ..database import get_db
from ..models import FactEnergyWeather

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections for live data broadcasting"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws/live-actuals")
async def websocket_live_actuals(websocket: WebSocket):
    """
    WebSocket endpoint for streaming live actual load data.

    Connects to WS /ws/live-actuals and receives:
    - Initial historical data (last 24 hours)
    - Periodic updates every 30 seconds with new data
    - Message format: {type: "live_actual", datetime, load_mw, source, timestamp}

    Usage (JavaScript):
        const ws = new WebSocket('ws://localhost:8000/ws/live-actuals');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log(data);
        };
    """
    await manager.connect(websocket)

    try:
        # Send initial historical data (last 24 hours)
        await send_historical_data(websocket)

        # Keep connection alive and send updates
        last_timestamp = datetime.now()

        while True:
            # Wait 30 seconds between checks
            await asyncio.sleep(30)

            # Check for new data since last update
            new_data = await get_new_data_since(last_timestamp)

            if new_data:
                for data_point in new_data:
                    message = {
                        "type": "live_actual",
                        "datetime": data_point["datetime"].isoformat(),
                        "load_mw": data_point["load_mw"],
                        "source": data_point["source"],
                        "timestamp": datetime.now().isoformat()
                    }
                    await websocket.send_json(message)

                # Update last timestamp
                last_timestamp = new_data[-1]["datetime"]

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


async def send_historical_data(websocket: WebSocket):
    """Send last 24 hours of data on connection"""
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        start_dt = datetime.now() - timedelta(hours=24)

        results = db.query(FactEnergyWeather).filter(
            FactEnergyWeather.DateTime >= start_dt
        ).order_by(FactEnergyWeather.DateTime.asc()).limit(100).all()

        for row in results:
            message = {
                "type": "historical",
                "datetime": row.DateTime.isoformat(),
                "load_mw": row.Load_MW,
                "source": "Fact_Energy_Weather",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send_json(message)

    finally:
        db.close()


async def get_new_data_since(since_timestamp: datetime) -> list:
    """Get new actual data since timestamp"""
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        results = db.query(FactEnergyWeather).filter(
            FactEnergyWeather.DateTime > since_timestamp
        ).order_by(FactEnergyWeather.DateTime.asc()).all()

        return [
            {
                "datetime": row.DateTime,
                "load_mw": row.Load_MW,
                "source": "Fact_Energy_Weather"
            }
            for row in results
        ]
    finally:
        db.close()


async def broadcast_new_data():
    """
    Background task to periodically broadcast new data to all connected clients.

    This function should be called from scheduler or background task.
    """
    # Get latest data
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        latest = db.query(FactEnergyWeather).order_by(
            FactEnergyWeather.DateTime.desc()
        ).first()

        if latest:
            message = {
                "type": "live_actual",
                "datetime": latest.DateTime.isoformat(),
                "load_mw": latest.Load_MW,
                "source": "Fact_Energy_Weather",
                "timestamp": datetime.now().isoformat()
            }
            await manager.broadcast(message)

    finally:
        db.close()
