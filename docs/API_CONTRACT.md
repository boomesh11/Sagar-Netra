# EchoSift / SagarNetra API Contract

This document specifies the exact JSON contract between the frontend marine-survey workstation and the Python FastAPI backend for EchoSift physics-verified detections.

---

## Endpoint: `GET /api/echosift/detections`

### Response Payload Schema
```json
{
  "surveyId": "SRV_CHENNAI_LINE_07",
  "surveyName": "Chennai Coast Line 07",
  "edgeMode": "shore",
  "edgeTelemetry": {
    "tilesPerSec": 18.5,
    "latencyMs": 42.1,
    "modelSizeMb": 6.8,
    "activeModules": [
      "Slant-Range Correction",
      "Enhanced Lee Despeckle",
      "Motion-Artifact Mask",
      "YOLOv8n / SegNet INT8",
      "Shadow-Highlight Consistency (SHC)",
      "Geometric Regularity Index (GRI)",
      "Multi-Pass Persistence",
      "5-Term Calibrated Fusion"
    ]
  },
  "detections": [
    {
      "id": "TGT-001",
      "class": "ghost_net",
      "confidence": 91.2,
      "evidence": {
        "cnn": 0.84,
        "shc": 0.92,
        "regularity": 0.78,
        "motionPenalty": 0.0,
        "persistence": 0.85
      },
      "heightEstimateM": 1.2,
      "shadowSide": "correct",
      "bbox": {
        "pingStart": 142,
        "pingEnd": 168,
        "rangeStartPx": 210,
        "rangeEndPx": 245
      },
      "geo": {
        "lat": 13.08512,
        "lon": 80.29841,
        "widthM": 2.1,
        "lengthM": 5.4
      },
      "passes": [
        "SRV_CHENNAI_LINE_07",
        "SRV_CHENNAI_LINE_08"
      ],
      "suppressed": false,
      "suppressionReason": null
    },
    {
      "id": "TGT-002",
      "class": "dark_sediment_patch",
      "confidence": 12.0,
      "evidence": {
        "cnn": 0.88,
        "shc": 0.10,
        "regularity": 0.32,
        "motionPenalty": 0.0,
        "persistence": 0.45
      },
      "heightEstimateM": 0.0,
      "shadowSide": "correct",
      "bbox": {
        "pingStart": 310,
        "pingEnd": 335,
        "rangeStartPx": 180,
        "rangeEndPx": 215
      },
      "geo": {
        "lat": 13.08410,
        "lon": 80.29650,
        "widthM": 3.0,
        "lengthM": 4.2
      },
      "passes": [
        "SRV_CHENNAI_LINE_07"
      ],
      "suppressed": true,
      "suppressionReason": "shadow implies height 0.0 m (flat sediment patch)"
    },
    {
      "id": "TGT-003",
      "class": "dropout_artifact",
      "confidence": 8.5,
      "evidence": {
        "cnn": 0.79,
        "shc": 0.40,
        "regularity": 0.25,
        "motionPenalty": 0.62,
        "persistence": 0.30
      },
      "heightEstimateM": 0.4,
      "shadowSide": "correct",
      "bbox": {
        "pingStart": 450,
        "pingEnd": 462,
        "rangeStartPx": 95,
        "rangeEndPx": 130
      },
      "geo": {
        "lat": 13.08220,
        "lon": 80.29410,
        "widthM": 1.2,
        "lengthM": 6.8
      },
      "passes": [
        "SRV_CHENNAI_LINE_07"
      ],
      "suppressed": true,
      "suppressionReason": "62% overlap with motion mask (heave/pitch collapse)"
    }
  ],
  "suppressionStats": {
    "totalCnnCandidates": 3,
    "verifiedHazards": 1,
    "suppressedFalsePositives": 2,
    "suppressionRatePct": 66.7
  }
}
```

---

## Evidence Formulation & Calibration

The calibrated confidence $C$ is computed via a fitted 6-parameter logistic regression:

$$ C = \sigma\big(w_0 + w_1 \cdot z_{cnn} + w_2 \cdot z_{shc} + w_3 \cdot z_{reg} - w_4 \cdot z_{motion} + w_5 \cdot z_{persist}\big) $$

- $z_{cnn}$: Raw CNN proposal probability $\in [0, 1]$
- $z_{shc}$: Shadow-Highlight Consistency score $\in [0, 1]$ based on $h = \frac{L_s \cdot H}{R + L_s}$
- $z_{reg}$: Geometric Regularity Index $\in [0, 1]$ (straightness + 2D FFT periodicity contrasted against 3x neighbourhood)
- $z_{motion}$: Fraction of detection overlapping heave/pitch/roll collapse mask $\in [0, 1]$
- $z_{persist}$: Multi-pass persistence score across overlapping survey tracks ($\le 5\text{ m}$ tolerance)
