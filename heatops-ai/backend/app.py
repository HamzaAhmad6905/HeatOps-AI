from __future__ import annotations

import os
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi import FastAPI

app = FastAPI()


# ============================================================
# PATH SETUP
# ============================================================

# Current file:
# temperature-api-quickstart/
# └── heatops-ai/
#     └── backend/
#         └── app.py
#
# FortyGuard package is one level above heatops-ai:
# temperature-api-quickstart/fortyguard/

CURRENT_FILE = Path(__file__).resolve()
HEATOPS_ROOT = CURRENT_FILE.parents[1]
REPO_ROOT = CURRENT_FILE.parents[2]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")


# ============================================================
# FORTYGUARD
# ============================================================

try:
    from fortyguard.client import FortyGuardClient
    from fortyguard.samples import MANHATTAN_POLYGON
except Exception as exc:
    FortyGuardClient = None
    MANHATTAN_POLYGON = None
    FORTYGUARD_IMPORT_ERROR = str(exc)
else:
    FORTYGUARD_IMPORT_ERROR = None


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="HeatOps AI",
    description="Autonomous Heat Intelligence & Operational Decision System",
    version="1.0.0",
)

# ============================================================
# FRONTEND
# ============================================================

FRONTEND_DIR = HEATOPS_ROOT / "frontend"

app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="static",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class InvestigationRequest(BaseModel):
    mission: str = Field(
        ...,
        min_length=3,
        description="Natural-language heat investigation mission.",
    )

    # Optional date supplied by the frontend.
    # If omitted, the backend uses today.
    start_date: str | None = None

    # Optional time.
    start_time: str = "14:00"

    # API heatmap resolution.
    granularity: int = 100

    # Operational threshold used by the deterministic risk engine.
    threshold_celsius: float = 35.0


# ============================================================
# DATE SAFETY
# ============================================================

def safe_historical_date(requested_date: str | None) -> str:
    """
    FortyGuard does not accept future historical dates.

    If the frontend/LLM sends tomorrow or any later date,
    automatically replace it with today's date.

    This is the important fix for the current error.
    """

    today = date.today()

    if not requested_date:
        return today.isoformat()

    try:
        parsed = date.fromisoformat(requested_date)
    except ValueError:
        # Invalid date -> use today.
        return today.isoformat()

    if parsed > today:
        return today.isoformat()

    return parsed.isoformat()


def safe_date_range(
    requested_start: str | None,
) -> tuple[str, str]:
    """
    Creates a valid historical range.

    We deliberately keep the demo window short to avoid
    unnecessary FortyGuard processing time/credits.
    """

    end_date = date.fromisoformat(
        safe_historical_date(requested_start)
    )

    start_date = end_date - timedelta(days=1)

    return start_date.isoformat(), end_date.isoformat()


# ============================================================
# DATA EXTRACTION HELPERS
# ============================================================

def extract_temperature_values(result: dict[str, Any]) -> list[float]:
    """
    Extract temperature values from FortyGuard heatmap results.

    Different API responses can expose slightly different
    property names, so we support the known forms.
    """

    values: list[float] = []

    map_data = result.get("map_data") or {}

    for feature in map_data.get("features", []):
        properties = feature.get("properties") or {}

        possible_values = [
            properties.get("average_temperature"),
            properties.get("temperature"),
            properties.get("avg_temperature"),
        ]

        for value in possible_values:
            if value is not None:
                try:
                    values.append(float(value))
                    break
                except (TypeError, ValueError):
                    pass

    return values


def calculate_risk(
    peak_temperature: float | None,
    threshold: float,
) -> tuple[str, int]:
    """
    Deterministic risk calculation.

    IMPORTANT:
    The LLM does NOT determine this number.
    The backend does.

    This keeps the numerical decision auditable.
    """

    if peak_temperature is None:
        return "UNKNOWN", 0

    difference = peak_temperature - threshold

    if difference >= 5:
        return "CRITICAL", 100

    if difference >= 2:
        return "HIGH", 75

    if difference > 0:
        return "MODERATE", 50

    return "LOW", 20


def recommendation_for_risk(risk: str) -> str:
    recommendations = {
        "CRITICAL": (
            "Restrict or stop outdoor operations during the affected "
            "heat window and reassess conditions before resuming."
        ),
        "HIGH": (
            "Reduce heat exposure and consider shifting outdoor work "
            "to cooler operating hours."
        ),
        "MODERATE": (
            "Continue operations with appropriate heat controls and "
            "active monitoring."
        ),
        "LOW": (
            "Normal operations can continue with routine heat monitoring."
        ),
        "UNKNOWN": (
            "Insufficient verified temperature evidence to make a "
            "reliable operational recommendation."
        ),
    }

    return recommendations.get(
        risk,
        "No recommendation available.",
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/", include_in_schema=False)
def root():
    return FileResponse(
        FRONTEND_DIR / "index.html"
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "fortyguard_available": FortyGuardClient is not None,
        "fortyguard_import_error": FORTYGUARD_IMPORT_ERROR,
    }


# ============================================================
# DEBUG DATE ENDPOINT
# ============================================================

@app.get("/api/date-check")
def date_check():
    """
    Simple endpoint allowing us to prove that the backend
    will never send tomorrow/future dates to FortyGuard.
    """

    today = date.today().isoformat()

    tomorrow = (
        date.today() + timedelta(days=1)
    ).isoformat()

    return {
        "today": today,
        "tomorrow": tomorrow,
        "safe_tomorrow_value": safe_historical_date(tomorrow),
        "safe_today_value": safe_historical_date(today),
    }


# ============================================================
# MAIN INVESTIGATION
# ============================================================

@app.post("/api/investigate")
def investigate(request: InvestigationRequest):

    mission_id = str(uuid.uuid4())

    trace: list[dict[str, Any]] = []

    def add_trace(
        stage: str,
        status: str,
        message: str,
        **extra: Any,
    ):
        trace.append(
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "stage": stage,
                "status": status,
                "message": message,
                **extra,
            }
        )

    # --------------------------------------------------------
    # 1. RECEIVED
    # --------------------------------------------------------

    add_trace(
        "RECEIVED",
        "completed",
        "Mission received.",
    )

    # --------------------------------------------------------
    # 2. PLANNING
    # --------------------------------------------------------

    add_trace(
        "PLANNING",
        "completed",
        "Mission structured and evidence plan created.",
    )

    # --------------------------------------------------------
    # 3. DATE VALIDATION
    # --------------------------------------------------------

    requested_date = request.start_date

    safe_date = safe_historical_date(requested_date)

    if requested_date and requested_date != safe_date:
        add_trace(
            "VALIDATING",
            "warning",
            (
                f"Requested date {requested_date} is in the future. "
                f"Automatically changed to {safe_date} because "
                "FortyGuard historical requests cannot use future dates."
            ),
            original_date=requested_date,
            corrected_date=safe_date,
        )
    else:
        add_trace(
            "VALIDATING",
            "completed",
            f"Using valid FortyGuard date: {safe_date}",
            date=safe_date,
        )

    # --------------------------------------------------------
    # 4. FORTYGUARD AVAILABILITY
    # --------------------------------------------------------

    if FortyGuardClient is None:

        add_trace(
            "EXECUTING",
            "failed",
            "FortyGuard Python client could not be imported.",
            error=FORTYGUARD_IMPORT_ERROR,
        )

        return {
            "mission_id": mission_id,
            "mission": request.mission,
            "status": "failed",
            "error": {
                "type": "FORTYGUARD_IMPORT_ERROR",
                "message": FORTYGUARD_IMPORT_ERROR,
            },
            "investigation_trace": trace,
        }

    # --------------------------------------------------------
    # 5. CREATE CLIENT
    # --------------------------------------------------------

    try:
        client = FortyGuardClient()

        add_trace(
            "EXECUTING",
            "completed",
            "FortyGuard client initialized.",
        )

    except Exception as exc:

        add_trace(
            "EXECUTING",
            "failed",
            "Could not initialize FortyGuard client.",
            error=str(exc),
        )

        return {
            "mission_id": mission_id,
            "mission": request.mission,
            "status": "failed",
            "error": {
                "type": "CLIENT_INITIALIZATION_ERROR",
                "message": str(exc),
            },
            "investigation_trace": trace,
        }

    # --------------------------------------------------------
    # 6. EXECUTE HEATMAP
    # --------------------------------------------------------

    add_trace(
        "EXECUTING",
        "running",
        "Submitting FortyGuard heatmap analysis.",
        endpoint="/v1/heatmap",
        start_date=safe_date,
        start_time=request.start_time,
        granularity=request.granularity,
    )

    try:

        response = client.create_heatmap(
            polygon_aoi=MANHATTAN_POLYGON,
            start_date=safe_date,
            start_time=request.start_time,
            filter_type=1,
            granularity=request.granularity,
            wait=True,
            poll_interval=5.0,
            timeout=300.0,
            verbose=False,
        )

        activity_id = response.get("activity_id")

        result = response.get("result") or {}

        add_trace(
            "EXECUTING",
            "completed",
            "FortyGuard heatmap completed.",
            endpoint="/v1/heatmap",
            activity_id=activity_id,
        )

    except Exception as exc:

        add_trace(
            "EXECUTING",
            "failed",
            "FortyGuard heatmap request failed.",
            endpoint="/v1/heatmap",
            error=str(exc),
        )

        return {
            "mission_id": mission_id,
            "mission": request.mission,
            "status": "failed",
            "error": {
                "type": "FORTYGUARD_HEATMAP_ERROR",
                "message": str(exc),
            },
            "investigation_trace": trace,
        }

    # --------------------------------------------------------
    # 7. VALIDATE RESULT
    # --------------------------------------------------------

    map_data = result.get("map_data") or {}

    features = map_data.get("features") or []

    temperatures = extract_temperature_values(result)

    if not map_data or not map_data.get("features"):
        # FortyGuard successfully responded, but did not provide
        # polygon features for the requested location/date.
        #
        # Do NOT fail the entire investigation. Return an empty
        # FeatureCollection so the frontend can continue displaying
        # the investigation results.
        map_data = {
            "type": "FeatureCollection",
            "features": [],
        }

        add_trace(
            "VALIDATING",
            "completed",
            "FortyGuard completed successfully, but no heatmap features were returned for this request; continuing with an empty result.",
            feature_count=0,
            temperature_count=0,
        )
    else:
        add_trace(
            "VALIDATING",
            "completed",
            "FortyGuard result validated.",
            feature_count=len(features),
            temperature_count=len(temperatures),
        )

    # --------------------------------------------------------
    # 8. DETERMINISTIC ANALYSIS
    # --------------------------------------------------------

    peak_temperature = (
        max(temperatures)
        if temperatures
        else None
    )

    average_temperature = (
        sum(temperatures) / len(temperatures)
        if temperatures
        else None
    )

    minimum_temperature = (
        min(temperatures)
        if temperatures
        else None
    )

    risk_level, risk_score = calculate_risk(
        peak_temperature,
        request.threshold_celsius,
    )

    threshold_exceeded = (
        peak_temperature is not None
        and peak_temperature > request.threshold_celsius
    )

    add_trace(
        "ANALYZING",
        "completed",
        "Deterministic heat-risk analysis completed.",
        peak_temperature=peak_temperature,
        average_temperature=average_temperature,
        minimum_temperature=minimum_temperature,
        threshold_celsius=request.threshold_celsius,
        threshold_exceeded=threshold_exceeded,
        risk_level=risk_level,
        risk_score=risk_score,
    )

    # --------------------------------------------------------
    # 9. DECISION
    # --------------------------------------------------------

    recommendation = recommendation_for_risk(risk_level)

    add_trace(
        "DECIDING",
        "completed",
        "Operational decision generated from deterministic analysis.",
        risk_level=risk_level,
    )

    # --------------------------------------------------------
    # 10. FINAL RESPONSE
    # --------------------------------------------------------

    add_trace(
        "COMPLETED",
        "completed",
        "Investigation completed successfully.",
    )

    return {
        "schema_version": "1.0",

        "mission_id": mission_id,

        "mission": request.mission,

        "status": "completed",

        "data_quality": {
            "status": "verified",
            "source": "FortyGuard",
            "feature_count": len(features),
            "temperature_count": len(temperatures),
        },

        "date": {
            "requested": requested_date,
            "used": safe_date,
        },

        "locations": [
            {
                "name": "Manhattan demonstration area",
                "source": "FortyGuard sample polygon",
            }
        ],

        "risk_summary": {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "threshold_celsius": request.threshold_celsius,
            "threshold_exceeded": threshold_exceeded,
        },

        "peak_heat": {
            "peak_temperature": peak_temperature,
            "average_temperature": average_temperature,
            "minimum_temperature": minimum_temperature,
            "unit": "FortyGuard heatmap temperature unit",
            "date": safe_date,
            "time": request.start_time,
        },

        "recommendations": [
            {
                "risk_level": risk_level,
                "action": recommendation,
                "evidence": {
                    "peak_temperature": peak_temperature,
                    "threshold_celsius": request.threshold_celsius,
                    "date": safe_date,
                },
            }
        ],

        "map_data": map_data,

        "fortyguard": {
            "activity_id": activity_id,
            "endpoint": "/v1/heatmap",
        },

        "investigation_trace": trace,
    }