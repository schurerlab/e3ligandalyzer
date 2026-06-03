#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Persistent shipment-event storage for PROTAC Builder handoffs."""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from Ligases import randy_client


DEFAULT_SQLITE_PATH = Path("instance") / "e3_shipments.db"
DEFAULT_CSV_FALLBACK_PATH = Path("Ligases") / "Ligases_Shipped_To_Builder.csv"
SHIPMENT_TABLE = "e3_shipment_events"


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "") or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _storage_mode() -> str:
    value = str(os.environ.get("E3_SHIPMENT_STORAGE", "auto") or "auto").strip().lower()
    return value or "auto"


def _sqlite_path() -> Path:
    raw = str(os.environ.get("E3_SHIPMENT_DB_PATH", "") or "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_SQLITE_PATH


def _csv_fallback_path() -> Path:
    raw = str(os.environ.get("E3_SHIPMENT_CSV_PATH", "") or "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_CSV_FALLBACK_PATH


def _database_url() -> str:
    return str(os.environ.get("DATABASE_URL", "") or "").strip()


def _shipment_headers() -> list[str]:
    return [
        "created_at",
        "recruiter_code",
        "client_ip",
        "session_id",
        "skip_modify",
        "source",
        "status",
        "backend_mode",
        "metadata_json",
    ]


def _mirror_enabled() -> bool:
    return _env_flag("E3_SHIPMENT_RANDY_BACKUP_ENABLED", False)


def _postgres_supported() -> bool:
    if not _database_url():
        return False
    try:
        import sqlalchemy  # noqa: F401
        import psycopg2  # noqa: F401
        return True
    except Exception:
        return False


def _resolve_mode() -> str:
    mode = _storage_mode()
    if mode != "auto":
        return mode
    if _postgres_supported():
        return "postgres"
    if randy_client.shipment_backup_configured():
        return "randy"
    return "sqlite"


def backup_status_hint() -> bool:
    mode = _resolve_mode()
    if mode == "randy":
        return randy_client.shipment_backup_configured()
    if not _mirror_enabled():
        return True
    return randy_client.shipment_backup_configured()


def _safe_session_id(value: Any) -> str:
    return str(value or "").strip()


def _safe_text(value: Any, default: str = "") -> str:
    return str(value or default).strip()


def _coerce_bool_int(value: Any) -> int:
    return 1 if bool(value) else 0


def _safe_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    return metadata


def normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    metadata = _safe_metadata(event.get("metadata_json"))
    if not metadata and isinstance(event.get("metadata"), dict):
        metadata = dict(event["metadata"])
    normalized = {
        "created_at": _safe_text(event.get("created_at")) or _utc_now(),
        "recruiter_code": _safe_text(event.get("recruiter_code")),
        "client_ip": _safe_text(event.get("client_ip")),
        "session_id": _safe_session_id(event.get("session_id")),
        "skip_modify": _coerce_bool_int(event.get("skip_modify")),
        "source": _safe_text(event.get("source"), "convert_atom_to_v"),
        "status": _safe_text(event.get("status"), "success"),
        "backend_mode": _safe_text(event.get("backend_mode"), "local"),
        "metadata_json": metadata,
    }
    return normalized


@dataclass
class ShipmentRecordResult:
    recorded: bool
    duplicate: bool
    source: str
    backup_ok: bool


def _sqlite_conn() -> sqlite3.Connection:
    db_path = _sqlite_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SHIPMENT_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            recruiter_code TEXT,
            client_ip TEXT,
            session_id TEXT UNIQUE,
            skip_modify INTEGER DEFAULT 0,
            source TEXT,
            status TEXT DEFAULT 'success',
            backend_mode TEXT,
            metadata_json TEXT
        )
        """
    )
    conn.commit()
    return conn


def _postgres_engine():
    from sqlalchemy import create_engine

    return create_engine(_database_url(), future=True, pool_pre_ping=True)


def _ensure_postgres_table() -> None:
    from sqlalchemy import text

    engine = _postgres_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {SHIPMENT_TABLE} (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    recruiter_code TEXT,
                    client_ip TEXT,
                    session_id TEXT UNIQUE,
                    skip_modify INTEGER DEFAULT 0,
                    source TEXT,
                    status TEXT DEFAULT 'success',
                    backend_mode TEXT,
                    metadata_json TEXT
                )
                """
            )
        )


def _record_sqlite(event: Dict[str, Any]) -> ShipmentRecordResult:
    payload = normalize_event(event)
    duplicate = False
    with _sqlite_conn() as conn:
        before = conn.total_changes
        conn.execute(
            f"""
            INSERT INTO {SHIPMENT_TABLE} (
                created_at, recruiter_code, client_ip, session_id,
                skip_modify, source, status, backend_mode, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO NOTHING
            """,
            (
                payload["created_at"],
                payload["recruiter_code"],
                payload["client_ip"],
                payload["session_id"],
                payload["skip_modify"],
                payload["source"],
                payload["status"],
                payload["backend_mode"],
                json.dumps(payload["metadata_json"], sort_keys=True),
            ),
        )
        conn.commit()
        duplicate = conn.total_changes == before
    return ShipmentRecordResult(recorded=not duplicate, duplicate=duplicate, source="sqlite", backup_ok=True)


def _record_postgres(event: Dict[str, Any]) -> ShipmentRecordResult:
    from sqlalchemy import text

    payload = normalize_event(event)
    _ensure_postgres_table()
    engine = _postgres_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                f"""
                INSERT INTO {SHIPMENT_TABLE} (
                    created_at, recruiter_code, client_ip, session_id,
                    skip_modify, source, status, backend_mode, metadata_json
                ) VALUES (
                    :created_at, :recruiter_code, :client_ip, :session_id,
                    :skip_modify, :source, :status, :backend_mode, :metadata_json
                )
                ON CONFLICT (session_id) DO NOTHING
                """
            ),
            {
                "created_at": payload["created_at"],
                "recruiter_code": payload["recruiter_code"],
                "client_ip": payload["client_ip"],
                "session_id": payload["session_id"],
                "skip_modify": payload["skip_modify"],
                "source": payload["source"],
                "status": payload["status"],
                "backend_mode": payload["backend_mode"],
                "metadata_json": json.dumps(payload["metadata_json"], sort_keys=True),
            },
        )
    duplicate = not bool(getattr(result, "rowcount", 0))
    return ShipmentRecordResult(recorded=not duplicate, duplicate=duplicate, source="postgres", backup_ok=True)


def _append_csv_row(event: Dict[str, Any]) -> ShipmentRecordResult:
    payload = normalize_event(event)
    csv_path = _csv_fallback_path()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    create_header = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if create_header:
            writer.writerow(_shipment_headers())
        writer.writerow(
            [
                payload["created_at"],
                payload["recruiter_code"],
                payload["client_ip"],
                payload["session_id"],
                payload["skip_modify"],
                payload["source"],
                payload["status"],
                payload["backend_mode"],
                json.dumps(payload["metadata_json"], sort_keys=True),
            ]
        )
    return ShipmentRecordResult(recorded=True, duplicate=False, source="csv-fallback", backup_ok=True)


def _record_randy(event: Dict[str, Any]) -> ShipmentRecordResult:
    payload = normalize_event(event)
    response = randy_client.post_shipment_event(payload)
    return ShipmentRecordResult(
        recorded=bool(response.get("stored", True)),
        duplicate=bool(response.get("duplicate", False)),
        source="randy",
        backup_ok=True,
    )


def _mirror_to_randy(event: Dict[str, Any]) -> bool:
    if not _mirror_enabled():
        return True
    if not randy_client.shipment_backup_configured():
        return False
    try:
        randy_client.post_shipment_event(normalize_event(event))
        return True
    except Exception:
        return False


def record_shipment_event(event: Dict[str, Any]) -> ShipmentRecordResult:
    mode = _resolve_mode()
    try:
        if mode == "postgres":
            result = _record_postgres(event)
        elif mode == "sqlite":
            result = _record_sqlite(event)
        elif mode == "randy":
            result = _record_randy(event)
        elif mode == "csv-fallback":
            result = _append_csv_row(event)
        else:
            raise ValueError(f"Unsupported shipment storage mode: {mode}")
    except Exception:
        if mode != "csv-fallback":
            result = _append_csv_row(event)
        else:
            raise

    if result.source != "randy":
        result.backup_ok = _mirror_to_randy(event)
    return result


def _count_sqlite_success() -> int:
    with _sqlite_conn() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS total FROM {SHIPMENT_TABLE} WHERE status = ?",
            ("success",),
        ).fetchone()
    return int(row["total"] if row else 0)


def _count_postgres_success() -> int:
    from sqlalchemy import text

    _ensure_postgres_table()
    engine = _postgres_engine()
    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) AS total FROM {SHIPMENT_TABLE} WHERE status = :status"),
            {"status": "success"},
        ).scalar_one()
    return int(total or 0)


def _count_csv_rows() -> int:
    csv_path = _csv_fallback_path()
    if not csv_path.exists():
        return 0
    with csv_path.open(encoding="utf-8") as handle:
        total = sum(1 for _ in handle)
    return max(total - 1, 0)


def get_shipment_count() -> Dict[str, Any]:
    mode = _resolve_mode()
    try:
        if mode == "postgres":
            total = _count_postgres_success()
            source = "postgres"
        elif mode == "sqlite":
            total = _count_sqlite_success()
            source = "sqlite"
        elif mode == "randy":
            response = randy_client.get_shipment_count()
            total = int(response.get("total", 0))
            source = "randy"
        elif mode == "csv-fallback":
            total = _count_csv_rows()
            source = "csv-fallback"
        else:
            raise ValueError(f"Unsupported shipment storage mode: {mode}")
    except Exception:
        total = _count_csv_rows()
        source = "csv-fallback"

    return {
        "ok": True,
        "total": total,
        "source": source,
        "backup_ok": backup_status_hint(),
    }
