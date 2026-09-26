"""
SagarNetra IO Schema — Pydantic v2 data contracts.
All data flowing through the system is validated against these models.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field, model_validator


# ── Enumerations ──────────────────────────────────────────────────────────────

class DataSource(str, Enum):
    SIM = "sim"
    HYBRID = "hybrid"
    REAL = "real"


class PingFlag(str, Enum):
    DROPOUT = "dropout"
    NAV_MISSING = "nav_missing"
    ALTITUDE_JUMP = "altitude_jump"
    ATTITUDE_EXCESS = "attitude_excess"


class PingFlags(BaseModel):
    dropout: bool = False
    nav_missing: bool = False
    altitude_jump: bool = False
    attitude_excess: bool = False

    def to_flag_list(self) -> list[PingFlag]:
        out = []
        if self.dropout:
            out.append(PingFlag.DROPOUT)
        if self.nav_missing:
            out.append(PingFlag.NAV_MISSING)
        if self.altitude_jump:
            out.append(PingFlag.ALTITUDE_JUMP)
        if self.attitude_excess:
            out.append(PingFlag.ATTITUDE_EXCESS)
        return out


class DetectionStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    LOW_EVIDENCE = "LOW_EVIDENCE"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNSURE = "unsure"


class HazardClass(str, Enum):
    GHOST_NET = "ghost_net"
    ROPE_CABLE = "rope_cable"
    PIPE = "pipe"
    CYLINDER = "cylinder"
    WRECK_DEBRIS = "wreck_debris"
    TRAP_POT = "trap_pot"
    UNKNOWN_MANMADE = "unknown_manmade"


class ConfuserClass(str, Enum):
    ROCK_CLUSTER = "rock_cluster"
    SAND_RIPPLE = "sand_ripple"
    SEAGRASS = "seagrass"
    FISH_SCHOOL = "fish_school"
    BIOLOGIC_MOUND = "biologic_mound"


class CoverageState(str, Enum):
    NOT_SURVEYED = "NOT_SURVEYED"
    INSUFFICIENT = "INSUFFICIENT"
    SURVEYED_CLEAR = "SURVEYED_CLEAR"
    CANDIDATE = "CANDIDATE"


# ── Core Models ───────────────────────────────────────────────────────────────

class Ping(BaseModel):
    """Single sonar ping with navigation and raw samples."""
    model_config = {"arbitrary_types_allowed": True}

    ping_id: int
    timestamp_utc: float  # Unix timestamp seconds
    ship_lat: Optional[float] = None
    ship_lon: Optional[float] = None
    heading_deg: float = 0.0
    cog_deg: float = 0.0
    speed_mps: float = 0.0
    altitude_m: float = 5.0
    depth_m: float = 10.0
    heave_m: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    yaw_deg: float = 0.0
    cable_out_m: Optional[float] = None
    layback_m: Optional[float] = None
    sound_speed_mps: float = 1500.0
    sample_interval_s: float = Field(default=1e-5, gt=0)
    frequency_hz: float = 450_000.0
    range_m: float = 50.0
    port: Optional[list[int]] = None   # uint16 samples
    stbd: Optional[list[int]] = None   # uint16 samples
    flags: list[PingFlag] = Field(default_factory=list)


class Survey(BaseModel):
    """Top-level survey metadata."""
    survey_id: str
    sensor_model: str = "unknown"
    frequency_hz: float = 450_000.0
    range_m: float = 50.0
    crs: str = "EPSG:4326"
    files: list[str] = Field(default_factory=list)
    start_utc: Optional[float] = None
    end_utc: Optional[float] = None
    line_ids: list[str] = Field(default_factory=list)


class RuleVerdict(BaseModel):
    rule: str
    verdict: int  # +1 consistent, 0 not assessable, -1 inconsistent
    reason: str


class ConfidenceComponents(BaseModel):
    p_cal: float = Field(ge=0.0, le=1.0)
    q_obs: float = Field(ge=0.0, le=1.0)
    v_phys: float = Field(ge=-1.0, le=1.0)
    s_net: float = Field(ge=0.0, le=1.0)
    position_certainty: float = Field(ge=0.0, le=1.0)


class Position(BaseModel):
    lat: Optional[float] = None
    lon: Optional[float] = None
    crs: str = "EPSG:4326"
    r95_m: Optional[float] = None
    method: Optional[str] = None
    position_reason: Optional[str] = None  # if null, explain why


class Dimensions(BaseModel):
    length_m: Optional[float] = None
    width_m: Optional[float] = None
    height_m: Optional[float] = None
    area_m2: Optional[float] = None
    orientation_deg: Optional[float] = None


class BBoxPx(BaseModel):
    side: str  # "port" or "stbd"
    ping_start: int
    ping_end: int
    sample_start: int
    sample_end: int


class ReviewInfo(BaseModel):
    status: ReviewStatus = ReviewStatus.UNREVIEWED
    reviewer: Optional[str] = None
    note: Optional[str] = None


class Detection(BaseModel):
    """Full detection record as output by the pipeline."""
    id: str
    cls: HazardClass
    subtype: Optional[str] = None
    status: DetectionStatus
    hazard_confidence: float = Field(ge=0.0, le=100.0)
    components: Optional[ConfidenceComponents] = None
    rule_log: list[RuleVerdict] = Field(default_factory=list)
    position: Optional[Position] = None
    dimensions: Optional[Dimensions] = None
    bbox_px: Optional[BBoxPx] = None
    polygon_wgs84: Optional[list[tuple[float, float]]] = None
    views: int = 1
    first_seen_utc: Optional[float] = None
    source_file: Optional[str] = None
    source: DataSource = DataSource.SIM
    priority: float = 0.0
    recommended_action: str = "investigate"
    review: ReviewInfo = Field(default_factory=ReviewInfo)


class Tile(BaseModel):
    """A 512×512 preprocessed tile fed to the detector."""
    model_config = {"arbitrary_types_allowed": True}

    tile_id: str
    survey_id: str
    side: str  # "port" or "stbd"
    ping_start: int
    ping_end: int
    ground_res_m: float = 0.10
    # Arrays stored separately (numpy), just metadata here
    quality_mask: Optional[list[list[bool]]] = None


class CoverageCell(BaseModel):
    """1 m² seabed cell with PoD state."""
    easting_m: float
    northing_m: float
    pod_net: float = 0.0
    pod_cyl: float = 0.0
    state: CoverageState = CoverageState.NOT_SURVEYED
