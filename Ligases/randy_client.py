#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Authenticated client for the E3 data service hosted on RANDY."""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

import requests
from flask import Response, stream_with_context


DEFAULT_TIMEOUT_SECONDS = 30


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "") or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "remote"}


def remote_enabled() -> bool:
    """Return True when this app should use RANDY instead of local SQLite/files."""
    backend = str(os.environ.get("E3_DATA_BACKEND", "") or "").strip().lower()
    if backend in {"remote", "randy"}:
        return True
    return _env_flag("E3_USE_RANDY", False)


def base_url() -> str:
    """Normalize the RANDY E3 base URL.

    Preferred value:
      E3_RANDY_BASE_URL=https://randy.example/backup/e3

    If the caller gives the parent /backup URL, append /e3.
    """
    raw = (
        os.environ.get("E3_RANDY_BASE_URL", "").strip()
        or os.environ.get("RANDY_E3_BASE_URL", "").strip()
    )
    value = raw.rstrip("/")
    if not value:
        return ""
    if value.endswith("/backup/e3"):
        return value
    if value.endswith("/backup"):
        return f"{value}/e3"
    return value


def token() -> str:
    return (
        os.environ.get("E3_RANDY_TOKEN", "").strip()
        or os.environ.get("RANDY_E3_TOKEN", "").strip()
        or os.environ.get("RANDY_BACKUP_TOKEN", "").strip()
        or os.environ.get("PROTAC_BACKUP_TOKEN", "").strip()
    )


def timeout_seconds() -> int:
    raw = str(os.environ.get("E3_RANDY_TIMEOUT_SECONDS", "") or "").strip()
    try:
        return max(1, int(raw))
    except Exception:
        return DEFAULT_TIMEOUT_SECONDS


def configured() -> bool:
    return bool(base_url() and token())


def headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    out = {"User-Agent": "e3-ligandalyzer-randy-client/1.0"}
    tok = token()
    if tok:
        out["Authorization"] = f"Bearer {tok}"
    if extra:
        out.update(extra)
    return out


def _url(path: str) -> str:
    root = base_url()
    if not root:
        raise RuntimeError("E3_RANDY_BASE_URL is not configured")
    return f"{root}/{path.lstrip('/')}"


def health() -> Dict[str, Any]:
    resp = requests.get(_url("healthz"), headers=headers(), timeout=timeout_seconds())
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("ok", False):
        raise RuntimeError(f"RANDY E3 health check failed: {payload}")
    return payload


def query(database: str, sql: str, params: Iterable[Any] = (), one: bool = False):
    """Run a parameterized read-only query through RANDY."""
    if not configured():
        raise RuntimeError("RANDY E3 query requested but E3_RANDY_BASE_URL/E3_RANDY_TOKEN is not configured")

    payload = {
        "database": database,
        "sql": sql,
        "params": list(params or []),
        "one": bool(one),
    }
    resp = requests.post(
        _url("query"),
        json=payload,
        headers=headers({"Accept": "application/json"}),
        timeout=timeout_seconds(),
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok", False):
        raise RuntimeError(data.get("error") or "RANDY E3 query failed")

    rows = data.get("rows", [])
    if one:
        return rows[0] if rows else None
    return rows


def get_json(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    resp = requests.get(_url(path), params=params or {}, headers=headers(), timeout=timeout_seconds())
    resp.raise_for_status()
    payload = resp.json()
    if isinstance(payload, dict) and payload.get("ok") is False:
        raise RuntimeError(payload.get("error") or f"RANDY E3 request failed: {path}")
    return payload


def proxy_file(path: str, *, download_name: Optional[str] = None, mimetype: Optional[str] = None) -> Response:
    """Stream a file endpoint from RANDY back to the browser."""
    resp = requests.get(
        _url(path),
        headers=headers(),
        timeout=timeout_seconds(),
        stream=True,
    )
    resp.raise_for_status()

    response_headers = {}
    content_type = mimetype or resp.headers.get("Content-Type") or "application/octet-stream"
    disposition = resp.headers.get("Content-Disposition")
    if disposition:
        response_headers["Content-Disposition"] = disposition
    elif download_name:
        response_headers["Content-Disposition"] = f'attachment; filename="{download_name}"'

    return Response(
        stream_with_context(resp.iter_content(chunk_size=1024 * 256)),
        status=resp.status_code,
        mimetype=content_type,
        headers=response_headers,
        direct_passthrough=True,
    )


def quote_part(value: Any) -> str:
    return quote(str(value or "").strip(), safe="")


def quote_path(value: Any) -> str:
    return quote(str(value or "").strip().lstrip("/"), safe="/")
