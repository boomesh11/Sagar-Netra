"""
SonarForge materials — acoustic backscatter coefficients (dB) and K-distribution shape.
Values sourced from Blondel "The Handbook of Sidescan Sonar" and Lurton.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Material(str, Enum):
    SAND = "sand"
    MUD = "mud"
    ROCK = "rock"
    METAL = "metal"
    AIR_FLOAT = "air_float"
    FOAM_FLOAT = "foam_float"
    NYLON_TWINE = "nylon_twine"
    SEAGRASS = "seagrass"
    WOOD = "wood"
    WATER = "water"
    UNKNOWN = "unknown"


@dataclass
class MaterialProps:
    mu_db: float          # Lambert backscatter coefficient (dB)
    k_nu: float           # K-distribution shape (higher = less speckle)
    height_std_m: float   # typical surface height std (m)


MATERIAL_TABLE: dict[Material, MaterialProps] = {
    Material.SAND:       MaterialProps(mu_db=-27.0, k_nu=5.0,  height_std_m=0.02),
    Material.MUD:        MaterialProps(mu_db=-35.0, k_nu=2.0,  height_std_m=0.005),
    Material.ROCK:       MaterialProps(mu_db=-17.0, k_nu=10.0, height_std_m=0.15),
    Material.METAL:      MaterialProps(mu_db=-5.0,  k_nu=15.0, height_std_m=0.0),
    Material.AIR_FLOAT:  MaterialProps(mu_db=-3.0,  k_nu=20.0, height_std_m=0.0),
    Material.FOAM_FLOAT: MaterialProps(mu_db=-12.0, k_nu=8.0,  height_std_m=0.0),
    Material.NYLON_TWINE:MaterialProps(mu_db=-30.0, k_nu=3.0,  height_std_m=0.0),
    Material.SEAGRASS:   MaterialProps(mu_db=-25.0, k_nu=2.0,  height_std_m=0.05),
    Material.WOOD:       MaterialProps(mu_db=-20.0, k_nu=4.0,  height_std_m=0.01),
    Material.WATER:      MaterialProps(mu_db=-60.0, k_nu=1.0,  height_std_m=0.0),
    Material.UNKNOWN:    MaterialProps(mu_db=-27.0, k_nu=5.0,  height_std_m=0.02),
}


def get_props(mat: Material | str) -> MaterialProps:
    if isinstance(mat, str):
        mat = Material(mat)
    return MATERIAL_TABLE.get(mat, MATERIAL_TABLE[Material.UNKNOWN])
