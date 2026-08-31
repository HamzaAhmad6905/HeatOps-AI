"use strict";

/*
 * HeatOps AI frontend
 * -----------------------------------------
 * Talks to:
 *   POST /api/investigate
 *
 * The backend may return slightly different
 * response shapes, so this UI safely handles
 * missing fields instead of crashing.
 */

let map = null;
let layer = null;


// --------------------------------------------------
// Helpers
// --------------------------------------------------

function $(id) {
    return document.getElementById(id);
}


function escapeHtml(value) {
    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function formatNumber(value, decimals = 1) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }

    const number = Number(value);

    if (!Number.isFinite(number)) {
        return escapeHtml(value);
    }

    return number.toFixed(decimals);
}


function formatTemperature(value) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }

    const number = Number(value);

    if (!Number.isFinite(number)) {
        return escapeHtml(value);
    }

    return `${number.toFixed(1)}°C`;
}


// --------------------------------------------------
// Timeline event renderer
// --------------------------------------------------

function event(stage, status, detail) {

    const safeStatus = status || "running";

    let cls = "run";
    let icon = "●";

    if (safeStatus === "completed" || safeStatus === "success") {
        cls = "ok";
        icon = "✓";
    }

    if (safeStatus === "failed" || safeStatus === "error") {
        cls = "bad";
        icon = "✕";
    }

    return `
        <div class="event">
            <b class="${cls}">
                ${icon} ${escapeHtml(stage || "Investigation")}
            </b>

            <span>
                ${escapeHtml(detail || "")}
            </span>
        </div>
    `;
}


// --------------------------------------------------
// Map initialization
// --------------------------------------------------

function initializeMap() {

    if (typeof L === "undefined") {
        console.error("Leaflet was not loaded.");
        return;
    }

    const mapElement = $("map");

    if (!mapElement) {
        console.error("Map element was not found.");
        return;
    }

    map = L
        .map("map")
        .setView(
            [33.4484, -112.074],
            12
        );

    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            maxZoom: 19,
            attribution: "© OpenStreetMap"
        }
    ).addTo(map);
}


// --------------------------------------------------
// Draw heatmap
// --------------------------------------------------

function drawMap(mapData) {

    if (!map || typeof L === "undefined") {
        return;
    }

    if (layer) {
        map.removeLayer(layer);
        layer = null;
    }

    if (
        !mapData ||
        typeof mapData !== "object" ||
        !Array.isArray(mapData.features) ||
        mapData.features.length === 0
    ) {
        console.log("No map data available.");
        return;
    }

    console.log(
        "Map data available:",
        true
    );

    console.log(
        "Map data keys:",
        Object.keys(mapData)
    );

    console.log(
        "Number of features:",
        mapData.features.length
    );

    layer = L.geoJSON(
        mapData,
        {
            style: function(feature) {

                const properties =
                    feature &&
                    feature.properties
                        ? feature.properties
                        : {};

                const temperature =
                    properties.average_temperature ??
                    properties.temperature ??
                    properties.avg_temperature ??
                    0;

                const t = Number(temperature);

                let fillColor = "#55d6be";

                if (t >= 42) {
                    fillColor = "#ff3b30";
                }
                else if (t >= 38) {
                    fillColor = "#ff7a18";
                }
                else if (t >= 35) {
                    fillColor = "#ffd166";
                }

                return {
                    color: "#18262e",
                    weight: 0.5,
                    fillColor: fillColor,
                    fillOpacity: 0.65
                };
            },

            onEachFeature: function(feature, featureLayer) {

                const properties =
                    feature &&
                    feature.properties
                        ? feature.properties
                        : {};

                const tileId =
                    properties.tile_id ??
                    properties.id ??
                    "";

                const averageTemperature =
                    properties.average_temperature ??
                    properties.temperature ??
                    properties.avg_temperature ??
                    null;

                featureLayer.bindPopup(
                    `
                    <strong>Heat Tile ${escapeHtml(tileId)}</strong>
                    <br>
                    Average: ${formatTemperature(averageTemperature)}
                    `
                );
            }
        }
    );

    layer.addTo(map);

    try {
        const bounds = layer.getBounds();

        if (bounds.isValid()) {
            map.fitBounds(
                bounds,
                {
                    padding: [20, 20]
                }
            );
        }
    }
    catch (error) {
        console.warn(
            "Could not fit map bounds:",
            error
        );
    }
}


// --------------------------------------------------
// Safely extract risk summary
// --------------------------------------------------

function getRiskSummary(data) {

    if (!data || typeof data !== "object") {
        return {};
    }

    /*
     * Backend may return:
     *
     * risk_summary
     * risk
     * summary
     *
     * We support all three.
     */

    if (
        data.risk_summary &&
        typeof data.risk_summary === "object"
    ) {
        return data.risk_summary;
    }

    if (
        data.risk &&
        typeof data.risk === "object"
    ) {
        return data.risk;
    }

    if (
        data.summary &&
        typeof data.summary === "object"
    ) {
        return data.summary;
    }

    return {};
}


// --------------------------------------------------
// Update dashboard cards
// --------------------------------------------------

function updateDashboard(data) {

    const riskSummary =
        getRiskSummary(data);


    // ----------------------------------------------
    // Risk
    // ----------------------------------------------

    const riskLevel =
        riskSummary.level ??
        riskSummary.risk_level ??
        data.risk_level ??
        data.risk ??
        "—";

    $("risk").textContent =
        String(riskLevel);


    const score =
        riskSummary.score ??
        riskSummary.risk_score ??
        data.risk_score ??
        data.score ??
        null;

    $("score").textContent =
        score === null
            ? "Risk score —"
            : `Risk score ${formatNumber(score, 0)}/100`;


    // ----------------------------------------------
    // Peak temperature
    // ----------------------------------------------

    const peak =
        riskSummary.peak_c ??
        riskSummary.peak_temperature ??
        data.peak_c ??
        data.peak_temperature ??
        null;

    $("peak").textContent =
        formatTemperature(peak);


    // ----------------------------------------------
    // Peak time
    // ----------------------------------------------

    let peakTime = "—";

    if (
        Array.isArray(data.peak_periods) &&
        data.peak_periods.length > 0
    ) {

        const firstPeak =
            data.peak_periods[0];

        if (firstPeak) {

            const date =
                firstPeak.date ??
                firstPeak.start_date ??
                "";

            const time =
                firstPeak.time ??
                firstPeak.start_time ??
                "";

            peakTime =
                `${date} ${time}`.trim() ||
                "—";
        }
    }

    if (
        peakTime === "—" &&
        data.peak_time
    ) {
        peakTime =
            String(data.peak_time);
    }

    $("peakTime").textContent =
        peakTime;


    // ----------------------------------------------
    // Exceedance
    // ----------------------------------------------

    const exceedance =
        riskSummary.exceedance_hours ??
        riskSummary.exceedance ??
        data.exceedance_hours ??
        data.exceedance ??
        null;

    $("exceed").textContent =
        exceedance === null
            ? "—"
            : formatNumber(exceedance, 1);


    // ----------------------------------------------
    // Persistence
    // ----------------------------------------------

    const persistence =
        riskSummary.persistence_hours ??
        riskSummary.persistence ??
        data.persistence_hours ??
        data.persistence ??
        null;

    $("persist").textContent =
        persistence === null
            ? "—"
            : formatNumber(persistence, 1);


    // ----------------------------------------------
    // Recommendation
    // ----------------------------------------------

    let recommendation =
        null;


    if (
        Array.isArray(data.recommendations) &&
        data.recommendations.length > 0
    ) {

        const first =
            data.recommendations[0];

        if (typeof first === "string") {
            recommendation = first;
        }
        else if (
            first &&
            typeof first === "object"
        ) {
            recommendation =
                first.action ??
                first.recommendation ??
                first.text ??
                first.message ??
                null;
        }
    }


    if (
        !recommendation &&
        typeof data.recommendation === "string"
    ) {
        recommendation =
            data.recommendation;
    }


    if (
        !recommendation &&
        typeof data.recommended_action === "string"
    ) {
        recommendation =
            data.recommended_action;
    }


    if (!recommendation) {
        recommendation =
            "Investigation completed. Review the evidence and operating-window results.";
    }


    $("recommendation").textContent =
        recommendation;
}


// --------------------------------------------------
// Render investigation trace
// --------------------------------------------------

function renderTrace(data) {

    const trace =
        Array.isArray(data.investigation_trace)
            ? data.investigation_trace
            : [];

    if (trace.length === 0) {

        $("timeline").innerHTML =
            event(
                "Investigation",
                "completed",
                "Investigation completed successfully."
            );

    }
    else {

        $("timeline").innerHTML =
            trace
                .map(function(item) {

                    if (!item) {
                        return "";
                    }

                    return event(
                        item.stage ??
                        item.name ??
                        "Investigation",

                        item.status ??
                        "completed",

                        item.detail ??
                        item.message ??
                        item.activity_id ??
                        ""
                    );
                })
                .join("");
    }


    $("trace").textContent =
        JSON.stringify(
            data,
            null,
            2
        );
}


// --------------------------------------------------
// Handle backend errors
// --------------------------------------------------

async function readError(response) {

    try {

        const data =
            await response.json();

        if (
            data &&
            typeof data.detail === "string"
        ) {
            return data.detail;
        }

        if (
            data &&
            typeof data.message === "string"
        ) {
            return data.message;
        }

        if (
            data &&
            data.error &&
            typeof data.error.message === "string"
        ) {
            return data.error.message;
        }

        return JSON.stringify(data);

    }
    catch (error) {

        try {
            return await response.text();
        }
        catch (textError) {
            return "Investigation failed.";
        }
    }
}


// --------------------------------------------------
// Run investigation
// --------------------------------------------------

async function runInvestigation() {

    const missionElement =
        $("mission");

    const button =
        $("run");


    if (!missionElement || !button) {
        console.error(
            "Mission input or run button not found."
        );
        return;
    }


    const mission =
        missionElement.value.trim();


    if (!mission) {

        $("timeline").innerHTML =
            event(
                "Mission",
                "failed",
                "Please enter a mission before investigating."
            );

        return;
    }


    // ----------------------------------------------
    // Disable button
    // ----------------------------------------------

    button.disabled = true;

    button.textContent =
        "INVESTIGATING…";


    // ----------------------------------------------
    // Initial trace
    // ----------------------------------------------

    $("timeline").innerHTML =
        event(
            "RECEIVED",
            "completed",
            "Mission received and structured."
        )
        +
        event(
            "PLANNING",
            "completed",
            "Selecting required evidence."
        )
        +
        event(
            "VALIDATING",
            "running",
            "Validating investigation requirements."
        );


    try {

        // ------------------------------------------
        // API request
        // ------------------------------------------

        const response =
            await fetch(
                "/api/investigate",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        mission: mission
                    })
                }
            );


        // ------------------------------------------
        // Handle HTTP errors
        // ------------------------------------------

        if (!response.ok) {

            const errorMessage =
                await readError(response);

            throw new Error(
                errorMessage ||
                `Investigation failed (${response.status})`
            );
        }


        // ------------------------------------------
        // Parse JSON
        // ------------------------------------------

        const data =
            await response.json();


        console.log(
            "Investigation response:",
            data
        );


        // ------------------------------------------
        // Validate response
        // ------------------------------------------

        if (
            !data ||
            typeof data !== "object"
        ) {
            throw new Error(
                "Backend returned an invalid response."
            );
        }


        // ------------------------------------------
        // Render backend trace
        // ------------------------------------------

        renderTrace(data);


        // ------------------------------------------
        // Update dashboard
        // ------------------------------------------

        updateDashboard(data);


        // ------------------------------------------
        // Update map
        // ------------------------------------------

        if (data.map_data) {
            drawMap(data.map_data);
        }
        else {
            console.log(
                "Backend did not return map_data."
            );
        }


    }
    catch (error) {

        console.error(
            "Investigation error:",
            error
        );


        $("timeline").innerHTML +=
            event(
                "Investigation",
                "failed",
                error.message ||
                "Unknown investigation error."
            );


        $("recommendation").textContent =
            "No recommendation was generated because the investigation failed.";


        $("trace").textContent =
            error.stack ||
            error.message ||
            String(error);
    }


    finally {

        button.disabled = false;

        button.textContent =
            "INVESTIGATE";
    }
}


// --------------------------------------------------
// Page startup
// --------------------------------------------------

document.addEventListener(
    "DOMContentLoaded",
    function() {

        initializeMap();


        const button =
            $("run");


        if (button) {

            button.addEventListener(
                "click",
                runInvestigation
            );
        }


        console.log(
            "HeatOps AI frontend initialized."
        );
    }
);