# SagarNetra REST and WebSocket API Specification
**Base URL:** `http://localhost:8000`  
**Protocol:** HTTP/1.1 & WebSocket  
**Version:** 1.0.0  

---

## 1. REST Endpoints

### 1.1 Surveys
* **`POST /api/surveys`**
  - Create a new hydrographic survey session.
  - *Request Body:*
    ```json
    {
      "survey_id": "SURVEY_2026_09",
      "site_name": "Chennai_Port",
      "swath_range_m": 75.0,
      "altitude_m": 12.0
    }
    ```
  - *Response:* `200 OK` with survey metadata.

* **`GET /api/surveys`**
  - List all recorded surveys with summary statistics.

### 1.2 Detections & Operator Reviews
* **`GET /api/targets?survey_id={id}`**
  - Fetch all detected targets for a survey, including physical dimensions, geotags, confidence scores, and rule audit logs.

* **`POST /api/review`**
  - Submit an operator review verdict (`CONFIRMED_HAZARD`, `FALSE_POSITIVE`, `SECOND_LOOK_REQUESTED`).
  - *Request Body:*
    ```json
    {
      "target_id": "SN-DET-001",
      "action": "CONFIRMED_HAZARD",
      "notes": "Verified float chain visible on starboard channel.",
      "reviewer": "Hydrographer-01",
      "timestamp": "2026-09-26T14:30:00Z"
    }
    ```

### 1.3 Reports & Multi-Format Exports
* **`GET /api/report?survey_id={id}&format={json|csv|geojson|kml|pdf}`**
  - Generate and stream full survey reports:
    - `pdf`: Dive-ready executive briefing with target crops, shadow profiles, rule logs, and $2 \times r_{95}$ search boxes.
    - `geojson`: FeatureCollection containing target points, $r_{95}$ error circles, and second-look track lines.
    - `kml`: Google Earth compatible placemarks and coverage tracks.
    - `csv`: Tabular spreadsheet for GIS ingestion.
    - `json`: Machine-readable raw inspection data.

### 1.4 Coverage & PoD Analysis
* **`GET /api/coverage?survey_id={id}`**
  - Return the 4-tier clearance map summary (cleared, adequate, marginal, inadequate km²), clearance percentage, and autonomous second-look infill waypoints.

### 1.5 Disaster Mode Comparison
* **`POST /api/change/disaster`**
  - Compare baseline pre-cyclone mosaic with post-cyclone survey.
  - Returns list of new underwater obstructions, displaced tetrapods, and navigation channel bathymetry shifts.

---

## 2. WebSocket Endpoints

* **`WS /ws/waterfall`**
  - High-throughput streaming channel for dual port/starboard waterfall pings.
  - Streaming rate: ~12 pings/sec.
  - *Message Format:*
    ```json
    {
      "ping_number": 104,
      "timestamp": 10.4,
      "altitude_m": 14.8,
      "heading_deg": 90.0,
      "port_samples": [24, 25, 30, ...],
      "stbd_samples": [26, 28, 35, ...],
      "detections": [
        {
          "target_id": "LIVE_0104",
          "channel": "stbd",
          "class_name": "ghost_net",
          "sample_idx": 220,
          "confidence": 84.5,
          "status": "CONFIRMED_HAZARD"
        }
      ]
    }
    ```
