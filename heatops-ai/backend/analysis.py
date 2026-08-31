from __future__ import annotations

from statistics import mean


def _temps(result: dict) -> list[float]:
    values = []

    features = (
        result.get("map_data") or {}
    ).get("features", [])

    for feature in features:
        properties = feature.get(
            "properties",
            {},
        )

        for key in (
            "average_temperature",
            "temperature",
            "value",
        ):
            value = properties.get(key)

            if isinstance(value, (int, float)):
                values.append(float(value))
                break

    return values


def summarize_heatmap(result: dict) -> dict:
    temperatures = _temps(result)

    if not temperatures:
        return {
            "tile_count": 0,
            "min_c": None,
            "mean_c": None,
            "max_c": None,
            "data_quality": "no_temperature_tiles",
        }

    return {
        "tile_count": len(temperatures),
        "min_c": min(temperatures),
        "mean_c": mean(temperatures),
        "max_c": max(temperatures),
        "data_quality": "validated",
    }


def summarize_analytic(result: dict) -> dict:
    stats = result.get(
        "stats_data",
        {},
    )

    return {
        "analytic_type": stats.get(
            "analytic_type"
        ),
        "units": stats.get("units"),
        "n_cells": stats.get("n_cells"),
        "min": stats.get("min"),
        "mean": stats.get("mean"),
        "max": stats.get("max"),
    }


def risk_from_metrics(
    peak,
    exceedance,
    persistence,
):
    score = 0

    if peak is not None:
        if peak >= 42:
            score += 60
        elif peak >= 38:
            score += 45
        elif peak >= 35:
            score += 30
        elif peak >= 32:
            score += 15

    if exceedance is not None:
        if exceedance >= 8:
            score += 25
        elif exceedance >= 4:
            score += 15
        elif exceedance >= 1:
            score += 8

    if persistence is not None:
        if persistence >= 6:
            score += 15
        elif persistence >= 3:
            score += 10
        elif persistence >= 1:
            score += 5

    score = min(score, 100)

    if score >= 70:
        level = "CRITICAL"
    elif score >= 50:
        level = "HIGH"
    elif score >= 25:
        level = "MODERATE"
    else:
        level = "LOW"

    return score, level


def build_recommendation(
    level,
    peak,
    threshold,
):
    if level == "CRITICAL":
        if peak is not None:
            return (
                f"Pause or substantially reschedule "
                f"intensive outdoor work during peak heat. "
                f"The investigated peak was "
                f"{peak:.1f}°C."
            )

        return (
            "Pause or substantially reschedule "
            "intensive outdoor work during peak heat."
        )

    if level == "HIGH":
        if peak is not None:
            return (
                f"Shift intensive outdoor work to cooler "
                f"hours and reduce exposure during peak "
                f"heat. Peak was {peak:.1f}°C."
            )

        return (
            "Shift intensive outdoor work to cooler "
            "hours."
        )

    if level == "MODERATE":
        return (
            "Continue with configured controls and "
            "active monitoring; prefer cooler operating "
            "hours where practical."
        )

    return (
        "Normal operations under the configured policy, "
        "with routine monitoring."
    )