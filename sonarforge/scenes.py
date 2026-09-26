"""
SonarForge scene generator — combines seabed, objects, navigation and renderer
to produce complete waterfall scenes with perfect ground-truth labels.
Also generates the 6 Indian demo XTF files for the demo.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from sonarforge.seabed import SeabedGenerator, PRESETS
from sonarforge.objects import (
    ObjectInstance, make_ghost_net, make_pipe, make_cylinder,
    make_wreck_debris, make_trap_pot, make_rope_cable,
    place_object_on_heightmap,
)
from sonarforge.render import SonarGeometry, render_ping, compute_shadow_length_m
from sonarforge.nav import generate_lawnmower, NavPoint, DEMO_SITES
from backend.sagarnetra.io.schema import Ping, Survey
from backend.sagarnetra.io.snl import write_snl
from backend.sagarnetra.io.xtf_writer import write_xtf

logger = logging.getLogger(__name__)


@dataclass
class SceneConfig:
    preset_name: str = "EAST_COAST_SAND"
    site: str = "CHENNAI_PORT"
    frequency_hz: float = 450_000.0
    range_m: float = 50.0
    altitude_m: float = 5.0
    n_lines: int = 4
    line_length_m: float = 300.0
    line_spacing_m: float = 50.0
    objects: list[ObjectInstance] = field(default_factory=list)
    seed: Optional[int] = None


@dataclass
class SceneTruthRecord:
    """Ground-truth for one object in a scene."""
    class_name: str
    subtype: str
    lat: float
    lon: float
    length_m: float
    width_m: float
    height_m: float
    burial_frac: float
    heading_deg: float
    material: str
    source: str = "sim"


def generate_scene(
    config: SceneConfig,
    output_dir: Path,
    scene_id: str = "scene_001",
    save_xtf: bool = False,
) -> tuple[list[Ping], list[SceneTruthRecord]]:
    """
    Generate a complete scene: seabed + objects + navigation → waterfall pings.

    Returns:
        pings: List of Ping objects (full waterfall)
        truth: List of ground-truth records
    """
    rng = np.random.default_rng(config.seed)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate seabed
    geom = SonarGeometry(
        altitude_m=config.altitude_m,
        range_m=config.range_m,
        frequency_hz=config.frequency_hz,
    )
    seabed_gen = SeabedGenerator(config.preset_name, seed=int(rng.integers(0, 1_000_000)))
    width_m = config.range_m * 2.0  # port + starboard
    length_m = config.n_lines * config.line_length_m
    height_map, material_map = seabed_gen.generate(width_m=width_m, length_m=min(length_m, 500))

    # Place objects
    instance_masks: dict[int, np.ndarray] = {}
    truth_records: list[SceneTruthRecord] = []
    lat0, lon0 = DEMO_SITES.get(config.site, (13.10, 80.30))

    for obj_idx, obj in enumerate(config.objects):
        height_map, material_map, mask = place_object_on_heightmap(
            height_map, material_map, obj, ground_res_m=0.10
        )
        instance_masks[obj_idx] = mask
        truth_records.append(SceneTruthRecord(
            class_name=obj.class_name,
            subtype=obj.subtype,
            lat=lat0 + obj.center_y_m / 111_111.0,
            lon=lon0 + obj.center_x_m / (111_111.0 * np.cos(np.deg2rad(lat0))),
            length_m=obj.length_m,
            width_m=obj.width_m,
            height_m=obj.height_m,
            burial_frac=obj.burial_frac,
            heading_deg=obj.heading_deg,
            material=obj.material.value,
        ))

    # Generate navigation
    nav_points = generate_lawnmower(
        site=config.site,
        n_lines=config.n_lines,
        line_length_m=config.line_length_m,
        line_spacing_m=config.line_spacing_m,
        altitude_m=config.altitude_m,
        rng=rng,
    )

    # Render pings
    pings: list[Ping] = []
    W = height_map.shape[1]

    for ping_idx, nav in enumerate(nav_points):
        # Sample a strip of the seabed at this along-track position
        along_y = int((ping_idx / max(len(nav_points) - 1, 1)) * (height_map.shape[0] - 1))
        along_y = min(along_y, height_map.shape[0] - 1)

        # Starboard side (right of towfish)
        strip_start = W // 2
        h_strip = height_map[along_y, strip_start:]
        m_strip = material_map[along_y, strip_start:]
        stbd_samples = render_ping(h_strip, m_strip, geom, rng)

        # Port side (left of towfish, mirrored)
        h_strip_port = height_map[along_y, :strip_start][::-1]
        m_strip_port = material_map[along_y, :strip_start][::-1]
        port_samples = render_ping(h_strip_port, m_strip_port, geom, rng)

        pings.append(Ping(
            ping_id=ping_idx,
            timestamp_utc=nav.timestamp_s,
            ship_lat=nav.lat,
            ship_lon=nav.lon,
            heading_deg=nav.heading_deg,
            speed_mps=nav.speed_mps,
            altitude_m=nav.altitude_m,
            depth_m=nav.depth_m,
            cable_out_m=nav.cable_out_m,
            heave_m=nav.heave_m,
            pitch_deg=nav.pitch_deg,
            roll_deg=nav.roll_deg,
            range_m=config.range_m,
            frequency_hz=config.frequency_hz,
            stbd=stbd_samples.tolist(),
            port=port_samples.tolist(),
        ))

    # Save SNL
    survey = Survey(
        survey_id=scene_id,
        sensor_model="SonarForge",
        frequency_hz=config.frequency_hz,
        range_m=config.range_m,
        files=[str(output_dir / f"{scene_id}.snl.h5")],
    )
    write_snl(output_dir / f"{scene_id}.snl.h5", survey, pings)

    # Save XTF if requested
    if save_xtf:
        write_xtf(output_dir / f"{scene_id}.xtf", pings, frequency_hz=config.frequency_hz)

    # Save ground truth
    truth_data = [
        {
            "class": r.class_name,
            "subtype": r.subtype,
            "lat": r.lat,
            "lon": r.lon,
            "length_m": r.length_m,
            "width_m": r.width_m,
            "height_m": r.height_m,
            "burial_frac": r.burial_frac,
            "heading_deg": r.heading_deg,
            "material": r.material,
            "source": r.source,
        }
        for r in truth_records
    ]
    with open(output_dir / f"{scene_id}_truth.json", "w") as f:
        json.dump(truth_data, f, indent=2)

    logger.info("Scene %s: %d pings, %d objects → %s", scene_id, len(pings), len(truth_records), output_dir)
    return pings, truth_records


def generate_demo_scenes(output_dir: str | Path = "data/demo_logs") -> None:
    """Generate the 6 XTF demo logs for the demo script."""
    output_dir = Path(output_dir)
    rng = np.random.default_rng(42)

    demo_configs = [
        SceneConfig(
            preset_name="REEF_RUBBLE",
            site="CHENNAI_PORT",
            objects=[
                make_ghost_net(120.0, 150.0, length_m=12.0, burial_frac=0.1, rng=rng),
                make_ghost_net(80.0, 200.0, length_m=8.0, burial_frac=0.4, rng=rng),
            ],
            seed=1,
        ),
        SceneConfig(
            preset_name="SEAGRASS_BED",
            site="GULF_OF_MANNAR",
            objects=[
                make_ghost_net(100.0, 100.0, length_m=15.0, burial_frac=0.5, rng=rng),
            ],
            seed=2,
        ),
        SceneConfig(
            preset_name="WEST_COAST_MUD",
            site="KOCHI",
            objects=[
                make_pipe(130.0, 120.0, length_m=40.0, diameter_m=0.6),
                make_cylinder(90.0, 180.0, diameter_m=0.5, length_m=1.5),
            ],
            seed=3,
        ),
        SceneConfig(
            preset_name="HARBOUR_FLOOR",
            site="JNPT_MUMBAI",
            objects=[
                make_wreck_debris(100.0, 150.0, length_m=12.0, height_m=2.0, subtype="boat"),
            ],
            seed=4,
        ),
        SceneConfig(
            preset_name="EAST_COAST_SAND",
            site="VISAKHAPATNAM",
            objects=[
                make_wreck_debris(110.0, 160.0, length_m=8.0, height_m=1.5, subtype="boat"),
                make_rope_cable(140.0, 140.0, length_m=25.0),
            ],
            seed=5,
        ),
        SceneConfig(
            preset_name="EAST_COAST_SAND",
            site="PARADIP",
            objects=[
                make_ghost_net(100.0, 130.0, length_m=20.0, burial_frac=0.2, rng=rng),
                make_trap_pot(120.0, 110.0),
            ],
            seed=6,
        ),
    ]

    for i, (site_name, cfg) in enumerate(zip(DEMO_SITES.keys(), demo_configs)):
        scene_id = f"demo_{site_name.lower()}"
        pings, truth = generate_scene(
            cfg,
            output_dir=output_dir / scene_id,
            scene_id=scene_id,
            save_xtf=True,
        )
        logger.info("Demo scene %s: %d pings generated.", scene_id, len(pings))
