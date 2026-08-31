from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any


def parse_mission(text: str) -> dict[str, Any]:
    t = text.strip()

    locations = (
        ["Phoenix"]
        if "phoenix" in t.lower()
        else []
    )

    if not locations:
        match = re.search(
            r"\bin\s+([A-Z][A-Za-z .-]{2,40})",
            t,
        )

        locations = (
            [match.group(1).strip()]
            if match
            else ["Phoenix"]
        )

    investigation_date = (
        date.today() + timedelta(days=1)
    )

    if "today" in t.lower():
        investigation_date = date.today()

    return {
        "location": locations[0],
        "date": investigation_date.isoformat(),
        "objective": t,
        "threshold_c": 35.0,
        "tools": [
            "create_heatmap",
            "check_exceedance",
            "check_persistence",
        ],
    }


def plan_trace(plan: dict):
    return [
        {
            "stage": "mission",
            "status": "completed",
            "detail": (
                "Mission parsed into structured fields."
            ),
        },
        {
            "stage": "location",
            "status": "completed",
            "detail": (
                f"Investigation area selected: "
                f"{plan['location']}."
            ),
        },
        {
            "stage": "planning",
            "status": "completed",
            "detail": (
                "Selected the minimum evidence set "
                "for heat exposure: temperature, "
                "exceedance and persistence."
            ),
        },
        {
            "stage": "tool_selection",
            "status": "completed",
            "detail": (
                "Selected FortyGuard heatmap analytics."
            ),
        },
    ]


def explain_with_optional_llm(
    mission: str,
    facts: dict,
    api_key: str,
    model: str,
) -> str:

    # Deterministic fallback.
    if not api_key:
        return facts.get(
            "recommendation",
            "",
        )

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key
        )

        prompt = (
            "You are the explanation layer for HeatOps AI. "
            "Never invent numbers. "
            "Rewrite the verified facts below as one concise "
            "operational recommendation. "
            "Do not create medical or regulatory claims.\n"
            f"MISSION: {mission}\n"
            f"FACTS: {facts}"
        )

        response = client.responses.create(
            model=model,
            input=prompt,
        )

        return response.output_text.strip()

    except Exception:
        return facts.get(
            "recommendation",
            "",
        )