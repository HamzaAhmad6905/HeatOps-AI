from __future__ import annotations

from heatops_ai.backend.fortyguard import FortyGuardClient


# Small Phoenix demonstration AOI.
# Keeping the polygon compact makes the demo faster
# and reduces unnecessary API work.

PHOENIX_AOI = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "name": "Phoenix Demo AOI"
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-112.095, 33.435],
                        [-112.055, 33.435],
                        [-112.055, 33.465],
                        [-112.095, 33.465],
                        [-112.095, 33.435],
                    ]
                ],
            },
        }
    ],
}


def create_heatmap(
    client: FortyGuardClient,
    start_date: str,
    start_time: str = "14:00",
):

    return client.create_heatmap(
        polygon_aoi=PHOENIX_AOI,
        start_date=start_date,
        start_time=start_time,
        filter_type=1,
        granularity=100,
        analytic_type="tcm",
        wait=True,
        poll_interval=3,
        timeout=600,
        verbose=False,
    )


def create_exceedance(
    client: FortyGuardClient,
    start_date: str,
    end_date: str,
    threshold: float,
):

    return client.create_heatmap(
        polygon_aoi=PHOENIX_AOI,
        start_date=start_date,
        end_date=end_date,
        filter_type=4,
        analytic_type="exceedance",
        threshold=threshold,
        direction="above",
        granularity=100,
        wait=True,
        poll_interval=3,
        timeout=600,
        verbose=False,
    )


def create_persistence(
    client: FortyGuardClient,
    start_date: str,
    end_date: str,
    threshold: float,
):

    return client.create_heatmap(
        polygon_aoi=PHOENIX_AOI,
        start_date=start_date,
        end_date=end_date,
        filter_type=4,
        analytic_type="persistence",
        threshold=threshold,
        direction="above",
        granularity=100,
        wait=True,
        poll_interval=3,
        timeout=600,
        verbose=False,
    )
