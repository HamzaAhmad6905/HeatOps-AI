from __future__ import annotations
import os
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# app must be defined at top level for Vercel to detect it
app = FastAPI(title="HeatOps AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path setup
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

FRONTEND_DIR = BASE_DIR / "heatops_ai" / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# Load env
from dotenv import load_dotenv
load_dotenv()

# FortyGuard
try:
    from heatops_ai.backend.fortyguard import FortyGuardClient
    from heatops_ai.backend.fortyguard.samples import MANHATTAN_POLYGON
    FORTYGUARD_IMPORT_ERROR = None
except Exception as exc:
    FortyGuardClient = None
    MANHATTAN_POLYGON = None
    FORTYGUARD_IMPORT_ERROR = str(exc)

# ── Request model ──────────────────────────────────────────
class InvestigationRequest(BaseModel):
    mission: str = Field(..., min_length=3)
    start_date: str | None = None
    start_time: str = "14:00"
    granularity: int = 100
    threshold_celsius: float = 35.0

# ── Helpers ────────────────────────────────────────────────
def safe_historical_date(requested_date: str | None) -> str:
    today = date.today()
    if not requested_date:
        return today.isoformat()
    try:
        parsed = date.fromisoformat(requested_date)
    except ValueError:
        return today.isoformat()
    return today.isoformat() if parsed > today else parsed.isoformat()

def extract_temperature_values(result: dict) -> list[float]:
    values = []
    for feature in (result.get("map_data") or {}).get("features", []):
        props = feature.get("properties") or {}
        for key in ["average_temperature", "temperature", "avg_temperature"]:
            val = props.get(key)
            if val is not None:
                try:
                    values.append(float(val))
                    break
                except (TypeError, ValueError):
                    pass
    return values

def calculate_risk(peak: float | None, threshold: float) -> tuple[str, int]:
    if peak is None:
        return "UNKNOWN", 0
    diff = peak - threshold
    if diff >= 5: return "CRITICAL", 100
    if diff >= 2: return "HIGH", 75
    if diff > 0:  return "MODERATE", 50
    return "LOW", 20

def recommendation_for_risk(risk: str) -> str:
    return {
        "CRITICAL": "Restrict or stop outdoor operations during the affected heat window.",
        "HIGH": "Reduce heat exposure and shift outdoor work to cooler hours.",
        "MODERATE": "Continue with appropriate heat controls and active monitoring.",
        "LOW": "Normal operations can continue with routine heat monitoring.",
        "UNKNOWN": "Insufficient temperature evidence for a reliable recommendation.",
    }.get(risk, "No recommendation available.")

# ── Routes ─────────────────────────────────────────────────
@app.get("/")
def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))

@app.get("/health")
def health():
    return {"status": "ok", "fortyguard_available": FortyGuardClient is not None}

@app.post("/api/investigate")
def investigate(request: InvestigationRequest):
    mission_id = str(uuid.uuid4())
    trace = []

    def add_trace(stage, status, message, **extra):
        trace.append({"timestamp": datetime.utcnow().isoformat() + "Z",
                      "stage": stage, "status": status, "message": message, **extra})

    add_trace("RECEIVED", "completed", "Mission received.")
    add_trace("PLANNING", "completed", "Mission structured and evidence plan created.")

    safe_date = safe_historical_date(request.start_date)
    add_trace("VALIDATING", "completed", f"Using valid FortyGuard date: {safe_date}")

    if FortyGuardClient is None:
        add_trace("EXECUTING", "failed", "FortyGuard client could not be imported.",
                  error=FORTYGUARD_IMPORT_ERROR)
        return {"mission_id": mission_id, "mission": request.mission,
                "status": "failed", "error": FORTYGUARD_IMPORT_ERROR,
                "investigation_trace": trace}

    try:
        client = FortyGuardClient()
        add_trace("EXECUTING", "completed", "FortyGuard client initialized.")
    except Exception as exc:
        add_trace("EXECUTING", "failed", str(exc))
        return {"mission_id": mission_id, "mission": request.mission,
                "status": "failed", "error": str(exc), "investigation_trace": trace}

    try:
        response = client.create_heatmap(
            polygon_aoi=MANHATTAN_POLYGON,
            start_date=safe_date,
            start_time=request.start_time,
            filter_type=1,
            granularity=request.granularity,
            wait=True, poll_interval=5.0, timeout=300.0, verbose=False,
        )
        result = response.get("result") or {}
        activity_id = response.get("activity_id")
        add_trace("EXECUTING", "completed", "FortyGuard heatmap completed.")
    except Exception as exc:
        add_trace("EXECUTING", "failed", str(exc))
        return {"mission_id": mission_id, "mission": request.mission,
                "status": "failed", "error": str(exc), "investigation_trace": trace}

    temperatures = extract_temperature_values(result)
    features = (result.get("map_data") or {}).get("features") or []
    map_data = result.get("map_data") or {"type": "FeatureCollection", "features": []}

    peak = max(temperatures) if temperatures else None
    avg  = sum(temperatures) / len(temperatures) if temperatures else None
    mini = min(temperatures) if temperatures else None
    risk_level, risk_score = calculate_risk(peak, request.threshold_celsius)
    recommendation = recommendation_for_risk(risk_level)

    add_trace("ANALYZING", "completed", "Heat-risk analysis completed.", risk_level=risk_level)
    add_trace("DECIDING", "completed", "Operational decision generated.")
    add_trace("COMPLETED", "completed", "Investigation completed successfully.")

    return {
        "schema_version": "1.0",
        "mission_id": mission_id,
        "mission": request.mission,
        "status": "completed",
        "date": {"requested": request.start_date, "used": safe_date},
        "risk_summary": {"risk_level": risk_level, "risk_score": risk_score,
                         "threshold_celsius": request.threshold_celsius,
                         "threshold_exceeded": peak is not None and peak > request.threshold_celsius},
        "peak_heat": {"peak_temperature": peak, "average_temperature": avg,
                      "minimum_temperature": mini, "date": safe_date, "time": request.start_time},
        "recommendations": [{"risk_level": risk_level, "action": recommendation}],
        "map_data": map_data,
        "fortyguard": {"activity_id": activity_id, "endpoint": "/v1/heatmap"},
        "investigation_trace": trace,
    }