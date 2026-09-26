"""
SagarNetra Storage — SQLite Review Store & Survey Persistence.
Persists survey sessions, georeferenced detections, rule logs, and operator reviews
(CONFIRMED, REJECTED, CHANGED_CLASS, UNSURE) for active learning and auditable reporting.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class SurveyStore:
    """
    SQLite persistent database for SagarNetra surveys, detections, and reviews.
    """
    def __init__(self, db_path: str | Path = "artifacts/sagarnetra.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Surveys table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS surveys (
                    survey_id TEXT PRIMARY KEY,
                    site_name TEXT NOT NULL,
                    source_file TEXT,
                    source_type TEXT DEFAULT 'REAL',
                    created_at TEXT NOT NULL,
                    total_pings INTEGER DEFAULT 0,
                    swath_range_m REAL DEFAULT 60.0,
                    altitude_m REAL DEFAULT 8.0,
                    clearance_status TEXT DEFAULT 'IN_PROGRESS'
                )
            """)

            # Detections table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detections (
                    target_id TEXT PRIMARY KEY,
                    survey_id TEXT NOT NULL,
                    class_name TEXT NOT NULL,
                    source_type TEXT DEFAULT 'REAL',
                    hazard_confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    priority REAL NOT NULL,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    utm_easting REAL NOT NULL,
                    utm_northing REAL NOT NULL,
                    zone INTEGER NOT NULL,
                    r95_m REAL NOT NULL,
                    position_status TEXT DEFAULT 'AVAILABLE',
                    position_reason TEXT,
                    r95_status TEXT DEFAULT 'AVAILABLE',
                    r95_reason TEXT,
                    length_m REAL NOT NULL,
                    width_m REAL NOT NULL,
                    height_m REAL,
                    height_status TEXT DEFAULT 'AVAILABLE',
                    height_reason TEXT,
                    orientation_deg REAL NOT NULL,
                    views INTEGER DEFAULT 1,
                    components_json TEXT,
                    rules_json TEXT,
                    review_status TEXT DEFAULT 'UNREVIEWED',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (survey_id) REFERENCES surveys (survey_id)
                )
            """)

            # Migrations for existing database
            for col, col_def in [
                ("source_type", "TEXT DEFAULT 'REAL'"),
                ("position_status", "TEXT DEFAULT 'AVAILABLE'"),
                ("position_reason", "TEXT"),
                ("r95_status", "TEXT DEFAULT 'AVAILABLE'"),
                ("r95_reason", "TEXT"),
                ("height_status", "TEXT DEFAULT 'AVAILABLE'"),
                ("height_reason", "TEXT"),
            ]:
                try:
                    cursor.execute(f"ALTER TABLE detections ADD COLUMN {col} {col_def}")
                except sqlite3.OperationalError:
                    pass  # column already exists

            try:
                cursor.execute("ALTER TABLE surveys ADD COLUMN source_type TEXT DEFAULT 'REAL'")
            except sqlite3.OperationalError:
                pass

            # Reviews table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    new_class TEXT,
                    operator_notes TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (target_id) REFERENCES detections (target_id)
                )
            """)
            conn.commit()

    def create_survey(
        self,
        survey_id: str,
        site_name: str,
        source_file: Optional[str] = None,
        source_type: str = "REAL",
        swath_range_m: float = 60.0,
        altitude_m: float = 8.0,
    ) -> Dict[str, Any]:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO surveys
                (survey_id, site_name, source_file, source_type, created_at, swath_range_m, altitude_m)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (survey_id, site_name, source_file, source_type, created_at, swath_range_m, altitude_m))
            conn.commit()

        return {
            "survey_id": survey_id,
            "site_name": site_name,
            "source_file": source_file,
            "source_type": source_type,
            "created_at": created_at,
            "swath_range_m": swath_range_m,
            "altitude_m": altitude_m,
        }

    def save_detection(
        self,
        target_id: str,
        survey_id: str,
        class_name: str,
        hazard_confidence: float,
        status: str,
        priority: float,
        lat: float,
        lon: float,
        utm_easting: float,
        utm_northing: float,
        zone: int,
        r95_m: float,
        length_m: float,
        width_m: float,
        height_m: Optional[float] = None,
        orientation_deg: float = 0.0,
        views: int = 1,
        source_type: str = "REAL",
        position_status: str = "AVAILABLE",
        position_reason: Optional[str] = None,
        r95_status: str = "AVAILABLE",
        r95_reason: Optional[str] = None,
        height_status: str = "AVAILABLE",
        height_reason: Optional[str] = None,
        components: Optional[Dict[str, Any]] = None,
        rules: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        created_at = datetime.now(timezone.utc).isoformat()
        comp_str = json.dumps(components or {})
        rules_str = json.dumps(rules or [])

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO detections
                (target_id, survey_id, class_name, source_type, hazard_confidence, status, priority,
                 lat, lon, utm_easting, utm_northing, zone, r95_m, position_status, position_reason,
                 r95_status, r95_reason, length_m, width_m, height_m, height_status, height_reason,
                 orientation_deg, views, components_json, rules_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                target_id, survey_id, class_name, source_type, hazard_confidence, status, priority,
                lat, lon, utm_easting, utm_northing, zone, r95_m, position_status, position_reason,
                r95_status, r95_reason, length_m, width_m, height_m, height_status, height_reason,
                orientation_deg, views, comp_str, rules_str, created_at,
            ))
            conn.commit()

        return {"target_id": target_id, "status": "SAVED", "source_type": source_type}

    def record_operator_review(
        self,
        target_id: str,
        action: str,  # "CONFIRMED", "REJECTED", "CHANGED_CLASS", "UNSURE"
        new_class: Optional[str] = None,
        operator_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reviews (target_id, action, new_class, operator_notes, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (target_id, action, new_class, operator_notes, timestamp))

            # Update detection record
            update_cls = new_class if (action == "CHANGED_CLASS" and new_class) else None
            if update_cls:
                cursor.execute("""
                    UPDATE detections
                    SET review_status = ?, class_name = ?
                    WHERE target_id = ?
                """, (action, update_cls, target_id))
            else:
                cursor.execute("""
                    UPDATE detections
                    SET review_status = ?
                    WHERE target_id = ?
                """, (action, target_id))

            conn.commit()

        return {"target_id": target_id, "action": action, "timestamp": timestamp}

    def get_detections(
        self,
        survey_id: Optional[str] = None,
        status: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM detections WHERE hazard_confidence >= ?"
        params: List[Any] = [min_confidence]

        if survey_id:
            query += " AND survey_id = ?"
            params.append(survey_id)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY priority DESC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["components"] = json.loads(d.pop("components_json") or "{}")
            d["rules"] = json.loads(d.pop("rules_json") or "[]")
            results.append(d)
        return results

    def get_detection_by_id(self, target_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM detections WHERE target_id = ?", (target_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["components"] = json.loads(d.pop("components_json") or "{}")
            d["rules"] = json.loads(d.pop("rules_json") or "[]")

            reviews = conn.execute("SELECT * FROM reviews WHERE target_id = ? ORDER BY timestamp DESC", (target_id,)).fetchall()
            d["reviews"] = [dict(rev) for rev in reviews]
            return d

    def get_survey_summary(self, survey_id: str) -> Dict[str, Any]:
        with self._get_connection() as conn:
            survey = conn.execute("SELECT * FROM surveys WHERE survey_id = ?", (survey_id,)).fetchone()
            if not survey:
                return {}
            s_dict = dict(survey)

            stats = conn.execute("""
                SELECT
                    COUNT(*) as total_targets,
                    SUM(CASE WHEN status = 'CONFIRMED_HAZARD' THEN 1 ELSE 0 END) as confirmed_count,
                    SUM(CASE WHEN status = 'SUSPECTED_HAZARD' THEN 1 ELSE 0 END) as suspected_count,
                    SUM(CASE WHEN status = 'CONFUSER_REJECTED' THEN 1 ELSE 0 END) as confuser_count,
                    SUM(CASE WHEN review_status != 'UNREVIEWED' THEN 1 ELSE 0 END) as reviewed_count,
                    AVG(hazard_confidence) as mean_confidence
                FROM detections
                WHERE survey_id = ?
            """, (survey_id,)).fetchone()

            s_dict.update(dict(stats))
            return s_dict
