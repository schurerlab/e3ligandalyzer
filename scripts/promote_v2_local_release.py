#!/usr/bin/env python3
"""Build and atomically select the immutable local E3 Ligandalyzer V2 bundle.

This promotion intentionally copies only assets named by the validated staging
catalogue.  It never merges the historical application ``Ligases`` tree.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE = Path("/Users/jxs794/Desktop/E3Ligandalyzer/Rebuild_Staging/v1.0-lock-20260908")
RELEASES = APP_ROOT / "releases"
RELEASE_NAME = "v1.0-locked-20260908"
DB_NAME = "E3_Ligandalyzer_v1.0_locked_20260908.sqlite"
STAGING_DB_NAME = "E3_Ligandalyzer_v1.0_locked_20260908.sqlite"
EXPECTED_DB_SHA256 = "33a80121ef1fdeb0bde917e860d89a5e3c80fcc0ef9609b86fd4c14bf0ab59fe"
EXCLUDED_SOURCE_KEYS = {
    "2AXI|1|B|PRD_000326", "2AXI|1|A|201|.|MPO", "8GCG|1|B|7|.|A1A2J",
    "9GFK|1|J|11|.|A1IL6", "9GFK|1|F|11|.|A1IL6", "9GFK|1|G|11|.|A1IL6",
    "9GFK|1|H|11|.|A1IL6",
}
POST_CUTOFF_TRIM21_PDB_IDS = set()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sqlite_counts(path: Path) -> dict[str, int]:
    queries = {
        "recruiter_entities": "SELECT COUNT(*) FROM Recruiter_Catalog",
        "permanent_recruiter_namespace": "SELECT COUNT(*) FROM Recruiter_Registry",
        "recruiter_instances": "SELECT COUNT(*) FROM Recruiter_Instance_Catalog",
        "permanent_instance_namespace": "SELECT COUNT(*) FROM Recruiter_Instance_Registry",
        "scaffolds": "SELECT COUNT(*) FROM Scaffold_Catalog",
        "permanent_scaffold_namespace": "SELECT COUNT(*) FROM Scaffold_Registry",
        "ligases": "SELECT COUNT(DISTINCT Ligase) FROM Ligase_Recruiter_Catalog",
        "distinct_source_pdbs": "SELECT COUNT(DISTINCT pdb_id) FROM Recruiter_Instance_Catalog",
        "ligase_recruiter_rows": "SELECT COUNT(*) FROM Ligase_Recruiter_Catalog",
        "ligase_scaffold_rows": "SELECT COUNT(*) FROM Ligase_Scaffold_Data",
        "sasa_summary": "SELECT COUNT(*) FROM Ligase_Ligand_SASA_summary",
        "sasa_atoms": "SELECT COUNT(*) FROM Ligase_Ligand_SASA_atoms",
    }
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
        return {key: int(conn.execute(sql).fetchone()[0]) for key, sql in queries.items()}


def safe_component(value: str) -> str:
    if not value or any(token in value for token in ("/", "\\", "..")):
        raise RuntimeError(f"Unsafe release asset component: {value!r}")
    return value


def copy_asset(source: Path, destination: Path) -> str:
    if not source.is_file():
        raise RuntimeError(f"Validated staging asset is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    source_hash, destination_hash = sha256(source), sha256(destination)
    if source_hash != destination_hash:
        raise RuntimeError(f"Hash mismatch after copying {source}")
    return destination_hash


def readonly_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def archive_legacy_release() -> Path:
    archive = RELEASES / "v1.0-pre-corrected"
    archive.mkdir(parents=True, exist_ok=True)
    legacy_db = APP_ROOT / "data" / DB_NAME
    legacy_assets = APP_ROOT / "Ligases"
    archive_db = archive / "database" / DB_NAME
    archive_db.parent.mkdir(exist_ok=True)
    if legacy_db.is_file() and not archive_db.exists():
        temporary = archive_db.with_suffix(".sqlite.tmp")
        shutil.copy2(legacy_db, temporary)
        if sha256(temporary) != sha256(legacy_db):
            raise RuntimeError("Legacy rollback database copy hash mismatch.")
        os.replace(temporary, archive_db)
    asset_root = archive / "assets"
    # The archive keeps a versioned root with an internal reference, so the
    # normal release-root asset resolver continues to work after rollback.
    if asset_root.is_symlink():
        asset_root.unlink()
    asset_root.mkdir(exist_ok=True)
    asset_link = asset_root / "Ligases"
    if not asset_link.exists() and not asset_link.is_symlink():
        asset_link.symlink_to(legacy_assets)
    inventory = []
    if legacy_assets.is_dir():
        for asset in sorted(legacy_assets.rglob("*")):
            if asset.is_file() and asset.suffix.lower() in {".pdb", ".sdf", ".cif"}:
                inventory.append({
                    "relative_path": str(asset.relative_to(legacy_assets)),
                    "size_bytes": str(asset.stat().st_size),
                    "sha256": sha256(asset),
                })
    write_csv(archive / "legacy_asset_inventory.csv", inventory,
              ["relative_path", "size_bytes", "sha256"])
    manifests = archive / "manifests"
    manifests.mkdir(exist_ok=True)
    legacy_rows = []
    if archive_db.is_file():
        with sqlite3.connect(f"file:{archive_db}?mode=ro", uri=True) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(Recruiter_Instance_Catalog)")}
            status_clause = "WHERE Registry_Status = 'ACTIVE'" if "Registry_Status" in columns else ""
            records = conn.execute(
                "SELECT Recruiter_Instance_ID, Recruiter_ID, Source_Instance_Key, Ligase, pdb_id, "
                "Recruiter_Entity_Type, Source_Entity_ID, Step4_PDB, Source_SDF "
                f"FROM Recruiter_Instance_Catalog {status_clause}"
            ).fetchall()
        for record in records:
            iid, rid, source_key, ligase, pdb_id, entity_type, source_entity, step4, source_sdf = record
            pdb_name, sdf_name = Path(str(step4 or "")).name, Path(str(source_sdf or "")).name
            pdb_path = legacy_assets / str(ligase) / "PDB" / pdb_name
            sdf_path = legacy_assets / str(ligase) / "SDF_4Download" / sdf_name
            if not sdf_path.is_file():
                sdf_path = legacy_assets / str(ligase) / "SDF" / sdf_name
            legacy_rows.append({
                "Recruiter_Instance_ID": iid, "Recruiter_ID": rid, "Source_Instance_Key": source_key,
                "Ligase": ligase, "pdb_id": pdb_id, "Recruiter_Entity_Type": entity_type,
                "Source_Entity_ID": source_entity, "PDB_Source_Path": str(pdb_path),
                "PDB_Web_Path": f"Ligases/{ligase}/PDB/{pdb_name}" if pdb_path.is_file() else "",
                "PDB_SHA256": sha256(pdb_path) if pdb_path.is_file() else "",
                "SDF_Source_Path": str(sdf_path) if sdf_path.is_file() else "",
                "SDF_Web_Path": f"Ligases/{ligase}/SDF_4Download/{sdf_name}" if sdf_path.is_file() else "",
                "SDF_SHA256": sha256(sdf_path) if sdf_path.is_file() else "",
                "PRD_ID": source_entity if entity_type == "BIRD_PRD" else "", "CIF_Source_Path": "",
                "Asset_Status": "LEGACY_ARCHIVE_REFERENCE", "Warnings": "Legacy rollback reference",
            })
    web_fields = ["Recruiter_Instance_ID", "Recruiter_ID", "Source_Instance_Key", "Ligase", "pdb_id",
                  "Recruiter_Entity_Type", "Source_Entity_ID", "PDB_Source_Path", "PDB_Web_Path", "PDB_SHA256",
                  "SDF_Source_Path", "SDF_Web_Path", "SDF_SHA256", "PRD_ID", "CIF_Source_Path", "Asset_Status", "Warnings"]
    write_csv(manifests / "Web_Asset_Manifest.csv", legacy_rows, web_fields)
    rollback_manifest = {
        "release_id": "v1.0-pre-corrected",
        "database": {"relative_path": f"database/{DB_NAME}", "sha256": sha256(archive_db) if archive_db.is_file() else None},
        "assets": {"root": "assets", "legacy_asset_inventory_sha256": sha256(archive / "legacy_asset_inventory.csv"),
                   "web_asset_manifest_sha256": sha256(manifests / "Web_Asset_Manifest.csv")},
        "asset_reference": str(legacy_assets.resolve()),
    }
    (manifests / "release_manifest.json").write_text(json.dumps(rollback_manifest, indent=2) + "\n", encoding="utf-8")
    (archive / "release_manifest.json").write_text(json.dumps(rollback_manifest, indent=2) + "\n", encoding="utf-8")
    payload = {
        "archive_version": "v1.0-pre-corrected",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "legacy_database_path": str(legacy_db.resolve()),
        "legacy_database_sha256": sha256(legacy_db) if legacy_db.is_file() else None,
        "legacy_asset_root": str(legacy_assets.resolve()),
        "legacy_asset_root_preserved_in_place": True,
        "rollback_bundle_database_copy": str(archive_db.resolve()),
        "rollback_bundle_assets_symlink": str(asset_link),
        "legacy_asset_file_count": len(inventory),
        "prior_environment": {
            "E3_DATABASE_PATH": os.environ.get("E3_DATABASE_PATH"),
            "E3_LOCAL_DB_PATH": os.environ.get("E3_LOCAL_DB_PATH"),
            "E3_RELEASE_ROOT": os.environ.get("E3_RELEASE_ROOT"),
        },
        "rollback": "Retarget releases/current to the prior release only after validating its own release manifest.",
    }
    (archive / "rollback_snapshot.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return archive


def build(stage: Path, switch: bool) -> Path:
    stage = stage.resolve()
    source_db = stage / STAGING_DB_NAME
    if sha256(source_db) != EXPECTED_DB_SHA256:
        raise RuntimeError("Staging SQLite hash does not match the validated corrected release.")
    staged_manifest = json.loads((stage / "V1_September08_Staged_Release_Manifest.json").read_text())
    expected_instances = staged_manifest["counts"]["active_source_instances"]
    catalog = read_csv(stage / "Ligase_Table/Database_Ready/Recruiter_Instance_Catalog.csv")
    if len(catalog) != expected_instances or any(row["Registry_Status"] != "ACTIVE" for row in catalog):
        raise RuntimeError("Staging catalogue does not reconcile the staged active-instance contract.")
    if any(row["pdb_id"] in POST_CUTOFF_TRIM21_PDB_IDS for row in catalog):
        raise RuntimeError("Post-cutoff TRIM21 PDB codes must not enter the corrected web release.")
    if {row["Source_Instance_Key"] for row in catalog} & EXCLUDED_SOURCE_KEYS:
        raise RuntimeError("Excluded MDM2 source instances must not enter the corrected web release.")

    chemistry_sdf = {
        path.name.removesuffix("_ideal.sdf"): path
        for path in (stage / "Chemistry_Input" / "SDF").glob("*_ideal.sdf")
    }
    a1iev = stage / "Chemistry_Input" / "CCD_Derived" / "A1IEV_from_CCD_InChI.sdf"
    chemistry_sdf["A1IEV"] = a1iev
    if not a1iev.is_file():
        raise RuntimeError("Required staging-derived A1IEV InChI SDF is missing.")

    RELEASES.mkdir(parents=True, exist_ok=True)
    final_root = RELEASES / RELEASE_NAME
    if final_root.exists():
        raise RuntimeError(f"Refusing to overwrite existing release: {final_root}")
    tmp_root = Path(tempfile.mkdtemp(prefix=f".{RELEASE_NAME}.", dir=RELEASES))
    try:
        db_dest = tmp_root / "database" / DB_NAME
        db_dest.parent.mkdir(parents=True)
        shutil.copy2(source_db, db_dest)
        if sha256(db_dest) != EXPECTED_DB_SHA256:
            raise RuntimeError("Copied SQLite hash mismatch.")
        counts = sqlite_counts(db_dest)
        final = staged_manifest["counts"]
        required = {"recruiter_entities": final["canonical_active_recruiters"], "recruiter_instances": final["active_source_instances"], "scaffolds": final["active_scaffolds"], "ligases": final["distinct_ligases"], "ligase_recruiter_rows": final["ligase_recruiter_relationships"], "ligase_scaffold_rows": final["ligase_scaffold_relationships"], "sasa_summary": final["active_source_instances"], "sasa_atoms": final["sasa_atom_rows"]}
        if any(counts[key] != value for key, value in required.items()):
            raise RuntimeError(f"Copied SQLite release counts do not match staged release manifest: {counts}")

        manifest_rows: list[dict[str, str]] = []
        copied_sdf: dict[str, tuple[str, str]] = {}
        pdb_destinations: set[str] = set()
        for row in catalog:
            instance_id = safe_component(row["Recruiter_Instance_ID"])
            ligase = safe_component(row["Ligase"])
            pdb_source = stage / "PRosettaC_PDB" / ligase / Path(row["Step4_PDB"]).name
            pdb_relative = Path("Ligases") / ligase / "PDB" / f"{instance_id}.pdb"
            if str(pdb_relative) in pdb_destinations:
                raise RuntimeError(f"Duplicate web PDB path: {pdb_relative}")
            pdb_destinations.add(str(pdb_relative))
            pdb_hash = copy_asset(pdb_source, tmp_root / "assets" / pdb_relative)

            source_entity = row["Source_Entity_ID"]
            sdf_source = chemistry_sdf.get(source_entity)
            sdf_relative, sdf_hash, warning = "", "", ""
            if row["Recruiter_Entity_Type"] == "BIRD_PRD":
                warning = "WHOLE_PRD_PDB_NO_FRAGMENT_SDF"
            elif not sdf_source:
                warning = "NO_STAGING_CHEMISTRY_SDF"
            else:
                sdf_relative_path = Path("chemistry") / "SDF" / f"{safe_component(source_entity)}.sdf"
                key = str(sdf_relative_path)
                if key not in copied_sdf:
                    copied_sdf[key] = (str(sdf_source), copy_asset(sdf_source, tmp_root / "assets" / sdf_relative_path))
                sdf_relative, sdf_hash = key, copied_sdf[key][1]
                if source_entity == "A1IEV":
                    warning = "A1IEV_STAGING_DERIVED_INCHI_SDF"

            manifest_rows.append({
                "Recruiter_Instance_ID": instance_id,
                "Recruiter_ID": row["Recruiter_ID"],
                "Source_Instance_Key": row["Source_Instance_Key"], "Ligase": ligase,
                "pdb_id": row["pdb_id"], "Recruiter_Entity_Type": row["Recruiter_Entity_Type"],
                "Source_Entity_ID": source_entity, "PDB_Source_Path": str(pdb_source),
                "PDB_Web_Path": str(pdb_relative), "PDB_SHA256": pdb_hash,
                "SDF_Source_Path": str(sdf_source) if sdf_source else "",
                "SDF_Web_Path": sdf_relative, "SDF_SHA256": sdf_hash,
                "PRD_ID": source_entity if row["Recruiter_Entity_Type"] == "BIRD_PRD" else "",
                "CIF_Source_Path": "", "Asset_Status": "PDB_READY" + ("_SDF_READY" if sdf_relative else ""),
                "Warnings": warning,
            })

        fields = list(manifest_rows[0])
        manifest_dir = tmp_root / "manifests"
        manifest_dir.mkdir(parents=True)
        write_csv(manifest_dir / "Web_Asset_Manifest.csv", manifest_rows, fields)
        used_pdb_sources = {row["PDB_Source_Path"] for row in manifest_rows}
        all_stage_pdbs = {str(path) for path in (stage / "PRosettaC_PDB").rglob("*.pdb")}
        orphan_rows = [{"Asset_Type": "PDB", "Source_Path": path, "Reason": "NOT_IN_ACTIVE_WEB_CATALOG"}
                       for path in sorted(all_stage_pdbs - used_pdb_sources)]
        # The only staged PDB corpus is the active 1:1 source set; any orphan is a promotion failure.
        if orphan_rows:
            raise RuntimeError(f"PDB orphan audit failed: {len(orphan_rows)} unreferenced staging PDBs")
        asset_audit_rows = []
        for relative in sorted((tmp_root / "assets").rglob("*")):
            if not relative.is_file():
                continue
            rel_text = str(relative.relative_to(tmp_root / "assets"))
            asset_audit_rows.append({
                "Asset_Path": rel_text,
                "Classification": "ACTIVE_REFERENCED" if rel_text.startswith("Ligases/") else "SHARED_ACTIVE_CHEMISTRY",
                "Reason": "Exact active instance PDB" if rel_text.startswith("Ligases/") else "Shared staging chemistry SDF",
            })
        write_csv(manifest_dir / "Web_Asset_Orphan_Audit.csv", asset_audit_rows,
                  ["Asset_Path", "Classification", "Reason"])

        asset_hashes = {str(path.relative_to(tmp_root / "assets")): sha256(path)
                        for path in sorted((tmp_root / "assets").rglob("*")) if path.is_file()}
        release_manifest = {
            "release_id": RELEASE_NAME, "release_type": "local_immutable_scientific_bundle",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "database_cutoff_date": "2026-09-08",
            "database": {"filename": DB_NAME, "relative_path": f"database/{DB_NAME}",
                         "sha256": EXPECTED_DB_SHA256, "size_bytes": db_dest.stat().st_size,
                         "integrity_check": "ok", "counts": counts},
            "assets": {"root": "assets", "pdb_count": len(manifest_rows),
                       "chemistry_sdf_count": len(copied_sdf), "prd_whole_entity_count": final["bird_prd_physical_observations"],
                       "orphan_count": 0, "hashes": asset_hashes,
                       "web_asset_manifest_sha256": sha256(manifest_dir / "Web_Asset_Manifest.csv")},
            "asset_policy": {
                "pdb": "Exact selected Step4 PRosettaC physical-instance PDB; one per Recruiter_Instance_ID.",
                "sdf": "Optional shared staging chemistry SDF by Source_Entity_ID; BIRD PRDs expose whole-entity PDB only.",
                "a1iev": "Chemistry SDF is the staging-derived A1IEV_from_CCD_InChI.sdf artifact.",
            },
            "exclusions": {"unapproved_mdm2_source_instances": sorted(EXCLUDED_SOURCE_KEYS)},
            "post_cutoff_trim21_pdb_ids": [],
            "source_staging_release_path": str(stage),
        }
        (manifest_dir / "release_manifest.json").write_text(json.dumps(release_manifest, indent=2) + "\n", encoding="utf-8")
        (tmp_root / "release_manifest.json").write_text(json.dumps(release_manifest, indent=2) + "\n", encoding="utf-8")
        readonly_tree(tmp_root)
        os.replace(tmp_root, final_root)
        archive_legacy_release()
        if switch:
            link_tmp = RELEASES / f".current.{os.getpid()}"
            link_tmp.symlink_to(RELEASE_NAME)
            os.replace(link_tmp, RELEASES / "current")
        return final_root
    except Exception:
        if tmp_root.exists():
            shutil.rmtree(tmp_root)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, default=DEFAULT_STAGE)
    parser.add_argument("--switch", action="store_true", help="Atomically point releases/current at the completed bundle.")
    args = parser.parse_args()
    print(build(args.stage, args.switch))


if __name__ == "__main__":
    main()
