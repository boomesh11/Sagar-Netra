"""
backend/sagarnetra/api/schemas.py
==================================
Pydantic v2 schemas defining the contract for SagarNetra analysis API.
Ensures strict synchronization between Python analysis engine and Next.js frontend.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, model_validator


class BoundingBoxPx(BaseModel):
    row_min: int = Field(..., ge=0, description="Top row coordinate")
    col_min: int = Field(..., ge=0, description="Left column coordinate")
    row_max: int = Field(..., ge=0, description="Bottom row coordinate")
    col_max: int = Field(..., ge=0, description="Right column coordinate")


class Dimensions(BaseModel):
    length_px: float = Field(..., ge=0.0, description="Along-track length in pixels")
    width_px: float = Field(..., ge=0.0, description="Across-track width in pixels")
    length_m: Optional[float] = Field(None, ge=0.0, description="Length in metres (null if uncalibrated/no nav)")
    width_m: Optional[float] = Field(None, ge=0.0, description="Width in metres (null if uncalibrated/no nav)")


class UTMCoordinates(BaseModel):
    easting: float = Field(..., description="UTM Easting in metres")
    northing: float = Field(..., description="UTM Northing in metres")
    zone: int = Field(..., ge=1, le=60, description="UTM Zone number")
    hemisphere: str = Field("N", description="'N' or 'S'")


class GeoPosition(BaseModel):
    status: str = Field(..., description="'AVAILABLE' or 'UNAVAILABLE'")
    lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description="WGS84 latitude")
    lon: Optional[float] = Field(None, ge=-180.0, le=180.0, description="WGS84 longitude")
    utm: Optional[UTMCoordinates] = Field(None, description="UTM projected coordinates")
    source: Optional[str] = Field(None, description="'SYNTHETIC_NAV_TEST', 'VESSEL_INS', or null")

    @model_validator(mode="after")
    def check_honesty(self) -> GeoPosition:
        if self.status == "UNAVAILABLE":
            if self.lat is not None or self.lon is not None or self.utm is not None:
                raise ValueError("Honesty violation: coordinates must be null when status is UNAVAILABLE")
        return self


class PipelineStage(BaseModel):
    step: int = Field(..., description="Stage step number (1-based)")
    name: str = Field(..., description="Stage display name")
    status: str = Field(..., description="'COMPLETED', 'SKIPPED', 'RUNNING', 'FAILED'")
    duration_ms: float = Field(..., ge=0.0, description="Actual execution time in milliseconds")
    details: Optional[str] = Field(None, description="Diagnostic / telemetry details")


class RawCandidate(BaseModel):
    id: str = Field(..., description="Raw candidate identifier")
    source: str = Field(..., description="'OS_CFAR', 'PATCHCORE', 'YOLO_V8'")
    bbox_px: BoundingBoxPx = Field(..., description="Candidate pixel bounding box")
    raw_score: float = Field(..., description="Raw detection confidence / SNR score")
    raw_class: str = Field(..., description="Provisional candidate class")
    has_shadow: bool = Field(False, description="Whether an acoustic shadow was paired")
    snr_db: float = Field(0.0, description="Acoustic SNR in decibels")


class TargetEvidence(BaseModel):
    cnn_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Detector score (null when detector does not run)")
    snr_score: float = Field(..., ge=0.0, le=1.0, description="Acoustic SNR evidence term")
    shc_score: float = Field(..., ge=0.0, le=1.0)
    height_estimate_m: Optional[float] = Field(None, ge=0.0)
    shadow_side: str = Field(..., description="'correct', 'incorrect', or 'absent'")
    regularity_score: float = Field(..., ge=0.0, le=1.0)
    is_sand_ripple: bool = Field(False)
    motion_penalty: float = Field(..., ge=0.0, le=1.0)
    persistence_score: float = Field(..., ge=0.0, le=1.0)
    pass_count: int = Field(1, ge=1)
    fused_confidence: float = Field(..., ge=0.0, le=100.0)
    suppressed: bool = Field(False)
    suppression_reason: Optional[str] = None
    s_net: Optional[float] = Field(None, ge=0.0, le=1.0)
    annular_contrast: Optional[float] = Field(None, ge=0.0, le=1.0)
    anomaly_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    anthropogenic_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class TargetOutput(BaseModel):
    id: str = Field(..., description="Unique target identifier")
    target_id: Optional[str] = Field(None, description="Legacy alias for id")
    class_name: str = Field(..., description="Target class")
    confidence: float = Field(..., ge=0.0, le=100.0, description="0-100 fused confidence")
    decision: str = Field(..., description="wreck | pipe_cylinder | net_debris | other_manmade | unknown_manmade | natural_suppressed | uncertain")
    decision_reason: str = Field(..., description="Plain-English explanation built from actual evidence values")
    evidence: TargetEvidence = Field(..., description="Full evidence components")
    bbox_px: BoundingBoxPx = Field(..., description="Bounding box [row_min, col_min, row_max, col_max]")
    dims: Dimensions = Field(..., description="Target dimensions")
    geo: GeoPosition = Field(..., description="Geographical position")
    height_m: Optional[float] = Field(None, description="Metric height (null if altitude unavailable)")
    quality_overlap_pct: float = Field(..., ge=0.0, le=100.0, description="% overlap with low-quality mask")
    raw_candidate_source: str = Field("OS_CFAR", description="Generator source")
    merged_count: int = Field(1, ge=1, description="Number of grouped raw fragments")
    position: Optional[Dict[str, Any]] = Field(None, description="Legacy compatibility mirror of geo")
    dimensions: Optional[Dict[str, Any]] = Field(None, description="Legacy compatibility mirror of dims")


class SummaryCounts(BaseModel):
    total_candidates: int = Field(..., ge=0)
    verified_count: int = Field(..., ge=0)
    suppressed_count: int = Field(..., ge=0)
    uncertain_count: int = Field(..., ge=0)
    by_class: Dict[str, int] = Field(default_factory=dict)


class AnalyzeSurveyInfo(BaseModel):
    id: str
    name: str
    source_file: str
    swath_range_m: float
    altitude_m: Optional[float] = None
    has_nav: bool = False
    created_at: str


class AnalyzeResponse(BaseModel):
    status: str = Field(..., description="'ANALYSIS_COMPLETE', 'INVALID_INPUT', 'ERROR'")
    survey: AnalyzeSurveyInfo
    stages: List[PipelineStage] = Field(default_factory=list)
    raw_candidates: List[RawCandidate] = Field(default_factory=list)
    targets: List[TargetOutput] = Field(default_factory=list)
    summary: SummaryCounts
    detector_status: str = Field("NOT_TRAINED", description="'NOT_TRAINED' | 'TRAINED' | 'DISABLED'")
    calibration_status: str = Field("uncalibrated", description="'uncalibrated' | 'calibrated'")
    geo_status: str = Field("UNAVAILABLE", description="'AVAILABLE' | 'UNAVAILABLE'")
    warnings: List[str] = Field(default_factory=list)
    modality: Optional[Dict[str, Any]] = None
    overlay_url: Optional[str] = None
    image_shape: Optional[Tuple[int, int]] = None
    error: Optional[str] = None
    message: Optional[str] = None
    mode: Optional[str] = Field("IMAGE_ONLY", description="Compatibility mode: IMAGE_ONLY | HYDROGRAPHIC_SURVEY")
    input: Optional[Dict[str, Any]] = Field(None, description="Input survey metadata")
    pipeline_stages: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Legacy 20-stage pipeline list")

