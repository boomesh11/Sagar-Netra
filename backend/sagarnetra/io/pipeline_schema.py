"""
backend/sagarnetra/io/pipeline_schema.py
========================================
Pydantic v2 schemas for SagarNetra standalone pipeline output.
Ensures rigorous data contract compliance for detection reports,
physical measurements, evidence terms, and navigation status.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, model_validator
from backend.sagarnetra.preprocess.modality import ModalityCheckResult


class BoundingBoxPx(BaseModel):
    row_min: int = Field(..., ge=0, description="Top row coordinate")
    col_min: int = Field(..., ge=0, description="Left column coordinate")
    row_max: int = Field(..., ge=0, description="Bottom row coordinate")
    col_max: int = Field(..., ge=0, description="Right column coordinate")


class Dimensions(BaseModel):
    length_px: float = Field(..., ge=0.0, description="Along-track length in pixels")
    width_px: float = Field(..., ge=0.0, description="Across-track width in pixels")
    length_m: Optional[float] = Field(None, ge=0.0, description="Physical length in metres (null if resolution unknown)")
    width_m: Optional[float] = Field(None, ge=0.0, description="Physical width in metres (null if resolution unknown)")


class UTMCoordinates(BaseModel):
    easting: float = Field(..., description="UTM Easting in metres")
    northing: float = Field(..., description="UTM Northing in metres")
    zone: int = Field(..., ge=1, le=60, description="UTM Zone number")
    hemisphere: str = Field("N", description="'N' or 'S'")


class GeoPosition(BaseModel):
    status: str = Field(..., description="'AVAILABLE' or 'UNAVAILABLE'")
    lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description="WGS84 latitude (null if UNAVAILABLE)")
    lon: Optional[float] = Field(None, ge=-180.0, le=180.0, description="WGS84 longitude (null if UNAVAILABLE)")
    utm: Optional[UTMCoordinates] = Field(None, description="UTM projected coordinates (null if UNAVAILABLE)")

    @model_validator(mode="after")
    def check_honesty(self) -> GeoPosition:
        if self.status == "UNAVAILABLE":
            if self.lat is not None or self.lon is not None or self.utm is not None:
                raise ValueError("Honesty violation: coordinates must be null when status is UNAVAILABLE")
        return self


class EchoSiftEvidenceReport(BaseModel):
    cnn_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    snr_score: float = Field(0.5, ge=0.0, le=1.0)
    shc_score: float = Field(..., ge=0.0, le=1.0)
    height_estimate_m: Optional[float] = Field(None, ge=0.0)
    shadow_side: str = Field(..., description="'correct' or 'incorrect'")
    regularity_score: float = Field(..., ge=0.0, le=1.0)
    is_sand_ripple: bool
    motion_penalty: float = Field(..., ge=0.0, le=1.0)
    persistence_score: float = Field(..., ge=0.0, le=1.0)
    pass_count: int = Field(1, ge=1)
    fused_confidence: float = Field(..., ge=0.0, le=100.0)
    suppressed: bool
    suppression_reason: Optional[str] = None
    s_net: Optional[float] = Field(None, ge=0.0, le=1.0)


class DetectionOutput(BaseModel):
    id: str = Field(..., description="Unique detection identifier")
    bbox_px: BoundingBoxPx = Field(..., description="Pixel bounding box [row_min, col_min, row_max, col_max]")
    class_name: str = Field(..., alias="class", description="Debris class name")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Calibrated confidence percentage")
    decision: str = Field(..., description="Target decision: <class> | unknown_manmade | natural_suppressed | uncertain | invalid_input")
    decision_reason: str = Field(..., description="Acoustic physics explanation for decision")
    evidence: EchoSiftEvidenceReport = Field(..., description="Full 5-term EchoSift evidence components")
    height_m: Optional[float] = Field(None, ge=0.0, description="Height in metres (null if no towfish altitude)")
    dims: Dimensions = Field(..., description="Target dimensions in pixels and metres")
    geo: GeoPosition = Field(..., description="Geographical position (UNAVAILABLE without navigation)")
    quality_overlap_pct: float = Field(..., ge=0.0, le=100.0, description="% overlap with motion-artifact/dropout mask")
    raw_candidate_source: str = Field("OS_CFAR", description="Candidate generator source ('OS_CFAR', 'YOLO', etc.)")

    model_config = {"populate_by_name": True}


class QualitySummary(BaseModel):
    total_rows: int
    flagged_rows_pct: float
    valid_pixels_pct: float


class PreprocessingSummary(BaseModel):
    nadir_column: Optional[int] = None
    resolution_m_per_px: Optional[float] = None
    quality: QualitySummary


class PipelineReport(BaseModel):
    status: str = Field(..., description="'SUCCESS' | 'INVALID_INPUT' | 'ERROR'")
    image_path: str
    nav_path: Optional[str] = None
    image_shape: Tuple[int, int]  # (height, width)
    modality: ModalityCheckResult
    preprocessing: Optional[PreprocessingSummary] = None
    detection_count: int
    detections: List[DetectionOutput] = Field(default_factory=list)
    overlay_path: Optional[str] = None
