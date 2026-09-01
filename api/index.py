from __future__ import annotations
import os
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Fix import path so fortyguard package is found
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

# Try importing FortyGuard client
try:
    from heatops_ai.backend.fortyguard import FortyGuardClient
    from heatops_ai.backend.fortyguard.samples import MANHATTAN_POLYGON
    FORTYGUARD_IMPORT_ERROR = None
except Exception as exc:
    FortyGuardClient = None
    MANHATTAN_POLYGON = None
    FORTYGUARD_IMPORT_ERROR = str(exc)

app = FastAPI(title="HeatOps AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = BASE_DIR / "heatops_ai" / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

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