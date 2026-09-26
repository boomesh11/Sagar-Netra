"""
SonarForge seabed generator.
Creates 2.5D height maps and material maps for Indian coastal seabed presets.
Grid resolution: 5 cm (0.05 m).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from sonarforge.materials import Material


@dataclass
class SeabedPreset:
    name: str
    slope_deg_max: float = 3.0
    ripple_wavelength_m: tuple[float, float] = (0.5, 1.2)
    ripple_amplitude_m: tuple[float, float] = (0.03, 0.10)
    rock_density: float = 0.0          # rocks per m²
    rock_height_m: tuple[float, float] = (0.2, 1.0)
    seagrass_fraction: float = 0.0
    base_material: Material = Material.SAND
    description: str = ""


PRESETS: dict[str, SeabedPreset] = {
    "EAST_COAST_SAND": SeabedPreset(
        name="EAST_COAST_SAND",
        slope_deg_max=2.0,
        ripple_wavelength_m=(0.4, 1.0),
        ripple_amplitude_m=(0.02, 0.08),
        rock_density=0.01,
        rock_height_m=(0.1, 0.5),
        seagrass_fraction=0.05,
        base_material=Material.SAND,
        description="Chennai/Visakhapatnam shelf style — sandy with gentle ripples",
    ),
    "WEST_COAST_MUD": SeabedPreset(
        name="WEST_COAST_MUD",
        slope_deg_max=1.0,
        ripple_wavelength_m=(0.8, 1.5),
        ripple_amplitude_m=(0.01, 0.04),
        rock_density=0.005,
        rock_height_m=(0.1, 0.3),
        seagrass_fraction=0.02,
        base_material=Material.MUD,
        description="Mumbai/Kutch style — soft mud, low relief",
    ),
    "REEF_RUBBLE": SeabedPreset(
        name="REEF_RUBBLE",
        slope_deg_max=5.0,
        ripple_wavelength_m=(0.3, 0.8),
        ripple_amplitude_m=(0.05, 0.15),
        rock_density=0.15,
        rock_height_m=(0.3, 2.0),
        seagrass_fraction=0.10,
        base_material=Material.ROCK,
        description="Gulf of Mannar/Lakshadweep — reef rubble with rocks",
    ),
    "SEAGRASS_BED": SeabedPreset(
        name="SEAGRASS_BED",
        slope_deg_max=1.5,
        ripple_wavelength_m=(0.5, 1.0),
        ripple_amplitude_m=(0.02, 0.06),
        rock_density=0.02,
        rock_height_m=(0.1, 0.4),
        seagrass_fraction=0.60,
        base_material=Material.SEAGRASS,
        description="Palk Bay style — dense seagrass beds",
    ),
    "HARBOUR_FLOOR": SeabedPreset(
        name="HARBOUR_FLOOR",
        slope_deg_max=0.5,
        ripple_wavelength_m=(0.3, 0.6),
        ripple_amplitude_m=(0.01, 0.03),
        rock_density=0.02,
        rock_height_m=(0.1, 0.5),
        seagrass_fraction=0.0,
        base_material=Material.MUD,
        description="Port basin — relatively flat mud with debris",
    ),
}


class SeabedGenerator:
    """Generates a 2.5D seabed height map and material map."""

    RESOLUTION_M = 0.05  # 5 cm grid

    def __init__(self, preset_name: str = "EAST_COAST_SAND", seed: Optional[int] = None):
        self.preset = PRESETS[preset_name]
        self.rng = np.random.default_rng(seed)

    def generate(
        self,
        width_m: float = 100.0,
        length_m: float = 200.0,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Generate seabed height map and material map.

        Returns:
            height_map: float32 array [length_px, width_px] in metres
            material_map: uint8 array with Material enum ordinal values
        """
        res = self.RESOLUTION_M
        W = int(width_m / res)
        L = int(length_m / res)

        height_map = np.zeros((L, W), dtype=np.float32)
        material_map = np.full((L, W), list(Material).index(self.preset.base_material), dtype=np.uint8)

        # (a) Low-frequency slope / undulation
        height_map += self._gen_slope(L, W)

        # (b) Sand ripples
        height_map += self._gen_ripples(L, W)

        # (c) Rock clusters
        height_map, material_map = self._add_rocks(height_map, material_map, L, W)

        # (d) Seagrass patches
        material_map = self._add_seagrass(material_map, L, W)

        return height_map, material_map

    def _gen_slope(self, L: int, W: int) -> np.ndarray:
        """Random slope + low-frequency undulation (fractional Brownian motion approximation)."""
        slope_rad = np.deg2rad(self.rng.uniform(0, self.preset.slope_deg_max))
        direction = self.rng.uniform(0, 2 * np.pi)
        x = np.linspace(0, W * self.RESOLUTION_M, W)
        y = np.linspace(0, L * self.RESOLUTION_M, L)
        XX, YY = np.meshgrid(x, y)
        slope = (XX * np.cos(direction) + YY * np.sin(direction)) * np.tan(slope_rad)

        # Add gentle undulation
        freq = self.rng.uniform(0.02, 0.08)
        amp = self.rng.uniform(0.05, 0.20)
        undulation = amp * np.sin(2 * np.pi * freq * XX + self.rng.uniform(0, 2 * np.pi))
        return (slope + undulation).astype(np.float32)

    def _gen_ripples(self, L: int, W: int) -> np.ndarray:
        """Sand ripples as sinusoidal pattern."""
        wl_min, wl_max = self.preset.ripple_wavelength_m
        amp_min, amp_max = self.preset.ripple_amplitude_m
        wavelength = self.rng.uniform(wl_min, wl_max)
        amplitude = self.rng.uniform(amp_min, amp_max)
        orientation = self.rng.uniform(0, np.pi)
        phase = self.rng.uniform(0, 2 * np.pi)

        x = np.linspace(0, W * self.RESOLUTION_M, W)
        y = np.linspace(0, L * self.RESOLUTION_M, L)
        XX, YY = np.meshgrid(x, y)
        ripple_coord = XX * np.cos(orientation) + YY * np.sin(orientation)
        # Add phase noise
        noise = self.rng.normal(0, 0.05, (L, W))
        ripples = amplitude * np.sin(2 * np.pi * ripple_coord / wavelength + phase + noise)
        return ripples.astype(np.float32)

    def _add_rocks(
        self, height_map: np.ndarray, material_map: np.ndarray, L: int, W: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """Add rock clusters using Poisson-disc ellipsoids."""
        area_m2 = L * W * self.RESOLUTION_M ** 2
        n_rocks = int(self.preset.rock_density * area_m2)
        rock_mat_idx = list(Material).index(Material.ROCK)
        h_min, h_max = self.preset.rock_height_m

        for _ in range(n_rocks):
            cx = self.rng.integers(0, W)
            cy = self.rng.integers(0, L)
            height = self.rng.uniform(h_min, h_max)
            r_x = int(self.rng.uniform(2, 20) / self.RESOLUTION_M)
            r_y = int(self.rng.uniform(2, 15) / self.RESOLUTION_M)

            yy, xx = np.ogrid[-r_y:r_y + 1, -r_x:r_x + 1]
            ellipse = (xx / max(r_x, 1)) ** 2 + (yy / max(r_y, 1)) ** 2 <= 1.0

            y0 = max(0, cy - r_y)
            y1 = min(L, cy + r_y + 1)
            x0 = max(0, cx - r_x)
            x1 = min(W, cx + r_x + 1)
            ey0 = y0 - (cy - r_y)
            ey1 = ey0 + (y1 - y0)
            ex0 = x0 - (cx - r_x)
            ex1 = ex0 + (x1 - x0)

            region = ellipse[ey0:ey1, ex0:ex1]
            profile = height * np.sqrt(np.maximum(0, 1.0 - (xx[0, ex0:ex1] / max(r_x, 1)) ** 2))
            height_map[y0:y1, x0:x1] = np.where(region, height_map[y0:y1, x0:x1] + height, height_map[y0:y1, x0:x1])
            material_map[y0:y1, x0:x1] = np.where(region, rock_mat_idx, material_map[y0:y1, x0:x1])

        return height_map, material_map

    def _add_seagrass(self, material_map: np.ndarray, L: int, W: int) -> np.ndarray:
        """Add seagrass patches as random blobs."""
        if self.preset.seagrass_fraction <= 0:
            return material_map
        grass_mat_idx = list(Material).index(Material.SEAGRASS)
        n_patches = max(1, int(self.preset.seagrass_fraction * 10))
        for _ in range(n_patches):
            cx = self.rng.integers(0, W)
            cy = self.rng.integers(0, L)
            r = self.rng.integers(10, 50)
            yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
            circle = xx ** 2 + yy ** 2 <= r ** 2
            y0, y1 = max(0, cy - r), min(L, cy + r + 1)
            x0, x1 = max(0, cx - r), min(W, cx + r + 1)
            ey0, ex0 = y0 - (cy - r), x0 - (cx - r)
            ey1, ex1 = ey0 + (y1 - y0), ex0 + (x1 - x0)
            material_map[y0:y1, x0:x1] = np.where(circle[ey0:ey1, ex0:ex1], grass_mat_idx, material_map[y0:y1, x0:x1])
        return material_map
