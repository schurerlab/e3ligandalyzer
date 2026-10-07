import os

import pytest
from flask import Flask

os.environ.setdefault("E3_DATABASE_PATH", "data/does-not-exist.sqlite")

from Ligase_app import create_app


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.org")
    monkeypatch.setenv("ADMIN_PASSWORD", "correct-password")
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret")
    monkeypatch.delenv("E3_RANDY_BASE_URL", raising=False)
    return create_app()


def test_admin_requires_login(app):
    response = app.test_client().get("/admin/analytics")
    assert response.status_code == 302
    assert "/admin/login" in response.location


def test_admin_login_valid_and_invalid(app):
    client = app.test_client()
    assert client.post("/admin/login", data={"email": "admin@example.org", "password": "wrong"}).status_code == 200
    response = client.post("/admin/login", data={"email": "admin@example.org", "password": "correct-password"})
    assert response.status_code == 302
    assert client.get("/admin/analytics").status_code == 200


def test_public_page_sets_anonymous_visitor_and_session_cookies(app, monkeypatch):
    # Avoid opening any scientific database while exercising the tracking layer.
    monkeypatch.setattr("e3_analytics.track", lambda *args, **kwargs: None)
    response = app.test_client().get("/docs")
    cookies = "\n".join(response.headers.getlist("Set-Cookie"))
    assert "e3_vid=" in cookies and "e3_sid=" in cookies


def test_browser_events_require_an_allowed_feature_and_receiver_failure_is_nonblocking(app, monkeypatch):
    client = app.test_client()
    assert client.post("/analytics/event", json={"event_type": "results_viewed", "feature": "not-a-real-feature"}).status_code == 400
    assert client.post("/analytics/event", json={"event_type": "analysis_failed", "feature": "recruiter_filter", "failure_stage": "smiles"}).status_code == 400
    monkeypatch.setattr("e3_analytics._enabled", lambda: True)
    monkeypatch.setattr("e3_analytics._post", lambda *args: type("R", (), {"ok": False, "status_code": 503})())
    response = client.post("/analytics/event", json={"event_type": "results_viewed", "feature": "recruiter_record"})
    assert response.status_code == 202 and response.json["delivered"] is False


def test_randy_receiver_rejects_scientific_values_and_rolls_up_feature(monkeypatch, tmp_path):
    from server.randy.e3_analytics_routes import register_e3_analytics_routes
    monkeypatch.setenv("E3_ANALYTICS_DB_PATH", str(tmp_path / "analytics.sqlite3"))
    receiver = Flask(__name__)
    register_e3_analytics_routes(receiver, lambda: "token")
    client = receiver.test_client()
    headers = {"Authorization": "Bearer token"}
    payload = {"event_id": "a" * 24, "visitor_id": "b" * 24, "session_id": "c" * 24, "event_type": "export_generated", "feature": "structure_pdb", "path": "/explorer", "referrer": "direct", "device": "desktop", "smiles": "CCO"}
    assert client.post("/backup/e3/analytics/events", json=payload, headers=headers).status_code == 400
    # Scientific fields are rejected, never silently retained.
    payload.pop("smiles")
    assert client.post("/backup/e3/analytics/events", json=payload, headers=headers).status_code == 200
    report = client.get("/backup/e3/analytics/rollup", headers=headers).json
    assert report["features"] == [{"feature": "structure_pdb", "event_type": "export_generated", "events": 1, "sessions": 1}]
    payload["event_id"] = "d" * 24
    payload["feature"] = "CCO"
    assert client.post("/backup/e3/analytics/events", json=payload, headers=headers).status_code == 400
