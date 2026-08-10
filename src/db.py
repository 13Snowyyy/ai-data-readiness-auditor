"""SQLite persistence for audit history and dashboard metrics."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List

from . import config
from .utils import human_readable_timestamp


def _connect() -> sqlite3.Connection:
    config.ensure_folders()
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the audits table if it does not exist."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                dataset_name TEXT,
                dataset_owner TEXT,
                intended_use TEXT,
                rows INTEGER,
                columns INTEGER,
                quality_score REAL,
                quality_status TEXT,
                dashboard_score REAL,
                dashboard_status TEXT,
                issue_count INTEGER,
                summary TEXT
            )
            """
        )
        conn.commit()


def save_audit(
    inputs: Dict[str, Any],
    audit: Dict[str, Any],
    quality: Dict[str, Any],
    dashboard: Dict[str, Any],
    summary: str,
) -> int:
    """Persist one audit run and return its new row id."""
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO audits (
                created_at, dataset_name, dataset_owner, intended_use,
                rows, columns, quality_score, quality_status,
                dashboard_score, dashboard_status, issue_count, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                human_readable_timestamp(),
                inputs.get("dataset_name", "") or "Untitled dataset",
                inputs.get("dataset_owner", ""),
                inputs.get("intended_use", ""),
                audit["shape"]["rows"],
                audit["shape"]["columns"],
                quality["score"],
                quality["status"],
                dashboard["score"],
                dashboard["status"],
                len(audit["issue_log"]),
                summary,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_history(limit: int = 100) -> List[Dict[str, Any]]:
    """Return recent audits, newest first."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audits ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_dashboard_metrics() -> Dict[str, Any]:
    """Return aggregate metrics across all saved audits."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_audits,
                AVG(quality_score) AS avg_quality,
                AVG(dashboard_score) AS avg_dashboard,
                MAX(quality_score) AS best_quality,
                MIN(quality_score) AS worst_quality
            FROM audits
            """
        ).fetchone()
    metrics = dict(row) if row else {}
    metrics["total_audits"] = metrics.get("total_audits", 0) or 0
    for key in ("avg_quality", "avg_dashboard", "best_quality", "worst_quality"):
        metrics[key] = round(metrics[key], 1) if metrics.get(key) is not None else 0.0
    return metrics


def delete_all() -> None:
    """Clear all saved audit history."""
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM audits")
        conn.commit()
