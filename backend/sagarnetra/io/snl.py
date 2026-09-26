"""
SNL — SagarNetra Log format.
An HDF5-based format for storing complete surveys with all metadata.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import h5py
import numpy as np

from backend.sagarnetra.io.schema import Ping, Survey


def write_snl(path: str | Path, survey: Survey, pings: list[Ping]) -> None:
    """Write a survey to an SNL (HDF5) file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with h5py.File(path, "w") as f:
        # Survey metadata
        meta = f.create_group("survey")
        meta.attrs["survey_id"] = survey.survey_id
        meta.attrs["sensor_model"] = survey.sensor_model
        meta.attrs["frequency_hz"] = survey.frequency_hz
        meta.attrs["range_m"] = survey.range_m
        meta.attrs["crs"] = survey.crs
        meta.attrs["start_utc"] = survey.start_utc or 0.0
        meta.attrs["end_utc"] = survey.end_utc or 0.0

        # Ping data
        pings_grp = f.create_group("pings")
        for i, ping in enumerate(pings):
            pg = pings_grp.create_group(str(i))
            pg.attrs["ping_id"] = ping.ping_id
            pg.attrs["timestamp_utc"] = ping.timestamp_utc
            pg.attrs["ship_lat"] = ping.ship_lat if ping.ship_lat is not None else float("nan")
            pg.attrs["ship_lon"] = ping.ship_lon if ping.ship_lon is not None else float("nan")
            pg.attrs["heading_deg"] = ping.heading_deg
            pg.attrs["altitude_m"] = ping.altitude_m
            pg.attrs["depth_m"] = ping.depth_m
            pg.attrs["speed_mps"] = ping.speed_mps
            pg.attrs["range_m"] = ping.range_m
            pg.attrs["frequency_hz"] = ping.frequency_hz
            pg.attrs["flags"] = json.dumps([f.value for f in ping.flags])
            if ping.stbd is not None:
                pg.create_dataset("stbd", data=np.array(ping.stbd, dtype=np.uint16))
            if ping.port is not None:
                pg.create_dataset("port", data=np.array(ping.port, dtype=np.uint16))


def read_snl(path: str | Path) -> tuple[Survey, list[Ping]]:
    """Read an SNL (HDF5) file and return (Survey, list[Ping])."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"SNL file not found: {path}")

    pings: list[Ping] = []
    with h5py.File(path, "r") as f:
        meta = f["survey"]
        survey = Survey(
            survey_id=str(meta.attrs["survey_id"]),
            sensor_model=str(meta.attrs.get("sensor_model", "SNL")),
            frequency_hz=float(meta.attrs.get("frequency_hz", 450_000.0)),
            range_m=float(meta.attrs.get("range_m", 50.0)),
            crs=str(meta.attrs.get("crs", "EPSG:4326")),
            start_utc=float(meta.attrs.get("start_utc", 0.0)) or None,
            end_utc=float(meta.attrs.get("end_utc", 0.0)) or None,
        )

        pings_grp = f["pings"]
        for key in sorted(pings_grp.keys(), key=int):
            pg = pings_grp[key]
            lat = float(pg.attrs["ship_lat"])
            lon = float(pg.attrs["ship_lon"])
            from backend.sagarnetra.io.schema import PingFlag
            flags_raw = json.loads(pg.attrs.get("flags", "[]"))
            flags = [PingFlag(fl) for fl in flags_raw]

            stbd = pg["stbd"][:].tolist() if "stbd" in pg else None
            port = pg["port"][:].tolist() if "port" in pg else None

            pings.append(Ping(
                ping_id=int(pg.attrs["ping_id"]),
                timestamp_utc=float(pg.attrs["timestamp_utc"]),
                ship_lat=None if (lat != lat) else lat,
                ship_lon=None if (lon != lon) else lon,
                heading_deg=float(pg.attrs.get("heading_deg", 0.0)),
                altitude_m=float(pg.attrs.get("altitude_m", 5.0)),
                depth_m=float(pg.attrs.get("depth_m", 10.0)),
                speed_mps=float(pg.attrs.get("speed_mps", 0.0)),
                range_m=float(pg.attrs.get("range_m", 50.0)),
                frequency_hz=float(pg.attrs.get("frequency_hz", 450_000.0)),
                stbd=stbd,
                port=port,
                flags=flags,
            ))

    return survey, pings
