import os

import pytest

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
