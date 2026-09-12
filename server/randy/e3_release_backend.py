"""Fail-closed resolver for an immutable E3 scientific release."""
from __future__ import annotations
import csv, hashlib, json, sqlite3
from pathlib import Path

class ReleaseError(RuntimeError): pass

class ReleaseBackend:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        try: self.manifest = json.loads((self.root / "manifests/release_manifest.json").read_text())
        except Exception as exc: raise ReleaseError("invalid E3 release manifest") from exc
        self.db = self.root / self.manifest.get("database", {}).get("relative_path", "")
        self.assets = self.root / "assets"
        self._asset_rows: list[dict[str, str]] | None = None
        if not self.db.is_file() or not self.assets.is_dir(): raise ReleaseError("incomplete E3 release")
        digest = hashlib.sha256(self.db.read_bytes()).hexdigest()
        if digest != self.manifest.get("database", {}).get("sha256"): raise ReleaseError("E3 release database hash mismatch")
        with sqlite3.connect(f"file:{self.db}?mode=ro", uri=True) as conn:
            conn.execute("PRAGMA query_only=ON")
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok": raise ReleaseError("E3 SQLite integrity failure")
    def connect(self):
        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True); conn.row_factory=sqlite3.Row; conn.execute("PRAGMA query_only=ON"); return conn
    def asset_rows(self):
        if self._asset_rows is None:
            with (self.root / "manifests/Web_Asset_Manifest.csv").open(newline="") as h:
                self._asset_rows = list(csv.DictReader(h))
        return self._asset_rows
