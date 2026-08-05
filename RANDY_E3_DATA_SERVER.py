#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deprecated standalone RANDY-hosted E3 Ligandalyzer data service.

Production E3 routes now belong on the shared RANDY Flask app under
`/backup/e3` via `RANDY/app.py` + `RANDY/e3_data_routes.py`.

This file is kept as a compatibility/reference copy of the earlier standalone
implementation and should not be the preferred runtime path.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from zipfile import ZIP_DEFLATED, ZipFile

from flask import Flask, Response, abort, jsonify, request, send_file


APP = Flask(__name__)

DEFAULT_E3_ROOT = Path("/srv/e3-ligandalyzer")
E3_ROOT = Path(os.environ.get("E3_DATA_DIR", str(DEFAULT_E3_ROOT))).expanduser()
DB_PATH = Path(os.environ.get("E3_DB_PATH", str(E3_ROOT / "Databases" / "Ligase_Recruiter.db"))).expanduser()
ELIAH_DB_PATH = Path(os.environ.get("E3_ELIAH_DB_PATH", str(E3_ROOT / "Databases" / "eliah.db"))).expanduser()
ASSET_ROOT = Path(os.environ.get("E3_ASSET_ROOT", str(E3_ROOT / "Ligases"))).expanduser()
TOKEN = (
    os.environ.get("E3_RANDY_TOKEN", "").strip()
    or os.environ.get("RANDY_E3_TOKEN", "").strip()
    or os.environ.get("RANDY_BACKUP_TOKEN", "").strip()
    or os.environ.get("PROTAC_BACKUP_TOKEN", "").strip()
)

MAX_QUERY_ROWS = int(os.environ.get("E3_MAX_QUERY_ROWS", "50000"))
SAFE_SQL_RE = re.compile(r"^\s*(SELECT|WITH|PRAGMA)\b", re.IGNORECASE)
UNSAFE_SQL_RE = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|REPLACE|VACUUM)\b", re.IGNORECASE)
SAFE_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

PUBLIC_DOWNLOAD_TABLES = {
    "Ligase_Scaffold_Data",
    "Ligase_Scaffold_Summary",
    "Ligase_Scaffold_Frequency",
    "Ligase_Recruiters_Scaffold",
    "Ligase_Chemical_Descriptors",
    "Ligase_Ligand_Metadata",
    "Ligase_Ligand_SASA_summary",
    "Ligase_Ligand_SASA_atoms",
    "Ligase_Ligands_Smiles_3DMapped",
    "Ligase_SMILE_Codes",
    "Recruiter_SMILES_Map",
}


def require_auth():
    if not TOKEN:
        return False, ("E3 RANDY token is not configured.", 500)
    if request.headers.get("Authorization", "") != f"Bearer {TOKEN}":
        return False, ("Unauthorized.", 401)
    return True, None


@APP.before_request
def _auth_all_routes():
    ok, error = require_auth()
    if not ok:
        message, status = error
        return jsonify({"ok": False, "error": message}), status


def _db_for_name(name: str) -> Path:
    if name == "main":
        return DB_PATH
    if name == "eliah":
        return ELIAH_DB_PATH
    raise ValueError("database must be 'main' or 'eliah'")


def _validate_sql(sql: str) -> str:
    sql = str(sql or "").strip()
    if not sql:
        raise ValueError("Missing SQL query.")
    if not SAFE_SQL_RE.match(sql):
        raise ValueError("Only SELECT, WITH, and PRAGMA queries are allowed.")
    if UNSAFE_SQL_RE.search(sql):
        raise ValueError("Write or schema-changing SQL is not allowed.")
    if ";" in sql.rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed.")
    return sql.rstrip(";")


def _safe_under(base: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


def _safe_ligase_dir(ligase: str) -> Path:
    if not ligase or "/" in ligase or "\\" in ligase or ".." in ligase:
        abort(400, description="Invalid ligase name.")
    root = ASSET_ROOT.resolve()
    exact = (root / ligase).resolve()
    if exact.is_dir() and _safe_under(root, exact):
        return exact
    low = ligase.lower()
    for item in root.iterdir() if root.is_dir() else []:
        if item.is_dir() and item.name.lower() == low:
            return item.resolve()
    abort(404, description=f"Ligase not found: {ligase}")


def _safe_file(folder: Path, filename: str, allowed_exts: set[str]) -> Path:
    if not filename or filename.startswith("/") or ".." in Path(filename).parts:
        abort(400, description="Invalid filename.")
    candidate = (folder / filename).resolve()
    if not _safe_under(folder, candidate):
        abort(400, description="Invalid filename.")
    if not candidate.is_file():
        abort(404, description=f"File not found: {filename}")
    if candidate.suffix.lower() not in allowed_exts:
        abort(400, description=f"Unsupported file type: {candidate.suffix}")
    return candidate


def _asset_dirs(ligase_dir: Path, asset_type: str):
    asset_type = asset_type.lower()
    folders = []
    if asset_type in {"pdb", "pdbs", "all", "structures"}:
        folders.append(("PDB", ligase_dir / "PDB", {".pdb"}))
    if asset_type in {"sdf", "sdfs", "all", "structures"}:
        folders.append(("SDF_4Download", ligase_dir / "SDF_4Download", {".sdf"}))
        folders.append(("SDF", ligase_dir / "SDF", {".sdf"}))
    return [(label, folder, exts) for label, folder, exts in folders if folder.is_dir()]


def _files_from_dirs(asset_dirs):
    files = []
    seen = set()
    for label, folder, exts in asset_dirs:
        for path in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
            if not path.is_file() or path.suffix.lower() not in exts:
                continue
            resolved = path.resolve()
            if not _safe_under(folder, resolved):
                continue
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            files.append((label, resolved))
    return files


def _list_ligase_dirs():
    if not ASSET_ROOT.is_dir():
        return []
    out = []
    for path in ASSET_ROOT.iterdir():
        if not path.is_dir() or path.name.startswith("."):
            continue
        if (path / "PDB").is_dir() or (path / "SDF_4Download").is_dir() or (path / "SDF").is_dir():
            out.append(path)
    return sorted(out, key=lambda p: p.name.lower())


def _zip_response(files, download_name: str, metadata: Optional[Dict[str, Any]] = None):
    if not files:
        abort(404, description="No matching files.")
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as zf:
        if metadata:
            zf.writestr("manifest.json", json.dumps(metadata, indent=2, sort_keys=True))
        added = set()
        for arcname, path in files:
            arcname = str(arcname).replace("\\", "/")
            if arcname in added:
                stem = Path(arcname).stem
                suffix = Path(arcname).suffix
                parent = str(Path(arcname).parent).replace("\\", "/")
                arcname = f"{parent}/{stem}_{len(added)}{suffix}"
            added.add(arcname)
            zf.write(path, arcname)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/zip", as_attachment=True, download_name=download_name, max_age=0)


@APP.get("/healthz")
def healthz():
    return jsonify({
        "ok": True,
        "service": "e3-randy-data",
        "main_db_exists": DB_PATH.exists(),
        "eliah_db_exists": ELIAH_DB_PATH.exists(),
        "asset_root_exists": ASSET_ROOT.exists(),
        "main_db_path": str(DB_PATH),
        "eliah_db_path": str(ELIAH_DB_PATH),
        "asset_root": str(ASSET_ROOT),
    })


@APP.post("/query")
def query():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "Expected JSON object."}), 400
    try:
        db_path = _db_for_name(str(payload.get("database") or "main"))
        sql = _validate_sql(str(payload.get("sql") or ""))
        params = payload.get("params") or []
        if not isinstance(params, list):
            return jsonify({"ok": False, "error": "params must be a list."}), 400
        one = bool(payload.get("one"))
        if not db_path.exists():
            return jsonify({"ok": False, "error": f"Database not found: {db_path}"}), 404
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = [dict(row) for row in conn.execute(sql, tuple(params)).fetchmany(MAX_QUERY_ROWS + 1)]
        truncated = len(rows) > MAX_QUERY_ROWS
        rows = rows[:MAX_QUERY_ROWS]
        if one:
            rows = rows[:1]
        return jsonify({"ok": True, "database": payload.get("database") or "main", "count": len(rows), "truncated": truncated, "rows": rows})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@APP.get("/ligase-pdbs/<ligase>")
def ligase_pdbs(ligase):
    folder = _safe_ligase_dir(ligase) / "PDB"
    if not folder.is_dir():
        return jsonify([])
    return jsonify(sorted([p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdb"]))


@APP.get("/file/pdb/<ligase>/<path:filename>")
def file_pdb(ligase, filename):
    folder = _safe_ligase_dir(ligase) / "PDB"
    path = _safe_file(folder, filename, {".pdb"})
    return send_file(path, mimetype="chemical/x-pdb", as_attachment=False, max_age=0)


@APP.get("/file/sdf/<ligase>/<path:filename>")
def file_sdf(ligase, filename):
    ligase_dir = _safe_ligase_dir(ligase)
    core = Path(filename).stem
    core_no_variant = re.sub(r"_\d+$", "", core)
    candidate_names = [f"{core_no_variant}.sdf", f"{core_no_variant}_1.sdf"]
    if core.endswith(".sdf"):
        candidate_names.insert(0, core)

    for folder in [ligase_dir / "SDF_4Download", ligase_dir / "SDF"]:
        if not folder.is_dir():
            continue
        for candidate_name in dict.fromkeys(candidate_names):
            candidate = (folder / candidate_name).resolve()
            if candidate.is_file() and _safe_under(folder, candidate):
                return send_file(candidate, mimetype="chemical/x-mdl-sdfile", as_attachment=True, download_name=candidate.name, max_age=0)
        pattern = re.compile(rf"^{re.escape(core_no_variant)}_(\d+)\.sdf$", re.IGNORECASE)
        for path in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
            if path.is_file() and pattern.match(path.name):
                return send_file(path, mimetype="chemical/x-mdl-sdfile", as_attachment=True, download_name=path.name, max_age=0)
    abort(404, description=f"SDF not found: {ligase}/{filename}")


@APP.get("/download/ligase/<ligase>/<asset_type>.zip")
def download_ligase_zip(ligase, asset_type):
    if asset_type.lower() not in {"pdbs", "sdfs", "all", "structures"}:
        abort(400, description="asset_type must be one of: pdbs, sdfs, all, structures")
    ligase_dir = _safe_ligase_dir(ligase)
    files = [(f"{ligase_dir.name}/{label}/{path.name}", path) for label, path in _files_from_dirs(_asset_dirs(ligase_dir, asset_type))]
    return _zip_response(files, f"E3Ligandalyzer_{ligase_dir.name}_{asset_type}.zip", {
        "scope": "ligase",
        "ligase": ligase_dir.name,
        "asset_type": asset_type,
        "file_count": len(files),
    })


@APP.get("/download/all/<asset_type>.zip")
def download_all_zip(asset_type):
    if asset_type.lower() not in {"pdbs", "sdfs", "all", "structures"}:
        abort(400, description="asset_type must be one of: pdbs, sdfs, all, structures")
    files = []
    for ligase_dir in _list_ligase_dirs():
        for label, path in _files_from_dirs(_asset_dirs(ligase_dir, asset_type)):
            files.append((f"{ligase_dir.name}/{label}/{path.name}", path))
    return _zip_response(files, f"E3Ligandalyzer_ALL_{asset_type}.zip", {
        "scope": "all_ligases",
        "asset_type": asset_type,
        "file_count": len(files),
    })


@APP.get("/download/table/<table_name>.csv")
def download_table(table_name):
    if table_name not in PUBLIC_DOWNLOAD_TABLES or not SAFE_TABLE_RE.fullmatch(table_name):
        abort(404, description=f"Table is not available for export: {table_name}")
    if not DB_PATH.exists():
        abort(404, description=f"Database not found: {DB_PATH}")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=E3Ligandalyzer_{table_name}.csv"},
    )


if __name__ == "__main__":
    APP.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5095")))
