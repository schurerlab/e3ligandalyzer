from __future__ import annotations

import io
import json
import os
import queue
import re
import sqlite3
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZIP_DEFLATED, ZipFile

from flask import Blueprint, Response, abort, current_app, jsonify, request, send_file, stream_with_context
from werkzeug.exceptions import HTTPException
from backup_receiver.e3_release_backend import ReleaseBackend, ReleaseError
from backup_receiver.e3_analytics_routes import register_e3_analytics_routes

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_E3_DATA_DIR = PROJECT_ROOT
DEFAULT_E3_DB_PATH = PROJECT_ROOT / "Ligases" / "Ligase_Recruiter.db"
DEFAULT_E3_ELIAH_DB_PATH = PROJECT_ROOT / "Ligases" / "eliah.db"
DEFAULT_E3_ASSET_ROOT = PROJECT_ROOT / "Ligases"
DEFAULT_E3_TABLE_ROOT = PROJECT_ROOT / "Ligase_Table"
DEFAULT_E3_SHIPMENT_DB_PATH = Path(
    os.environ.get("E3_SHIPMENT_DB_PATH", "/var/lib/e3-ligandalyzer/e3_shipments.db")
).expanduser()

MAX_QUERY_ROWS = int(os.environ.get("E3_MAX_QUERY_ROWS", "50000"))
SAFE_SQL_RE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
UNSAFE_SQL_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|VACUUM|ATTACH|DETACH|PRAGMA)\b",
    re.IGNORECASE,
)
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
R2_LEGACY_LIGASE_RE = re.compile(r"^[A-Za-z0-9_.() -]+$")


def _token() -> str:
    return (
        os.environ.get("E3_RANDY_TOKEN", "").strip()
        or os.environ.get("RANDY_E3_TOKEN", "").strip()
        or os.environ.get("RANDY_BACKUP_TOKEN", "").strip()
        or os.environ.get("PROTAC_BACKUP_TOKEN", "").strip()
    )


def _data_dir() -> Path:
    return Path(os.environ.get("E3_DATA_DIR", str(DEFAULT_E3_DATA_DIR))).expanduser()


def _db_path() -> Path:
    root = os.environ.get("E3_RELEASE_ROOT", "").strip()
    if root:
        return _release_backend().db
    return Path(os.environ.get("E3_DB_PATH", str(DEFAULT_E3_DB_PATH))).expanduser()


def _eliah_db_path() -> Path:
    return Path(os.environ.get("E3_ELIAH_DB_PATH", str(DEFAULT_E3_ELIAH_DB_PATH))).expanduser()


def _asset_root() -> Path:
    root = os.environ.get("E3_RELEASE_ROOT", "").strip()
    if root:
        return _release_backend().assets / "Ligases"
    return Path(os.environ.get("E3_ASSET_ROOT", str(DEFAULT_E3_ASSET_ROOT))).expanduser()


@lru_cache(maxsize=4)
def _release_backend_for_root(root: str) -> ReleaseBackend:
    return ReleaseBackend(root)


def _release_backend() -> ReleaseBackend:
    root = os.environ.get("E3_RELEASE_ROOT", "").strip()
    if not root:
        raise ReleaseError("versioned E3 release is not configured")
    return _release_backend_for_root(root)


def _release_asset_row(instance_id: str) -> dict[str, str]:
    """Resolve a V1 asset by its immutable recruiter-instance identifier."""
    instance_id = str(instance_id or "").strip()
    if not instance_id or not SAFE_NAME_RE.fullmatch(instance_id):
        abort(400, description="Invalid recruiter instance ID.")
    for row in _release_backend().asset_rows():
        if row.get("Recruiter_Instance_ID") == instance_id:
            return row
    abort(404, description=f"Recruiter instance not found: {instance_id}")


def _release_asset_path(row: dict[str, str], field: str) -> Path:
    relative = str(row.get(field) or "").strip()
    if not relative:
        abort(404, description="Requested release asset is unavailable.")
    asset_root = _release_backend().assets.resolve()
    path = (asset_root / relative).resolve()
    if not path.is_file() or not _safe_under(asset_root, path):
        abort(404, description="Requested release asset is unavailable.")
    return path


def _release_structural_sdf_path(row: dict[str, str]) -> Path:
    """Resolve a separately materialized observed-coordinate SDF.

    R2 2D assets are intentionally not eligible here.  Older manifests retain
    their explicit exact-instance SDF field for backwards compatibility.
    """
    asset_root = _release_backend().assets.resolve()
    structural_root = Path(os.environ.get("E3_STRUCTURAL_ASSET_ROOT", str(asset_root))).expanduser().resolve()
    instance_id = str(row.get("Recruiter_Instance_ID") or "").strip()
    candidate = (structural_root / "coordinates" / instance_id / "structure_observed_3d.sdf").resolve()
    if candidate.is_file() and _safe_under(structural_root, candidate):
        return candidate
    # The R2 table identifies a release whose manifest SDF is explicitly a
    # planar chemistry asset.  Failing closed here prevents the download API
    # from silently reverting to that different provenance class.
    with _release_backend().connect() as connection:
        has_r2_assets = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'R2_2D_Chemistry_Assets'"
        ).fetchone()
    if has_r2_assets:
        abort(404, description="No validated observed-coordinate SDF is available for this instance.")
    return _release_asset_path(row, "SDF_Web_Path")


def _is_r2_release() -> bool:
    root = os.environ.get("E3_RELEASE_ROOT", "").strip()
    return bool(root) and _release_backend().format == "R2"


def _r2_rows_for_ligase(ligase: str) -> list[dict[str, str]]:
    requested = str(ligase or "").strip()
    if not requested or not R2_LEGACY_LIGASE_RE.fullmatch(requested):
        abort(400, description="Invalid ligase name.")
    rows = [
        row for row in _release_backend().asset_rows()
        if str(row.get("Ligase") or "").casefold() == requested.casefold()
    ]
    if not rows:
        abort(404, description=f"Ligase not found: {ligase}")
    return rows


def _r2_legacy_row(ligase: str, filename: str, asset_kind: str) -> dict[str, str]:
    """Apply the legacy ordered filename fallback to active R2 rows only."""
    field = "Legacy_PDB_Filename" if asset_kind == "pdb" else "Legacy_SDF_Filename"
    extension = ".pdb" if asset_kind == "pdb" else ".sdf"
    rows = _r2_rows_for_ligase(ligase)
    by_name: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        name = str(row.get(field) or "").strip()
        if name:
            by_name.setdefault(name.casefold(), []).append(row)

    candidates = _candidate_names(filename, extension)
    requested = Path(filename).name
    stem = Path(requested).stem if requested.lower().endswith(extension) else requested
    core_no_variant = re.sub(r"_\d+$", "", stem)
    variant_re = re.compile(rf"^{re.escape(core_no_variant)}_(\d+){re.escape(extension)}$", re.IGNORECASE)
    candidates.extend(sorted(name for name in by_name if variant_re.fullmatch(name)))
    for candidate in dict.fromkeys(name.casefold() for name in candidates):
        matches = by_name.get(candidate, [])
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            abort(409, description="Ambiguous legacy release asset request.")
    abort(404, description=f"File not found: {requested}")


def _r2_legacy_asset_path(ligase: str, filename: str, asset_kind: str) -> Path:
    row = _r2_legacy_row(ligase, filename, asset_kind)
    field = "PDB_Web_Path" if asset_kind == "pdb" else "SDF_Web_Path"
    return _release_asset_path(row, field)


def _r2_zip_files(asset_type: str, ligase: str | None = None) -> list[tuple[str, Path]]:
    key = str(asset_type or "").strip().lower()
    if key not in {"pdb", "pdbs", "sdf", "sdfs", "all", "structures"}:
        abort(400, description="asset_type must be one of: pdb, pdbs, sdf, sdfs, all, structures")
    rows = _r2_rows_for_ligase(ligase) if ligase is not None else _release_backend().asset_rows()
    include_pdb = key in {"pdb", "pdbs", "all", "structures"}
    include_sdf = key in {"sdf", "sdfs", "all", "structures"}
    files: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for row in sorted(rows, key=lambda item: (str(item.get("Ligase") or "").casefold(), str(item.get("Recruiter_Instance_ID") or ""))):
        ligase_name = str(row.get("Ligase") or "").strip()
        if include_pdb:
            name = str(row.get("Legacy_PDB_Filename") or "").strip()
            arcname = f"{ligase_name}/PDB/{name}"
            if arcname in seen:
                abort(409, description="Ambiguous R2 legacy archive entry.")
            seen.add(arcname)
            files.append((arcname, _release_asset_path(row, "PDB_Web_Path")))
        if include_sdf:
            name = str(row.get("Legacy_SDF_Filename") or "").strip()
            arcname = f"{ligase_name}/SDF_4Download/{name}"
            if arcname in seen:
                abort(409, description="Ambiguous R2 legacy archive entry.")
            seen.add(arcname)
            files.append((arcname, _release_asset_path(row, "SDF_Web_Path")))
    return files


def _table_root() -> Path:
    return Path(os.environ.get("E3_TABLE_ROOT", str(DEFAULT_E3_TABLE_ROOT))).expanduser()


def _shipment_db_path() -> Path:
    configured = os.environ.get("E3_SHIPMENT_DB_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    if DEFAULT_E3_SHIPMENT_DB_PATH.parent.is_dir() and os.access(DEFAULT_E3_SHIPMENT_DB_PATH.parent, os.W_OK):
        return DEFAULT_E3_SHIPMENT_DB_PATH
    return PROJECT_ROOT / "data" / "e3_shipments.db"


def _safe_under(base: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


def _validate_ligase_name(ligase: str) -> str:
    ligase = str(ligase or "").strip()
    if not ligase or not SAFE_NAME_RE.fullmatch(ligase):
        abort(400, description="Invalid ligase name.")
    return ligase


def _resolve_ligase_dir(ligase: str) -> Path:
    ligase = _validate_ligase_name(ligase)
    asset_root = _asset_root().resolve()
    if not asset_root.is_dir():
        abort(404, description=f"Asset root not found: {asset_root}")

    exact = (asset_root / ligase).resolve()
    if exact.is_dir() and _safe_under(asset_root, exact):
        return exact

    ligase_lower = ligase.lower()
    for item in asset_root.iterdir():
        if item.is_dir() and item.name.lower() == ligase_lower and _safe_under(asset_root, item):
            return item.resolve()

    abort(404, description=f"Ligase not found: {ligase}")


def _validate_relative_filename(filename: str, allowed_exts: set[str]) -> str:
    filename = str(filename or "").strip()
    if not filename:
        abort(400, description="Missing filename.")
    rel = Path(filename)
    if rel.is_absolute() or ".." in rel.parts:
        abort(400, description="Invalid filename.")
    if any(part in {"", "."} for part in rel.parts):
        abort(400, description="Invalid filename.")
    if rel.suffix.lower() and rel.suffix.lower() not in allowed_exts:
        abort(400, description=f"Unsupported file type: {rel.suffix}")
    return rel.as_posix()


def _candidate_names(filename: str, extension: str) -> list[str]:
    rel_name = _validate_relative_filename(filename, {extension})
    basename = Path(rel_name).name
    stem = Path(basename).stem
    suffix = Path(basename).suffix.lower()
    if suffix and suffix != extension:
        abort(400, description=f"Unsupported file type: {suffix}")

    normalized_stem = stem if suffix else basename
    core_no_variant = re.sub(r"_\d+$", "", normalized_stem)
    candidates = [f"{normalized_stem}{extension}"]
    if core_no_variant != normalized_stem:
        candidates.append(f"{core_no_variant}{extension}")
    candidates.append(f"{core_no_variant}_1{extension}")
    return list(dict.fromkeys(candidates))


def _find_variant_file(folder: Path, filename: str, extension: str) -> Path:
    if not folder.is_dir():
        abort(404, description=f"Folder not found: {folder.name}")

    seen: set[str] = set()
    for candidate_name in _candidate_names(filename, extension):
        if candidate_name in seen:
            continue
        seen.add(candidate_name)
        candidate = (folder / candidate_name).resolve()
        if candidate.is_file() and _safe_under(folder, candidate):
            return candidate

    requested = Path(filename).name
    stem = Path(requested).stem if requested.lower().endswith(extension) else requested
    core_no_variant = re.sub(r"_\d+$", "", stem)
    variant_re = re.compile(rf"^{re.escape(core_no_variant)}_(\d+){re.escape(extension)}$", re.IGNORECASE)
    for candidate in sorted(folder.iterdir(), key=lambda item: item.name.lower()):
        if candidate.is_file() and variant_re.fullmatch(candidate.name) and _safe_under(folder, candidate):
            return candidate.resolve()

    abort(404, description=f"File not found: {requested}")


def _resolve_sdf_folders(ligase_dir: Path) -> list[Path]:
    folders = [folder for folder in [ligase_dir / "SDF_4Download", ligase_dir / "SDF"] if folder.is_dir()]
    if folders:
        return folders
    abort(404, description=f"No SDF folder found for {ligase_dir.name}.")


def _resolve_display_sdf_folder(ligase_dir: Path) -> Path:
    """Locate ligand-only SDFs with CCD bond order and PDB-derived coordinates."""
    folder = ligase_dir / "SDF_3DDisplay"
    if folder.is_dir():
        return folder
    abort(404, description=f"No corrected 3D SDF folder found for {ligase_dir.name}.")


def _iter_asset_files(ligase_dir: Path, asset_type: str) -> list[tuple[str, Path]]:
    key = str(asset_type or "").strip().lower()
    options = {
        "pdb": ("PDB", [("PDB", ligase_dir / "PDB", {".pdb"})]),
        "pdbs": ("pdb", [("PDB", ligase_dir / "PDB", {".pdb"})]),
        "sdf": ("SDF", [("SDF_4Download", ligase_dir / "SDF_4Download", {".sdf"}), ("SDF", ligase_dir / "SDF", {".sdf"})]),
        "sdfs": ("sdf", [("SDF_4Download", ligase_dir / "SDF_4Download", {".sdf"}), ("SDF", ligase_dir / "SDF", {".sdf"})]),
        "all": ("all", [("PDB", ligase_dir / "PDB", {".pdb"}), ("SDF_4Download", ligase_dir / "SDF_4Download", {".sdf"}), ("SDF", ligase_dir / "SDF", {".sdf"})]),
        "structures": ("all", [("PDB", ligase_dir / "PDB", {".pdb"}), ("SDF_4Download", ligase_dir / "SDF_4Download", {".sdf"}), ("SDF", ligase_dir / "SDF", {".sdf"})]),
    }
    if key not in options:
        abort(400, description="asset_type must be one of: pdb, pdbs, sdf, sdfs, all, structures")

    _, folders = options[key]
    files: list[tuple[str, Path]] = []
    seen_paths: set[Path] = set()
    for label, folder, exts in folders:
        if not folder.is_dir():
            continue
        for child in sorted(folder.iterdir(), key=lambda item: item.name.lower()):
            resolved = child.resolve()
            if (
                child.is_file()
                and child.suffix.lower() in exts
                and _safe_under(folder, resolved)
                and resolved not in seen_paths
            ):
                seen_paths.add(resolved)
                files.append((label, resolved))
    return files


def _list_download_ligase_dirs() -> list[Path]:
    asset_root = _asset_root().resolve()
    if not asset_root.is_dir():
        return []
    out = []
    for item in asset_root.iterdir():
        if not item.is_dir():
            continue
        if any((item / name).is_dir() for name in ("PDB", "SDF_4Download", "SDF")) and _safe_under(asset_root, item):
            out.append(item.resolve())
    return sorted(out, key=lambda path: path.name.lower())


def _zip_response(files: Iterable[tuple[str, Path]], download_name: str):
    file_list = list(files)
    if not file_list:
        abort(404, description="No matching files.")

    # ZIPs containing the full PDB release take longer than Heroku's 30-second
    # first-byte deadline to assemble.  An unseekable ZIP writer emits data
    # descriptors, allowing the proxy to begin streaming immediately without
    # changing any files or ZIP membership.
    chunks: queue.Queue[bytes | None] = queue.Queue(maxsize=16)

    class _QueueWriter:
        def write(self, data):
            if data:
                chunks.put(bytes(data))
            return len(data)

        def flush(self):
            return None

        def tell(self):
            raise OSError("stream is not seekable")

    def build_zip():
        try:
            with ZipFile(_QueueWriter(), "w", ZIP_DEFLATED) as zip_handle:
                for arcname, path in file_list:
                    zip_handle.write(path, arcname.replace("\\", "/"))
        finally:
            chunks.put(None)

    threading.Thread(target=build_zip, daemon=True).start()

    def generate():
        while True:
            chunk = chunks.get()
            if chunk is None:
                break
            yield chunk

    return Response(
        stream_with_context(generate()),
        mimetype="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
        direct_passthrough=True,
    )


def _validate_sql(sql: str) -> str:
    sql = str(sql or "").strip()
    if not sql:
        raise ValueError("Missing SQL query.")
    if not SAFE_SQL_RE.match(sql):
        raise ValueError("Only SELECT and WITH queries are allowed.")
    if UNSAFE_SQL_RE.search(sql):
        raise ValueError("Write or schema-changing SQL is not allowed.")
    if ";" in sql.rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed.")
    return sql.rstrip(";")


def _database_path(name: str) -> Path:
    database = str(name or "main").strip().lower()
    if database == "main":
        return _db_path()
    if database == "eliah":
        return _eliah_db_path()
    raise ValueError("database must be 'main' or 'eliah'")


def _ensure_shipment_store() -> None:
    db_path = _shipment_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS e3_shipment_events (
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


def _normalize_shipment_payload(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata_json")
    if not isinstance(metadata, dict):
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    return {
        "created_at": str(payload.get("created_at") or "").strip(),
        "recruiter_code": str(payload.get("recruiter_code") or "").strip(),
        "client_ip": str(payload.get("client_ip") or "").strip(),
        "session_id": str(payload.get("session_id") or "").strip(),
        "skip_modify": 1 if bool(payload.get("skip_modify")) else 0,
        "source": str(payload.get("source") or "convert_atom_to_v").strip(),
        "status": str(payload.get("status") or "success").strip(),
        "backend_mode": str(payload.get("backend_mode") or "remote").strip(),
        "metadata_json": metadata,
    }


def _shipment_created_at(payload: dict[str, Any]) -> str:
    value = str(payload.get("created_at") or "").strip()
    if value:
        return value
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _store_shipment_event(payload: dict[str, Any]) -> bool:
    _ensure_shipment_store()
    clean = _normalize_shipment_payload(payload)
    clean["created_at"] = _shipment_created_at(payload)
    with sqlite3.connect(_shipment_db_path()) as conn:
        before = conn.total_changes
        conn.execute(
            """
            INSERT INTO e3_shipment_events (
                created_at, recruiter_code, client_ip, session_id, skip_modify,
                source, status, backend_mode, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO NOTHING
            """,
            (
                clean["created_at"],
                clean["recruiter_code"],
                clean["client_ip"],
                clean["session_id"],
                clean["skip_modify"],
                clean["source"],
                clean["status"],
                clean["backend_mode"],
                json.dumps(clean["metadata_json"], sort_keys=True),
            ),
        )
        conn.commit()
        return conn.total_changes > before


def _shipment_success_count() -> int:
    _ensure_shipment_store()
    with sqlite3.connect(_shipment_db_path()) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM e3_shipment_events WHERE status = ?",
            ("success",),
        ).fetchone()
    return int(row[0] if row else 0)


def register_e3_routes(app) -> None:
    if "randy_e3" in app.blueprints:
        return

    bp = Blueprint("randy_e3", __name__, url_prefix="/backup/e3")

    @bp.before_request
    def _require_e3_auth():
        if not request.path.startswith("/backup/e3"):
            return None
        token = _token()
        if not token:
            return jsonify({"ok": False, "error": "E3 RANDY token is not configured."}), 500
        if request.headers.get("Authorization", "") != f"Bearer {token}":
            return jsonify({"ok": False, "error": "Unauthorized."}), 401
        return None

    @bp.errorhandler(HTTPException)
    def _json_http_error(error: HTTPException):
        response = error.get_response()
        response.data = jsonify({"ok": False, "error": error.description or error.name}).get_data()
        response.content_type = "application/json"
        return response

    @bp.errorhandler(Exception)
    def _json_unhandled_error(error: Exception):
        current_app.logger.exception("Unhandled RANDY E3 route error")
        return jsonify({"ok": False, "error": str(error)}), 500

    @bp.get("/healthz")
    def e3_healthz():
        return jsonify(
            {
                "ok": True,
                "service": "randy-e3-data",
                "data_dir": str(_data_dir()),
                "main_db_exists": _db_path().exists(),
                "eliah_db_exists": _eliah_db_path().exists(),
                "asset_root": str(_asset_root()),
                "asset_root_exists": _asset_root().exists(),
                "table_root": str(_table_root()),
                "table_root_exists": _table_root().exists(),
                "shipment_db_path": str(_shipment_db_path()),
                "shipment_db_exists": _shipment_db_path().exists(),
            }
        )

    @bp.get("/release-info")
    def e3_release_info():
        backend = _release_backend()
        manifest = backend.manifest
        counts = manifest.get("database", {}).get("counts", {})
        return jsonify({
            "ok": True,
            "release_id": manifest.get("release_id", "v1.0-locked"),
            "release_version": str(manifest.get("release_version", "1.0")),
            "release_revision": int(manifest.get("release_revision", 0)),
            "release_status": "LOCKED",
            "correction_type": manifest.get("correction_type", "none"),
            "database_cutoff": manifest.get("database_cutoff_date", "2026-09-08"),
            "lockdown_date": manifest.get("database_cutoff_date", "2026-09-08"),
            "database_sha256": manifest["database"]["sha256"],
            "counts": counts,
        })

    @bp.get("/instances/<instance_id>/pdb")
    def release_instance_pdb(instance_id: str):
        row = _release_asset_row(instance_id)
        file_path = _release_asset_path(row, "PDB_Web_Path")
        return send_file(file_path, mimetype="chemical/x-pdb", as_attachment=False, max_age=0)

    @bp.get("/instances/<instance_id>/sdf")
    def release_instance_sdf(instance_id: str):
        row = _release_asset_row(instance_id)
        file_path = _release_structural_sdf_path(row)
        return send_file(file_path, mimetype="chemical/x-mdl-sdfile", as_attachment=False, max_age=0)

    @bp.get("/instances/<instance_id>/chemistry-sdf")
    def release_instance_chemistry_sdf(instance_id: str):
        row = _release_asset_row(instance_id)
        file_path = _release_asset_path(row, "SDF_Web_Path")
        return send_file(file_path, mimetype="chemical/x-mdl-sdfile", as_attachment=False, max_age=0)

    @bp.post("/query")
    def e3_query():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "Expected JSON object."}), 400

        try:
            sql = _validate_sql(payload.get("sql", ""))
            db_path = _database_path(payload.get("database", "main"))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

        params = payload.get("params", [])
        if not isinstance(params, list):
            return jsonify({"ok": False, "error": "params must be a list."}), 400
        if not db_path.exists():
            return jsonify({"ok": False, "error": f"Database not found: {db_path}"}), 404

        one = bool(payload.get("one"))
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            rows = [dict(row) for row in conn.execute(sql, tuple(params)).fetchmany(MAX_QUERY_ROWS + 1)]

        truncated = len(rows) > MAX_QUERY_ROWS
        rows = rows[:MAX_QUERY_ROWS]
        if one:
            rows = rows[:1]

        return jsonify(
            {
                "ok": True,
                "database": str(payload.get("database") or "main"),
                "count": len(rows),
                "truncated": truncated,
                "rows": rows,
            }
        )

    @bp.post("/shipments")
    def store_shipment():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "Expected JSON object."}), 400

        session_id = str(payload.get("session_id") or "").strip()
        if not session_id:
            return jsonify({"ok": False, "error": "session_id is required."}), 400

        stored = _store_shipment_event(payload)
        return jsonify(
            {
                "ok": True,
                "stored": stored,
                "duplicate": not stored,
                "source": "randy",
            }
        )

    @bp.get("/shipments/count")
    def shipment_count():
        return jsonify(
            {
                "ok": True,
                "total": _shipment_success_count(),
                "source": "randy",
                "backup_ok": True,
            }
        )

    @bp.get("/ligase-pdbs/<ligase>")
    def ligase_pdbs(ligase: str):
        if _is_r2_release():
            return jsonify(sorted(str(row["Legacy_PDB_Filename"]) for row in _r2_rows_for_ligase(ligase)))
        folder = _resolve_ligase_dir(ligase) / "PDB"
        if not folder.is_dir():
            return jsonify([])
        files = sorted(path.name for path in folder.iterdir() if path.is_file() and path.suffix.lower() == ".pdb")
        return jsonify(files)

    @bp.get("/file/pdb/<ligase>/<path:filename>")
    def file_pdb(ligase: str, filename: str):
        if _is_r2_release():
            return send_file(_r2_legacy_asset_path(ligase, filename, "pdb"), mimetype="chemical/x-pdb", as_attachment=False, max_age=0)
        ligase_dir = _resolve_ligase_dir(ligase)
        file_path = _find_variant_file(ligase_dir / "PDB", filename, ".pdb")
        return send_file(file_path, mimetype="chemical/x-pdb", as_attachment=False, max_age=0)

    @bp.get("/file/sdf/<ligase>/<path:filename>")
    def file_sdf(ligase: str, filename: str):
        if _is_r2_release():
            return send_file(_r2_legacy_asset_path(ligase, filename, "sdf"), mimetype="chemical/x-mdl-sdfile", as_attachment=False, max_age=0)
        ligase_dir = _resolve_ligase_dir(ligase)
        for folder in _resolve_sdf_folders(ligase_dir):
            try:
                file_path = _find_variant_file(folder, filename, ".sdf")
                return send_file(file_path, mimetype="chemical/x-mdl-sdfile", as_attachment=False, max_age=0)
            except HTTPException as exc:
                if exc.code != 404:
                    raise
        abort(404, description=f"SDF not found: {ligase}/{filename}")

    @bp.get("/file/display-sdf/<ligase>/<path:filename>")
    def file_display_sdf(ligase: str, filename: str):
        if _is_r2_release():
            return send_file(_r2_legacy_asset_path(ligase, filename, "sdf"), mimetype="chemical/x-mdl-sdfile", as_attachment=False, max_age=0)
        ligase_dir = _resolve_ligase_dir(ligase)
        file_path = _find_variant_file(_resolve_display_sdf_folder(ligase_dir), filename, ".sdf")
        return send_file(file_path, mimetype="chemical/x-mdl-sdfile", as_attachment=False, max_age=0)

    @bp.get("/download/ligase/<ligase>/<asset_type>.zip")
    def download_ligase_zip(ligase: str, asset_type: str):
        if _is_r2_release():
            rows = _r2_rows_for_ligase(ligase)
            return _zip_response(_r2_zip_files(asset_type, ligase), f"E3Ligandalyzer_{rows[0]['Ligase']}_{str(asset_type).lower()}.zip")
        ligase_dir = _resolve_ligase_dir(ligase)
        files = [
            (f"{ligase_dir.name}/{label}/{path.name}", path)
            for label, path in _iter_asset_files(ligase_dir, asset_type)
        ]
        return _zip_response(files, f"E3Ligandalyzer_{ligase_dir.name}_{asset_type.lower()}.zip")

    @bp.get("/download/all/<asset_type>.zip")
    def download_all_zip(asset_type: str):
        if _is_r2_release():
            return _zip_response(_r2_zip_files(asset_type), f"E3Ligandalyzer_ALL_{str(asset_type).lower()}.zip")
        files = []
        for ligase_dir in _list_download_ligase_dirs():
            for label, path in _iter_asset_files(ligase_dir, asset_type):
                files.append((f"{ligase_dir.name}/{label}/{path.name}", path))
        return _zip_response(files, f"E3Ligandalyzer_ALL_{asset_type.lower()}.zip")

    @bp.get("/download/table/<path:table_name>")
    @bp.get("/download/table/<path:table_name>.csv")
    def download_table_csv(table_name: str):
        table_name = str(table_name or "").strip()
        if table_name.lower().endswith(".csv"):
            table_name = table_name[:-4]
        if not table_name or not SAFE_NAME_RE.fullmatch(table_name):
            abort(400, description="Invalid table name.")

        table_root = _table_root().resolve()
        if not table_root.is_dir():
            abort(404, description=f"Table root not found: {table_root}")

        csv_path = (table_root / f"{table_name}.csv").resolve()
        if not _safe_under(table_root, csv_path):
            abort(400, description="Invalid table name.")
        if not csv_path.is_file() or csv_path.suffix.lower() != ".csv":
            abort(404, description=f"CSV table not found: {table_name}.csv")

        return send_file(
            csv_path,
            mimetype="text/csv",
            as_attachment=True,
            download_name=csv_path.name,
            max_age=0,
        )

    app.register_blueprint(bp)
    # Analytics has an independent blueprint and SQLite store so it can never
    # affect the immutable scientific-data API above.
    register_e3_analytics_routes(app, _token)
