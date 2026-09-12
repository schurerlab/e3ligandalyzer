"""Read-only access to the E3 Ligandalyzer V1 scientific release.

The Flask application consumes the immutable SQLite release through this small
query service.  It deliberately has no write methods and never opens the
scientific database outside SQLite's read-only URI mode.
"""

from __future__ import annotations

import os
import sqlite3
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "E3_Ligandalyzer_v1.0.sqlite"
RELEASE_DATABASE_NAME = "E3_Ligandalyzer_v1.0.sqlite"


class E3DatabaseError(RuntimeError):
    """A configuration or read-only release-query failure."""


def remote_backend_enabled() -> bool:
    """Keep transport selection in one place for local and hosted deployments."""
    from Ligases import randy_client

    return randy_client.remote_enabled()


def configured_release_root() -> Optional[Path]:
    """Return the active versioned local release, if one has been selected."""
    raw_root = os.environ.get("E3_RELEASE_ROOT", "").strip()
    if raw_root:
        return Path(raw_root).expanduser()
    current = PROJECT_ROOT / "releases" / "current"
    return current if current.exists() else None


def configured_asset_root() -> Optional[Path]:
    """Return the asset tree coupled to the active versioned release."""
    if remote_backend_enabled():
        return None
    release_root = configured_release_root()
    if release_root:
        return release_root / "assets"
    return None


def release_database_path(release_root: Path) -> Path:
    """Resolve the immutable DB named by this release's own manifest."""
    manifest = release_root / "manifests" / "release_manifest.json"
    try:
        relative = json.loads(manifest.read_text(encoding="utf-8")).get("database", {}).get("relative_path")
    except (OSError, json.JSONDecodeError):
        relative = None
    return release_root / str(relative or f"database/{RELEASE_DATABASE_NAME}")


def configured_database_path() -> Path:
    """Return the active release DB, preferring the coupled release root."""
    if remote_backend_enabled():
        raise E3DatabaseError("Remote backend mode does not expose a local scientific database path.")
    release_root = configured_release_root()
    if release_root:
        return release_database_path(release_root)
    raw_path = (
        os.environ.get("E3_DATABASE_PATH", "").strip()
        or os.environ.get("E3_LOCAL_DB_PATH", "").strip()
    )
    return Path(raw_path).expanduser() if raw_path else DEFAULT_DATABASE_PATH


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@lru_cache(maxsize=4)
def _verified_release_bundle(root_text: str, manifest_mtime_ns: int, db_mtime_ns: int, db_size: int) -> Dict[str, Any]:
    """Validate the release linkage once per manifest/database revision."""
    root = Path(root_text)
    manifest_path = root / "manifests" / "release_manifest.json"
    database_path = release_database_path(root)
    asset_root = root / "assets"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise E3DatabaseError(f"Invalid local release manifest: {manifest_path}") from error
    expected = str(manifest.get("database", {}).get("sha256") or "")
    actual = _sha256(database_path)
    if not expected or actual != expected:
        raise E3DatabaseError("The active local release database does not match its manifest.")
    if not asset_root.is_dir():
        raise E3DatabaseError("The active local release asset tree is unavailable.")
    return {
        "release_root": str(root.resolve()),
        "asset_root": str(asset_root.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "manifest": manifest,
        "database_sha256": actual,
    }


def release_bundle_info() -> Dict[str, Any]:
    """Return verified local bundle provenance, or a legacy-path indicator."""
    if remote_backend_enabled():
        from Ligases import randy_client

        info = randy_client.release_info()
        return {
            "mode": "remote-backend",
            "release_id": f"v{info.get('release_version', 'unknown')}",
            "database_sha256": info.get("database_sha256"),
            "manifest": {
                "release_id": f"v{info.get('release_version', 'unknown')}",
                "release_status": info.get("release_status"),
                "database_cutoff": info.get("database_cutoff"),
                "lockdown_date": info.get("lockdown_date"),
            },
        }
    root = configured_release_root()
    if not root:
        return {"mode": "legacy-path", "database_path": str(configured_database_path().resolve())}
    manifest = root / "manifests" / "release_manifest.json"
    database = release_database_path(root)
    if not manifest.is_file() or not database.is_file():
        raise E3DatabaseError(f"Active local release is incomplete: {root}")
    return _verified_release_bundle(
        str(root.resolve()), manifest.stat().st_mtime_ns,
        database.stat().st_mtime_ns, database.stat().st_size,
    )


class E3Database:
    """Narrow, entity/instance-aware interface to E3_Ligandalyzer V1.0."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path).expanduser() if path else configured_database_path()

    def connect(self) -> sqlite3.Connection:
        path = self.path.resolve()
        if configured_release_root():
            release_bundle_info()
        if not path.is_file():
            raise E3DatabaseError(
                f"E3 Ligandalyzer V1 database was not found at {path}. "
                "Set E3_DATABASE_PATH to the immutable release artifact."
            )
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn

    def _all(self, sql: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        conn = self.connect()
        try:
            return [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]
        finally:
            # ``Connection.__exit__`` commits or rolls back but does not close.
            # Close every short-lived read connection to avoid descriptor leaks
            # under the Flask development server and concurrent production use.
            conn.close()

    def _one(self, sql: str, params: Iterable[Any] = ()) -> Optional[Dict[str, Any]]:
        rows = self._all(sql, params)
        return rows[0] if rows else None

    def execute_read(
        self, sql: str, params: Iterable[Any] = (), one: bool = False
    ) -> List[Dict[str, Any]] | Optional[Dict[str, Any]]:
        """Execute an application read query; reject mutating SQL defensively."""
        statement = str(sql or "").strip()
        if not statement.lower().startswith(("select", "with", "pragma")):
            raise E3DatabaseError("The scientific release only permits read queries.")
        rows = self._all(statement, params)
        return rows[0] if one and rows else (None if one else rows)

    def release_metadata(self) -> Dict[str, str]:
        return {
            row["Key"]: row["Value"]
            for row in self._all("SELECT Key, Value FROM __release_info")
        }

    def release_counts(self) -> Dict[str, int]:
        queries = {
            "recruiter_entities": "SELECT COUNT(*) AS n FROM Recruiter_Catalog",
            "recruiter_instances": "SELECT COUNT(*) AS n FROM Recruiter_Instance_Catalog",
            "scaffolds": "SELECT COUNT(*) AS n FROM Scaffold_Catalog",
            "ligase_recruiter_rows": "SELECT COUNT(*) AS n FROM Ligase_Recruiter_Catalog",
            "ligase_scaffold_rows": "SELECT COUNT(*) AS n FROM Ligase_Scaffold_Data",
            "ligases": "SELECT COUNT(DISTINCT Ligase) AS n FROM Ligase_Recruiter_Catalog",
            "distinct_pdbs": "SELECT COUNT(DISTINCT pdb_id) AS n FROM Recruiter_Instance_Catalog",
            "sasa_atoms": "SELECT COUNT(*) AS n FROM Ligase_Ligand_SASA_atoms",
            "mapped_atoms": "SELECT COUNT(*) AS n FROM Ligase_Ligands_Smiles_3DMapped",
            "source_crosswalk_rows": "SELECT COUNT(*) AS n FROM Source_Entity_Recruiter_Crosswalk",
            "source_ambiguity_rows": "SELECT COUNT(*) AS n FROM Source_Entity_Ambiguity",
        }
        return {name: int(self._one(sql)["n"]) for name, sql in queries.items()}

    def ligases(self) -> List[str]:
        return [
            row["Ligase"]
            for row in self._all(
                "SELECT DISTINCT Ligase FROM Ligase_Recruiter_Catalog ORDER BY Ligase"
            )
        ]

    def recruiter_entity(self, recruiter_id: str) -> Optional[Dict[str, Any]]:
        return self._one(
            """
            SELECT r.*, d.MW, d.Exact_MW, d.LogP, d.TPSA, d.HBA, d.HBD,
                   d.Rotatable_Bonds, d.QED, d.SA_Score, d.BertzCT,
                   d.Lipinski_Pass, d.Veber_Pass, d.Egan_Pass
            FROM Recruiter_Catalog AS r
            LEFT JOIN Ligase_Chemical_Descriptors AS d USING (Recruiter_ID)
            WHERE r.Recruiter_ID = ?
            """,
            (recruiter_id,),
        )

    def recruiter_instances(self, recruiter_id: str) -> List[Dict[str, Any]]:
        return self._all(
            """
            SELECT i.Recruiter_Instance_ID, i.Recruiter_ID, i.Source_Instance_Key,
                   i.Ligase, i.pdb_id, i.Source_Entity_ID, i.Recruiter_Entity_Type,
                   i.Scaffold_ID, i.Recruiter_Asym_ID, i.Recruiter_Residue_ID,
                   i.Model_ID, i.PDB_Model_Num, NULL AS Variant,
                   i.Source_Entity_ID AS Ligand, i.Source_Entity_ID AS Name,
                   i.Recruiter_Entity_Type AS Type,
                   i.Structural_Coordinate_Status, s.SASA_in_complex_A2,
                   s.SASA_free_recruiter_A2, s.Buried_SASA_A2,
                   i.Step4_PDB, i.Source_SDF
            FROM Recruiter_Instance_Catalog AS i
            LEFT JOIN Ligase_Ligand_SASA_summary AS s USING (Recruiter_Instance_ID)
            WHERE i.Recruiter_ID = ?
            ORDER BY i.Ligase, i.pdb_id, i.Recruiter_Instance_ID
            """,
            (recruiter_id,),
        )

    def recruiter_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        return self._one(
            "SELECT * FROM Recruiter_Instance_Catalog WHERE Recruiter_Instance_ID = ?",
            (instance_id,),
        )

    def entity_ligases(self, recruiter_id: str) -> List[Dict[str, Any]]:
        return self._all(
            """
            SELECT Ligase, Recruiter_ID, Scaffold_ID, Scaffold_Class,
                   Physical_Instance_Count, PDB_Count, PDB_IDs,
                   Recruiter_Instance_IDs
            FROM Ligase_Recruiter_Catalog
            WHERE Recruiter_ID = ?
            ORDER BY Ligase
            """,
            (recruiter_id,),
        )

    def scaffold(self, scaffold_id: str) -> Optional[Dict[str, Any]]:
        return self._one("SELECT * FROM Scaffold_Catalog WHERE Scaffold_ID = ?", (scaffold_id,))

    def scaffold_recruiters(self, scaffold_id: str) -> List[Dict[str, Any]]:
        return self._all(
            """
            SELECT r.Recruiter_ID, r.Canonical_SMILES, r.InChIKey, r.Scaffold_ID,
                   GROUP_CONCAT(DISTINCT lr.Ligase) AS Ligases,
                   COUNT(DISTINCT i.Recruiter_Instance_ID) AS Physical_Instance_Count
            FROM Recruiter_Catalog AS r
            LEFT JOIN Ligase_Recruiter_Catalog AS lr USING (Recruiter_ID)
            LEFT JOIN Recruiter_Instance_Catalog AS i USING (Recruiter_ID)
            WHERE r.Scaffold_ID = ?
            GROUP BY r.Recruiter_ID
            ORDER BY r.Recruiter_ID
            """,
            (scaffold_id,),
        )

    def instance_sasa_summary(self, instance_id: str) -> Optional[Dict[str, Any]]:
        return self._one(
            "SELECT * FROM Ligase_Ligand_SASA_summary WHERE Recruiter_Instance_ID = ?",
            (instance_id,),
        )

    def instance_sasa_atoms(self, instance_id: str) -> List[Dict[str, Any]]:
        return self._all(
            """
            SELECT * FROM Ligase_Ligand_SASA_atoms
            WHERE Recruiter_Instance_ID = ?
            ORDER BY atom_id
            """,
            (instance_id,),
        )

    def instance_atom_mapping(self, instance_id: str) -> List[Dict[str, Any]]:
        return self._all(
            """
            SELECT *, atom_id AS SASA_atom_id,
                   NULL AS instance_sdf_atom_index,
                   NULL AS chemistry_atom_index,
                   NULL AS coordinate_distance_A
            FROM Ligase_Ligands_Smiles_3DMapped
            WHERE Recruiter_Instance_ID = ?
            ORDER BY atom_id
            """,
            (instance_id,),
        )

    def entity_for_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Resolve a canonical entity or exact instance identifier without guessing."""
        value = str(identifier or "").strip()
        entity = self.recruiter_entity(value)
        if entity:
            return {"kind": "entity", "entity": entity}
        instance = self.recruiter_instance(value)
        if instance:
            return {"kind": "instance", "instance": instance}
        return None

    def legacy_identifier_entities(self, identifier: str) -> List[str]:
        """Return every entity matched by an exact historical identifier.

        A caller may redirect only when this list has exactly one member.
        """
        value = str(identifier or "").strip()
        if not value:
            return []
        rows = self._all(
            """
            SELECT DISTINCT Recruiter_ID
            FROM (
                SELECT Recruiter_ID
                FROM Recruiter_Instance_Catalog
                WHERE RECRUITER_CODE = ? COLLATE NOCASE
                   OR Source_Entity_ID = ? COLLATE NOCASE
                UNION
                SELECT Recruiter_ID
                FROM Source_Entity_Recruiter_Crosswalk
                WHERE Source_Entity_ID = ? COLLATE NOCASE
            )
            ORDER BY Recruiter_ID
            """,
            (value, value, value),
        )
        return [row["Recruiter_ID"] for row in rows]

    def search_recruiters(self, query: str, limit: int = 50) -> Dict[str, List[Dict[str, Any]]]:
        value = str(query or "").strip()
        if not value:
            return {"entities": [], "instances": []}
        pattern = f"%{value}%"
        limit = max(1, min(int(limit), 200))
        entities = self._all(
            """
            SELECT DISTINCT r.Recruiter_ID, r.Canonical_SMILES, r.InChIKey,
                   r.Scaffold_ID, r.Scaffold_Class
            FROM Recruiter_Catalog AS r
            LEFT JOIN Ligase_Recruiter_Catalog AS lr USING (Recruiter_ID)
            LEFT JOIN Source_Entity_Recruiter_Crosswalk AS src USING (Recruiter_ID)
            WHERE r.Recruiter_ID LIKE ? COLLATE NOCASE
               OR r.Primary_Source_Entity_ID LIKE ? COLLATE NOCASE
               OR src.Source_Entity_ID LIKE ? COLLATE NOCASE
               OR r.Canonical_SMILES LIKE ? COLLATE NOCASE
               OR r.Scaffold_ID LIKE ? COLLATE NOCASE
               OR lr.Ligase LIKE ? COLLATE NOCASE
            ORDER BY r.Recruiter_ID
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, pattern, pattern, limit),
        )
        instances = self._all(
            """
            SELECT Recruiter_Instance_ID, Recruiter_ID, Ligase, pdb_id,
                   Source_Entity_ID, Source_Entity_ID AS Ligand,
                   Source_Entity_ID AS Name, Scaffold_ID
            FROM Recruiter_Instance_Catalog
            WHERE Recruiter_Instance_ID LIKE ? COLLATE NOCASE
               OR pdb_id LIKE ? COLLATE NOCASE
               OR Source_Entity_ID LIKE ? COLLATE NOCASE
               OR Ligand LIKE ? COLLATE NOCASE
               OR Name LIKE ? COLLATE NOCASE
               OR Ligase LIKE ? COLLATE NOCASE
            ORDER BY Recruiter_Instance_ID
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, pattern, pattern, limit),
        )
        return {"entities": entities, "instances": instances}

    def scaffold_data(self, ligase: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = """
            SELECT Ligase, Scaffold_ID,
                   Recruiter_Entity_Count AS Recruiter_Count,
                   Physical_Instance_Count,
                   Scaffold_Identity_SMILES AS Scaffold_SMILES,
                   Murcko_SMILES, Scaffold_Class,
                   Ligase_Scaffold_Connectivity,
                   Total_Recruiter_Entities_For_Ligase AS Total_Recruiters,
                   Recruiter_Entity_Density AS Recruiter_Density_Score
            FROM Ligase_Scaffold_Data
        """
        params: tuple[Any, ...] = ()
        if ligase:
            sql += " WHERE Ligase = ?"
            params = (ligase,)
        return self._all(sql + " ORDER BY Ligase, Recruiter_Count DESC", params)


class RemoteE3Database(E3Database):
    """The same logical V1 read interface backed only by RANDY's API.

    Hosted deployments deliberately inherit the entity/instance methods above:
    their SQL is transported to Randy's read-only query endpoint, never opened
    from a Heroku filesystem.
    """

    def __init__(self):
        from Ligases import randy_client

        if not randy_client.configured():
            raise E3DatabaseError("Remote backend mode requires RANDY E3 URL and authentication configuration.")

    def connect(self) -> sqlite3.Connection:
        raise E3DatabaseError("Remote backend mode does not permit local SQLite connections.")

    def _all(self, sql: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        from Ligases import randy_client

        try:
            return list(randy_client.query("main", sql, params))
        except Exception as error:
            raise E3DatabaseError("Remote V1 scientific query failed.") from error

    def release_metadata(self) -> Dict[str, str]:
        from Ligases import randy_client

        info = randy_client.release_info()
        return {
            "Release_Version": str(info.get("release_version") or "unknown"),
            "Release_Status": str(info.get("release_status") or "unknown"),
            "Release_Date": str(info.get("lockdown_date") or "Unknown"),
            "Database_Cutoff_Date": str(info.get("database_cutoff") or "Unknown"),
            "Database_SHA256": str(info.get("database_sha256") or ""),
            "Schema_Version": "V1",
        }


def get_database() -> E3Database:
    """Construct a database service using the active environment configuration."""
    if remote_backend_enabled():
        return RemoteE3Database()
    return E3Database()
