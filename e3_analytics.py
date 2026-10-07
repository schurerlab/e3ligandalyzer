"""Privacy-preserving analytics client and admin blueprint for E3 Ligandalyzer."""
from __future__ import annotations

import os
import secrets
import logging
import threading
from datetime import timedelta
from functools import wraps
from urllib.parse import urlparse

import requests
from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request, session, url_for

SAFE_EVENTS = {
    "workflow_started", "upload_started", "import_started", "analysis_submitted",
    "analysis_completed", "analysis_failed", "results_viewed", "export_generated", "companion_handoff",
}
SAFE_FAILURE_STAGES = {"selection", "upload", "input_validation", "analysis", "result_generation", "export", "handoff", "unknown"}
# Features are deliberately paired to the broad event families.  This is the
# complete browser/server contract; it prevents a page from smuggling user or
# scientific values into the analytics store.
SAFE_EVENT_FEATURES = {
    "workflow_started": {"recruiter_discovery", "structure_explorer", "recruiter_builder_preparation"},
    "analysis_submitted": {"recruiter_filter", "attachment_vector_preparation"},
    "analysis_completed": {"recruiter_filter", "attachment_vector_preparation"},
    "analysis_failed": {"recruiter_filter", "attachment_vector_preparation"},
    "results_viewed": {"recruiter_record", "structural_instance", "scaffold_record", "scaffold_network", "ligand_structure_page", "sasa_mapping", "attachment_context"},
    "export_generated": {"structure_pdb", "structure_sdf", "scaffold_smiles_copy"},
    "companion_handoff": {"builder_from_explorer", "builder_from_recruiter"},
}
PUBLIC_EXCLUDED_PREFIXES = ("/admin", "/api", "/static", "/health", "/analytics")
logger = logging.getLogger(__name__)


class _FailedDelivery:
    ok = False
    status_code = "no-response"

    def __init__(self, reason):
        self.reason = reason


def _base_url():
    value = (os.getenv("E3_RANDY_BASE_URL") or os.getenv("RANDY_E3_BASE_URL") or "").rstrip("/")
    return value if value.endswith("/backup/e3") else (f"{value}/e3" if value.endswith("/backup") else value)


def _token():
    return next((os.getenv(name, "").strip() for name in ("E3_RANDY_TOKEN", "RANDY_E3_TOKEN", "RANDY_BACKUP_TOKEN", "PROTAC_BACKUP_TOKEN") if os.getenv(name, "").strip()), "")


def _enabled():
    return str(os.getenv("E3_USAGE_ANALYTICS", "1")).lower() in {"1", "true", "yes", "on"} and bool(_base_url() and _token())


def _client_ip():
    # Heroku's left-most X-Forwarded-For address is the browser address.
    return (request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or "")


def _device():
    ua = (request.user_agent.string or "").lower()
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    return "mobile" if any(item in ua for item in ("mobi", "android", "iphone")) else "desktop"


def _referrer():
    host = urlparse(request.referrer or "").hostname
    return host.lower()[:255] if host else "direct"


def _post(path, payload):
    if not _enabled():
        return None
    try:
        return requests.post(
            f"{_base_url()}/analytics/{path.lstrip('/')}", json=payload,
            # Match the established RANDY client tolerance. Public page views
            # are sent by a post-load request, so this cannot delay page use.
            headers={"Authorization": f"Bearer {_token()}", "User-Agent": "e3-ligandalyzer-analytics/1.0"}, timeout=(10, 45),
        )
    except requests.RequestException as exc:
        logger.warning("E3 analytics delivery failed: %s", type(exc).__name__)
        return _FailedDelivery(type(exc).__name__)


def _get(path):
    if not _enabled():
        return None
    try:
        return requests.get(
            f"{_base_url()}/analytics/{path.lstrip('/')}",
            headers={"Authorization": f"Bearer {_token()}", "User-Agent": "e3-ligandalyzer-analytics/1.0"}, timeout=2,
        )
    except requests.RequestException:
        current_app.logger.info("E3 analytics receiver unavailable")
        return None


def track(event_type, *, feature=None, path=None, failure_stage=None, background=True):
    if event_type not in SAFE_EVENTS and event_type != "page_view":
        return
    if feature is not None and feature not in SAFE_EVENT_FEATURES.get(event_type, set()):
        return
    payload = {
        "event_id": secrets.token_urlsafe(24), "event_type": event_type,
        "visitor_id": g.analytics_visitor_id, "session_id": g.analytics_session_id,
        "path": (path or request.path)[:256], "referrer": _referrer(), "device": _device(),
        # The receiver uses this only for the immediate GeoIP lookup, then discards it.
        "ip_address": _client_ip(),
    }
    if failure_stage in SAFE_FAILURE_STAGES:
        payload["failure_stage"] = failure_stage
    if feature:
        payload["feature"] = feature
    if background:
        # Tracking must never delay or break a scientific workflow/page response.
        threading.Thread(target=_post, args=("events", payload), daemon=True, name="e3-analytics-event").start()
    else:
        return _post("events", payload)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("e3_admin"):
            return redirect(url_for("e3_analytics.admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def register_analytics(app):
    bp = Blueprint("e3_analytics", __name__)

    @app.before_request
    def _analytics_ids():
        g.analytics_visitor_id = request.cookies.get("e3_vid") or secrets.token_urlsafe(18)
        g.analytics_session_id = request.cookies.get("e3_sid") or secrets.token_urlsafe(18)
        g.analytics_new_visitor = "e3_vid" not in request.cookies
        g.analytics_new_session = "e3_sid" not in request.cookies

    @app.after_request
    def _page_view(response):
        if g.get("analytics_new_visitor"):
            response.set_cookie("e3_vid", g.analytics_visitor_id, max_age=int(timedelta(days=400).total_seconds()), secure=request.is_secure, httponly=True, samesite="Lax")
        if g.get("analytics_new_session"):
            response.set_cookie("e3_sid", g.analytics_session_id, secure=request.is_secure, httponly=True, samesite="Lax")
        if response.content_type.startswith("text/html") and response.status_code < 400 and not request.path.startswith(PUBLIC_EXCLUDED_PREFIXES):
            track("page_view")
        return response

    @bp.route("/analytics/event", methods=["POST"])
    def public_event():
        body = request.get_json(silent=True) or {}
        event_type, feature = body.get("event_type"), body.get("feature")
        if event_type not in SAFE_EVENTS or feature not in SAFE_EVENT_FEATURES.get(event_type, set()):
            return jsonify({"ok": False}), 400
        failure_stage = body.get("failure_stage")
        if failure_stage is not None and failure_stage not in SAFE_FAILURE_STAGES:
            return jsonify({"ok": False}), 400
        # Browser-triggered workflow events are safe and controlled. Page views
        # are recorded exclusively by the server's after-request tracker.
        result = track(event_type, feature=feature, failure_stage=failure_stage, background=False)
        # Browser analytics is best effort: failure must never make a user
        # action appear failed, including a Builder navigation.
        if result is None or not result.ok:
            logger.warning("E3 analytics receiver response: %s", getattr(result, "status_code", "no-response"))
            return jsonify({"ok": True, "delivered": False}), 202
        return jsonify({"ok": True}), 202

    @bp.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        error = None
        if request.method == "POST":
            import hmac
            expected_email, expected_password = os.getenv("ADMIN_EMAIL", ""), os.getenv("ADMIN_PASSWORD", "")
            if expected_email and expected_password and hmac.compare_digest(request.form.get("email", ""), expected_email) and hmac.compare_digest(request.form.get("password", ""), expected_password):
                session.clear(); session["e3_admin"] = True
                return redirect(request.args.get("next") or url_for("e3_analytics.admin_analytics"))
            error = "Invalid email or password."
        return render_template("admin_login.html", error=error)

    @bp.get("/admin/logout")
    def admin_logout():
        session.clear()
        return redirect(url_for("e3_analytics.admin_login"))

    @bp.get("/admin/analytics")
    @admin_required
    def admin_analytics():
        days = request.args.get("days", "30")
        if days not in {"7", "30", "90", "365", "all"}:
            days = "30"
        report = {}
        unavailable = False
        try:
            response = _get(f"rollup?days={days}")
            report = response.json() if response and response.ok else {}
            unavailable = not bool(report.get("ok"))
        except (ValueError, requests.RequestException):
            unavailable = True
        return render_template("admin_analytics.html", report=report, days=days, unavailable=unavailable)

    app.register_blueprint(bp)
