"""Isolated, anonymous E3 Ligandalyzer analytics receiver for RANDY."""
from __future__ import annotations

import ipaddress
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from flask import Blueprint, jsonify, request

SAFE_EVENTS = {"page_view", "workflow_started", "upload_started", "import_started", "analysis_submitted", "analysis_completed", "analysis_failed", "results_viewed", "export_generated", "companion_handoff"}
SAFE_FAILURES = {"selection", "upload", "input_validation", "analysis", "result_generation", "export", "handoff", "unknown"}
SAFE_FAILURE_REASONS = {"timeout", "remote_unavailable", "missing_artifact", "output_validation", "conversion_failed", "permission_denied", "internal_error", "unknown"}
SAFE_OUTCOMES = {"success", "empty", "failed"}
SAFE_EVENT_FEATURES = {
    "workflow_started": {"recruiter_discovery", "structure_explorer", "recruiter_builder_preparation"},
    "analysis_submitted": {"recruiter_filter", "attachment_vector_preparation"},
    "analysis_completed": {"recruiter_filter", "attachment_vector_preparation"},
    "analysis_failed": {"recruiter_filter", "attachment_vector_preparation"},
    "results_viewed": {"recruiter_record", "structural_instance", "scaffold_record", "scaffold_network", "ligand_structure_page", "sasa_mapping", "attachment_context"},
    "export_generated": {"structure_pdb", "structure_sdf", "scaffold_smiles_copy"},
    "companion_handoff": {"builder_from_explorer", "builder_from_recruiter"},
}
SAFE_PATH = re.compile(r"^/[A-Za-z0-9_./-]{0,255}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{12,100}$")
SAFE_HANDOFF_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
SAFE_PAYLOAD_KEYS = {"event_id", "event_type", "visitor_id", "session_id", "path", "referrer", "device", "ip_address", "failure_stage", "failure_reason", "feature", "handoff_id", "duration_ms", "outcome_status"}


def _db_path():
    return Path(os.getenv("E3_ANALYTICS_DB_PATH", "/var/lib/e3-ligandalyzer/e3_ligandalyzer_analytics.sqlite3")).expanduser()


def _init():
    path = _db_path(); path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS e3_ligandalyzer_events (
          event_id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL, visitor_id TEXT NOT NULL, session_id TEXT NOT NULL,
          path TEXT NOT NULL, referrer TEXT NOT NULL, device TEXT NOT NULL, country_code TEXT, country_name TEXT,
          latitude REAL, longitude REAL, event_type TEXT NOT NULL, failure_stage TEXT, failure_reason TEXT, feature TEXT, handoff_id TEXT,
          duration_ms INTEGER, outcome_status TEXT
        );
        CREATE INDEX IF NOT EXISTS e3_events_time ON e3_ligandalyzer_events(occurred_at);
        CREATE INDEX IF NOT EXISTS e3_events_type ON e3_ligandalyzer_events(event_type);
        CREATE INDEX IF NOT EXISTS e3_events_session ON e3_ligandalyzer_events(session_id);
        """)
        columns = {row[1] for row in db.execute("PRAGMA table_info(e3_ligandalyzer_events)")}
        if "feature" not in columns:
            db.execute("ALTER TABLE e3_ligandalyzer_events ADD COLUMN feature TEXT")
        if "handoff_id" not in columns:
            db.execute("ALTER TABLE e3_ligandalyzer_events ADD COLUMN handoff_id TEXT")
        if "failure_reason" not in columns:
            db.execute("ALTER TABLE e3_ligandalyzer_events ADD COLUMN failure_reason TEXT")
        if "duration_ms" not in columns:
            db.execute("ALTER TABLE e3_ligandalyzer_events ADD COLUMN duration_ms INTEGER")
        if "outcome_status" not in columns:
            db.execute("ALTER TABLE e3_ligandalyzer_events ADD COLUMN outcome_status TEXT")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS e3_events_handoff_id ON e3_ligandalyzer_events(handoff_id) WHERE handoff_id IS NOT NULL")


def _geo(ip):
    if str(os.getenv("E3_USAGE_GEOIP", "0")).lower() not in {"1", "true", "yes", "on"}:
        return (None, None, None, None)
    try:
        parsed = ipaddress.ip_address(ip)
        if parsed.is_private or parsed.is_loopback:
            return (None, None, None, None)
        data = requests.get(f"https://ipwho.is/{parsed}", timeout=1.5).json()
        if data.get("success", True):
            return (str(data.get("country_code") or "")[:2].upper() or None, str(data.get("country") or "")[:80] or None, data.get("latitude"), data.get("longitude"))
    except (ValueError, requests.RequestException):
        pass
    return (None, None, None, None)


def register_e3_analytics_routes(app, token_getter):
    if "randy_e3_analytics" in app.blueprints:
        return
    bp = Blueprint("randy_e3_analytics", __name__, url_prefix="/backup/e3/analytics")

    @bp.before_request
    def auth():
        token = token_getter()
        if not token or request.headers.get("Authorization", "") != f"Bearer {token}":
            return jsonify({"ok": False, "error": "Unauthorized."}), 401

    @bp.post("/events")
    def events():
        body = request.get_json(silent=True) or {}
        if set(body) - SAFE_PAYLOAD_KEYS:
            return jsonify({"ok": False, "error": "Unexpected analytics fields."}), 400
        if not all(SAFE_ID.fullmatch(str(body.get(key, ""))) for key in ("event_id", "visitor_id", "session_id")):
            return jsonify({"ok": False, "error": "Invalid anonymous event identifier."}), 400
        event_type, path = str(body.get("event_type", "")), str(body.get("path", ""))
        if event_type not in SAFE_EVENTS or not SAFE_PATH.fullmatch(path):
            return jsonify({"ok": False, "error": "Invalid analytics event."}), 400
        feature = str(body.get("feature") or "") or None
        if event_type != "page_view" and feature not in SAFE_EVENT_FEATURES.get(event_type, set()):
            return jsonify({"ok": False, "error": "Invalid analytics feature."}), 400
        handoff_id = str(body.get("handoff_id") or "") or None
        if handoff_id is not None and (event_type != "companion_handoff" or not SAFE_HANDOFF_ID.fullmatch(handoff_id)):
            return jsonify({"ok": False, "error": "Invalid handoff identifier."}), 400
        failure = str(body.get("failure_stage") or "") or None
        if failure and failure not in SAFE_FAILURES:
            return jsonify({"ok": False, "error": "Invalid failure stage."}), 400
        reason = str(body.get("failure_reason") or "") or None
        if reason and reason not in SAFE_FAILURE_REASONS:
            return jsonify({"ok": False, "error": "Invalid failure reason."}), 400
        outcome = str(body.get("outcome_status") or "") or None
        if outcome and outcome not in SAFE_OUTCOMES:
            return jsonify({"ok": False, "error": "Invalid outcome status."}), 400
        try:
            duration_ms = int(body["duration_ms"]) if body.get("duration_ms") is not None else None
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Invalid operation duration."}), 400
        if duration_ms is not None and not 0 <= duration_ms <= 900000:
            return jsonify({"ok": False, "error": "Invalid operation duration."}), 400
        # Raw IP is used only here for GeoIP and is never written or logged.
        country_code, country_name, latitude, longitude = _geo(str(body.get("ip_address") or ""))
        _init()
        with sqlite3.connect(_db_path()) as db:
            before = db.total_changes
            db.execute("""INSERT OR IGNORE INTO e3_ligandalyzer_events (event_id, occurred_at, visitor_id, session_id, path, referrer, device, country_code, country_name, latitude, longitude, event_type, failure_stage, failure_reason, feature, handoff_id, duration_ms, outcome_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? )""", (
                body["event_id"], datetime.now(timezone.utc).isoformat(), body["visitor_id"], body["session_id"], path,
                str(body.get("referrer") or "direct")[:255], str(body.get("device") if body.get("device") in {"desktop", "mobile", "tablet"} else "desktop"),
                country_code, country_name, latitude, longitude, event_type, failure, reason, feature, handoff_id, duration_ms, outcome,
            ))
            stored = db.total_changes > before
        return jsonify({"ok": True, "stored": stored, "duplicate": not stored})

    @bp.get("/rollup")
    def rollup():
        raw = request.args.get("days", "30")
        days = None if raw == "all" else int(raw) if raw in {"7", "30", "90", "365"} else 30
        _init(); since = "" if days is None else (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        clause, params = ("", ()) if not since else (" WHERE occurred_at >= ?", (since,))
        with sqlite3.connect(_db_path()) as db:
            db.row_factory = sqlite3.Row
            metrics = dict(db.execute("SELECT COUNT(DISTINCT visitor_id) visitors, COUNT(DISTINCT session_id) sessions, COALESCE(SUM(event_type='page_view'), 0) page_views FROM e3_ligandalyzer_events" + clause, params).fetchone())
            daily = [dict(r) for r in db.execute("SELECT substr(occurred_at,1,10) date, SUM(event_type='page_view') page_views, COUNT(DISTINCT visitor_id) visitors, COUNT(DISTINCT session_id) sessions, SUM(event_type='workflow_started') workflow_starts, SUM(event_type='analysis_completed' AND COALESCE(outcome_status,'success') != 'empty') completed, SUM(event_type='export_generated') exports, SUM(event_type='companion_handoff') handoffs FROM e3_ligandalyzer_events" + clause + " GROUP BY 1 ORDER BY 1", params)]
            grouped = lambda select: [dict(r) for r in db.execute(select + clause + " GROUP BY 1 ORDER BY 2 DESC LIMIT 30", params)]
            event_sessions = {r["event_type"]: r["sessions"] for r in db.execute("SELECT event_type, COUNT(DISTINCT session_id) sessions FROM e3_ligandalyzer_events" + clause + " GROUP BY event_type", params)}
            def feature_sessions(features, event_types=None):
                terms, values = ["feature IN (" + ",".join("?" for _ in features) + ")"], list(features)
                if event_types:
                    terms.append("event_type IN (" + ",".join("?" for _ in event_types) + ")")
                    values.extend(event_types)
                sql = "SELECT COUNT(DISTINCT session_id) FROM e3_ligandalyzer_events" + clause + (" AND " if clause else " WHERE ") + " AND ".join(terms)
                return db.execute(sql, params + tuple(values)).fetchone()[0]
            export_handoff = feature_sessions(("structure_pdb", "structure_sdf", "scaffold_smiles_copy", "builder_from_explorer", "builder_from_recruiter"))
            funnel = [
                ("Landing page", metrics["sessions"] or 0),
                ("Discovery search / workflow started", feature_sessions(("recruiter_discovery", "recruiter_filter", "structure_explorer"))),
                ("Recruiter or structure viewed", feature_sessions(("recruiter_record", "structural_instance", "ligand_structure_page"))),
                ("Builder preparation started", feature_sessions(("recruiter_builder_preparation",))),
                ("Attachment-vector preparation completed", feature_sessions(("attachment_vector_preparation",), ("analysis_completed",))),
                ("Export or Builder handoff", export_handoff),
            ]
            failures = [dict(r) for r in db.execute("SELECT occurred_at, failure_stage, failure_reason, feature FROM e3_ligandalyzer_events" + clause + (" AND" if clause else " WHERE") + " event_type='analysis_failed' ORDER BY occurred_at DESC LIMIT 20", params)]
            workflow_outcomes = [dict(r) for r in db.execute(
                "SELECT feature, "
                "SUM(event_type IN ('workflow_started','analysis_submitted')) started, "
                "SUM(event_type='analysis_completed' AND COALESCE(outcome_status,'success') != 'empty') completed, "
                "SUM(outcome_status='empty') empty_results, "
                "SUM(event_type='analysis_failed') failed, "
                "SUM(event_type='export_generated') exports, "
                "SUM(event_type='companion_handoff') handoffs "
                "FROM e3_ligandalyzer_events" + clause + (" AND" if clause else " WHERE") + " feature IS NOT NULL GROUP BY feature "
                "ORDER BY completed DESC, started DESC, exports DESC", params)]
            all_first_seen = {r[0]: r[1] for r in db.execute("SELECT visitor_id, MIN(occurred_at) FROM e3_ligandalyzer_events GROUP BY visitor_id")}
            visible_visitors = {r[0] for r in db.execute("SELECT DISTINCT visitor_id FROM e3_ligandalyzer_events" + clause, params)}
            first_cutoff = since or ""
            new_visitors = sum(1 for visitor in visible_visitors if not first_cutoff or all_first_seen.get(visitor, "") >= first_cutoff)
            session_rows = db.execute("SELECT session_id, SUM(event_type='page_view') pages, SUM(event_type IN ('analysis_submitted','analysis_completed','results_viewed','export_generated','companion_handoff')) research FROM e3_ligandalyzer_events" + clause + " GROUP BY session_id", params).fetchall()
            engaged_sessions = sum(int(row[1] or 0) >= 2 for row in session_rows)
            research_sessions = sum(int(row[2] or 0) > 0 for row in session_rows)
            timed = [dict(r) for r in db.execute("SELECT feature, duration_ms FROM e3_ligandalyzer_events" + clause + (" AND" if clause else " WHERE") + " duration_ms IS NOT NULL AND feature IS NOT NULL", params)]
            empty_results = [dict(r) for r in db.execute("SELECT feature, COUNT(*) count FROM e3_ligandalyzer_events" + clause + (" AND" if clause else " WHERE") + " outcome_status='empty' GROUP BY feature ORDER BY count DESC", params)]
            segment_rows = [dict(r) for r in db.execute("SELECT 'Device' label, device value, COUNT(DISTINCT session_id) sessions FROM e3_ligandalyzer_events" + clause + " GROUP BY device HAVING COUNT(DISTINCT session_id) >= 5 UNION ALL SELECT 'Referral', referrer, COUNT(DISTINCT session_id) sessions FROM e3_ligandalyzer_events" + clause + " GROUP BY referrer HAVING COUNT(DISTINCT session_id) >= 5", params + params)]
            handoff_total = db.execute("SELECT COUNT(*) FROM e3_ligandalyzer_events" + clause + (" AND" if clause else " WHERE") + " event_type='companion_handoff'", params).fetchone()[0]
            handoff_origins = [dict(r) for r in db.execute("SELECT feature, COUNT(*) count FROM e3_ligandalyzer_events" + clause + (" AND" if clause else " WHERE") + " event_type='companion_handoff' GROUP BY feature ORDER BY count DESC", params)]
        previous = None; funnel_rows = []
        for label, count in funnel:
            funnel_rows.append({"label": label, "sessions": count, "conversion": None if previous in (None, 0) else round(100 * count / previous, 1)})
            previous = count
        submitted, failed = (event_sessions.get(key, 0) for key in ("analysis_submitted", "analysis_failed"))
        completed = sum(item.get("completed", 0) or 0 for item in workflow_outcomes)
        duration_groups = {}
        for row in timed:
            duration_groups.setdefault(row["feature"], []).append(int(row["duration_ms"]))
        performance = []
        for feature, values in duration_groups.items():
            values.sort(); p95 = values[min(len(values) - 1, round((len(values) - 1) * .95))]
            performance.append({"feature": feature, "count": len(values), "median_ms": values[len(values)//2], "p95_ms": p95})
        performance.sort(key=lambda item: item["p95_ms"], reverse=True)
        alerts = []
        if failed >= 3 and submitted and failed / submitted >= .2:
            alerts.append("Failure rate is above the 20% review threshold.")
        if any(item["p95_ms"] > 60000 for item in performance):
            alerts.append("One or more operations exceeded the 60-second p95 review threshold.")
        return jsonify({"ok": True, "metrics": metrics, "daily": daily,
            "referrers": grouped("SELECT referrer label, COUNT(*) value FROM e3_ligandalyzer_events"), "devices": grouped("SELECT device label, COUNT(*) value FROM e3_ligandalyzer_events"),
            "pages": [dict(r) for r in db.execute("SELECT path, SUM(event_type='page_view') views, COUNT(DISTINCT visitor_id) visitors FROM e3_ligandalyzer_events" + clause + " GROUP BY path ORDER BY views DESC LIMIT 50", params)],
            "countries": [dict(r) for r in db.execute("SELECT country_code, country_name, latitude, longitude, SUM(event_type='page_view') views FROM e3_ligandalyzer_events" + clause + (" AND" if clause else " WHERE") + " country_code IS NOT NULL GROUP BY country_code ORDER BY views DESC", params)],
            "funnel": funnel_rows, "operational": {"submitted": submitted, "completed": completed, "failed": failed, "success_rate": round(100 * completed / submitted, 1) if submitted else None, "empty_results": empty_results, "performance": performance[:10], "segmentation": segment_rows, "alerts": alerts}, "engagement": {"new_visitors": new_visitors, "returning_visitors": len(visible_visitors) - new_visitors, "engaged_sessions": engaged_sessions, "research_sessions": research_sessions, "research_session_rate": round(100 * research_sessions / len(session_rows), 1) if session_rows else None}, "handoffs": {"total": handoff_total, "by_origin": handoff_origins, "cross_tool": {"initiated": handoff_total, "builder_arrived": None, "candidate_constructed": None, "candidate_exported": None}}, "failures": failures,
            "workflows": grouped("SELECT COALESCE(feature, event_type) label, COUNT(*) value FROM e3_ligandalyzer_events"), "workflow_outcomes": workflow_outcomes,
            "features": [dict(r) for r in db.execute("SELECT feature, event_type, COUNT(*) events, COUNT(DISTINCT session_id) sessions FROM e3_ligandalyzer_events" + clause + (" AND" if clause else " WHERE") + " feature IS NOT NULL GROUP BY feature, event_type ORDER BY events DESC", params)]})

    app.register_blueprint(bp)
