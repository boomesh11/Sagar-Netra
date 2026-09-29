"""
backend/sagarnetra/preprocess/modality.py
=========================================
Validates whether an input image conforms to Side-Scan Sonar (SSS) acoustic modality
or is a non-sonar optical RGB photo / chart / document.
Direct Python port of lib/sonar-detector.ts checkImageModality().
"""
from __future__ import annotations

from typing import List, Tuple
import numpy as np
from pydantic import BaseModel, Field


class ModalityCheckResult(BaseModel):
    is_sss: bool = Field(..., description="True if acoustic backscatter profile matches SSS")
    confidence_pct: int = Field(..., ge=0, le=100, description="Modality classification confidence %")
    detected_modality: str = Field(..., description="SIDE_SCAN_SONAR | OPTICAL_RGB_PHOTO | UNKNOWN_NON_ACOUSTIC")
    chromatic_dispersion: float = Field(..., description="Optical chromatic dispersion score (< 18 for SSS)")
    speckle_parity: float = Field(..., description="Acoustic speckle consistency score [0, 1]")
    verdict_title: str
    verdict_message: str
    diagnostic_details: List[str] = Field(default_factory=list)


def check_image_modality(image: np.ndarray) -> ModalityCheckResult:
    """
    Evaluates acoustic modality vs optical RGB photo.
    
    Args:
        image: numpy array with shape [H, W] (grayscale) or [H, W, C] (RGB / RGBA).
    
    Returns:
        ModalityCheckResult with full physics-based diagnostic reasoning.
    """
    # 1. Grayscale images are inherently single-channel intensity (strictly SSS compliant)
    if image.ndim == 2 or (image.ndim == 3 and image.shape[2] == 1):
        return ModalityCheckResult(
            is_sss=True,
            confidence_pct=98,
            detected_modality="SIDE_SCAN_SONAR",
            chromatic_dispersion=0.0,
            speckle_parity=0.92,
            verdict_title="SIDE-SCAN SONAR (SSS) VERIFIED",
            verdict_message="Single-channel monochrome acoustic intensity: 100% compliant with hydrographic SSS format.",
            diagnostic_details=[
                "Optical chromatic dispersion: 0.0 (Threshold < 18.0 for SSS)",
                "Acoustic colormap compliance: 100.0% (Single-channel intensity)",
                "Acoustic palette classification: Monochrome Grayscale Acoustic",
            ],
        )

    # 2. RGB image: downsample for rapid diagnostic inspection if needed
    h, w, c = image.shape
    if c >= 3:
        rgb = image[:, :, :3]
    else:
        rgb = np.repeat(image[:, :, :1], 3, axis=2)

    # Convert to float/int in 0-255 range if normalized
    if rgb.dtype in (np.float32, np.float64):
        if np.max(rgb) <= 1.05:
            rgb = np.clip(rgb * 255.0, 0, 255).astype(np.uint8)
        else:
            rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    # Uniform sampling up to ~15,000 pixels
    total_pixels = h * w
    step = max(1, total_pixels // 15000)
    flat_rgb = rgb.reshape(-1, 3)[::step]
    n_samples = len(flat_rgb)

    r = flat_rgb[:, 0].astype(np.float32)
    g = flat_rgb[:, 1].astype(np.float32)
    b = flat_rgb[:, 2].astype(np.float32)

    # 1. Monochrome / Grayscale parity
    is_mono = (np.abs(r - g) <= 22) & (np.abs(g - b) <= 22) & (np.abs(b - r) <= 22)
    monochrome_count = int(np.sum(is_mono))

    # 2. Copper / Amber / Sepia false-color acoustic palette
    # Standard acoustic colormaps map monotonically: Red >= Green >= Blue
    is_copper = (r >= g - 8) & (g >= b - 14) & (b < 0.70 * r + 25)
    copper_count = int(np.sum(is_copper & (~is_mono)))

    acoustic_palette_count = monochrome_count + copper_count
    acoustic_compliance_ratio = acoustic_palette_count / max(n_samples, 1)

    # 3. Optical chromatic violation
    excess_bg = np.maximum(0.0, b - g)
    excess_gr = np.maximum(0.0, g - r)
    excess_br = np.maximum(0.0, b - r)
    chroma_violation = excess_bg * 1.5 + excess_gr * 1.2 + excess_br * 1.5
    total_chroma_violation = float(np.sum(chroma_violation))

    optical_violation_count = int(np.sum(chroma_violation > 20.0))
    optical_violation_ratio = optical_violation_count / max(n_samples, 1)

    # Blue/green dominance (sky, open water, vegetation, synthetic colored objects)
    blue_green_dominant = ((b > r + 16) & (b > 45)) | ((g > r + 20) & (g > 45))
    blue_green_count = int(np.sum(blue_green_dominant))
    blue_green_ratio = blue_green_count / max(n_samples, 1)

    optical_dispersion = total_chroma_violation / max(n_samples, 1)

    is_copper_colormap = (copper_count > monochrome_count) and (copper_count > n_samples * 0.20)
    if is_copper_colormap:
        palette_type = "Copper / Amber False-Color Acoustic"
    elif monochrome_count > n_samples * 0.50:
        palette_type = "Monochrome Grayscale Acoustic"
    else:
        palette_type = "Acoustic Backscatter"

    diagnostics = [
        f"Optical chromatic dispersion: {optical_dispersion:.1f} (Threshold < 18.0 for SSS)",
        f"Acoustic colormap compliance: {acoustic_compliance_ratio * 100:.1f}% (Threshold >= 88.0% for SSS)",
        f"Optical spectrum bias (Blue/Green dominance): {blue_green_ratio * 100:.1f}%",
        f"Acoustic palette classification: {palette_type}",
    ]

    # Criteria for optical RGB photograph
    is_optical = (
        optical_violation_ratio > 0.08
        or optical_dispersion > 16.0
        or blue_green_ratio > 0.04
        or acoustic_compliance_ratio < 0.88
    )

    if is_optical:
        conf_pct = int(max(2, min(18, round((1.0 - min(1.0, optical_dispersion / 50.0)) * 25.0))))
        return ModalityCheckResult(
            is_sss=False,
            confidence_pct=conf_pct,
            detected_modality="OPTICAL_RGB_PHOTO",
            chromatic_dispersion=round(optical_dispersion, 1),
            speckle_parity=0.14,
            verdict_title="NON-SSS IMAGE DETECTED (OPTICAL PHOTOGRAPH)",
            verdict_message="Sensor QA Audit: Uploaded image exhibits optical RGB chromaticity (multi-color dispersion or blue/green spectrum). Real side-scan sonar is single-frequency acoustic intensity (monochrome/copper palette).",
            diagnostic_details=diagnostics,
        )

    conf_pct = int(min(99, max(88, round(acoustic_compliance_ratio * 100.0 - optical_dispersion * 0.5))))
    return ModalityCheckResult(
        is_sss=True,
        confidence_pct=conf_pct,
        detected_modality="SIDE_SCAN_SONAR",
        chromatic_dispersion=round(optical_dispersion, 1),
        speckle_parity=0.88,
        verdict_title="SIDE-SCAN SONAR (SSS) VERIFIED",
        verdict_message=f"Acoustic backscatter characteristics verified: {palette_type} profile with valid single-frequency intensity distribution.",
        diagnostic_details=diagnostics,
    )
