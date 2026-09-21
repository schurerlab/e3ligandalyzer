#!/usr/bin/env python
"""Validate the assembled V1 Beta R2 assets without changing their bytes."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sqlite3
from pathlib import Path

from rdkit import Chem

APP = Path(__file__).resolve().parents[1]
SCI = Path("/Users/jxs794/Desktop/E3Ligandalyzer")
RELEASE = APP / "releases/v1.0-beta-r2-20260912"
AUDIT = SCI / "Corpus_Audit"
EXPECTED_DB_SHA = "33afb375ade1cbbb428230bfc226fe0b5b8a43a3231bfa699ba5ddc576f89689"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sdf_molecule(path: Path):
    molecule = Chem.MolFromMolFile(str(path), sanitize=True, removeHs=False)
    if molecule is None or not molecule.GetNumAtoms() or not molecule.GetNumConformers():
        raise ValueError("RDKit parse/sanitize/conformer failure")
    conformer = molecule.GetConformer()
    for atom in molecule.GetAtoms():
        point = conformer.GetAtomPosition(atom.GetIdx())
        if not all(math.isfinite(value) for value in (point.x, point.y, point.z)):
            raise ValueError("non-finite coordinate")
    return molecule


def main() -> None:
    manifest_path = RELEASE / "manifests/Web_Asset_Manifest.csv"
    database = RELEASE / "database/E3_Ligandalyzer_v1.0_locked_20260908.sqlite"
    rows = list(csv.DictReader(manifest_path.open(newline="")))
    if len(rows) != 1378:
        raise RuntimeError(f"expected 1378 manifest rows, found {len(rows)}")
    if sha256(database) != EXPECTED_DB_SHA:
        raise RuntimeError("R1 SQLite fingerprint changed")

    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    details = []
    failures = []
    exact_rows = 0
    exact_with_mappings = 0
    coordinate_deltas = []
    pdb_hash_failures = 0
    sdf_hash_failures = 0
    for row in rows:
        iid = row["Recruiter_Instance_ID"]
        pdb_path = RELEASE / "assets" / row["PDB_Web_Path"]
        pdb_ok = pdb_path.is_file() and sha256(pdb_path) == row["PDB_SHA256"]
        if not pdb_ok:
            pdb_hash_failures += 1
            failures.append(f"{iid}: PDB missing or hash mismatch")
        record = {
            "Recruiter_Instance_ID": iid,
            "SDF_Asset_Type": row["SDF_Asset_Type"],
            "PDB_hash_status": "PASS" if pdb_ok else "FAIL",
            "SDF_hash_status": "NOT_DECLARED",
            "SDF_parse_status": "NOT_DECLARED",
            "validated_mapping_atoms": 0,
            "coordinate_rmsd_A": "",
            "coordinate_max_deviation_A": "",
            "coordinate_validation": "NOT_APPLICABLE",
            "failure": "",
        }
        sdf_rel = row["SDF_Web_Path"]
        if sdf_rel:
            sdf_path = RELEASE / "assets" / sdf_rel
            sdf_ok = sdf_path.is_file() and sha256(sdf_path) == row["SDF_SHA256"]
            record["SDF_hash_status"] = "PASS" if sdf_ok else "FAIL"
            if not sdf_ok:
                sdf_hash_failures += 1
                message = f"{iid}: SDF missing or hash mismatch"
                failures.append(message)
                record["failure"] = message
            else:
                try:
                    molecule = sdf_molecule(sdf_path)
                    record["SDF_parse_status"] = "PASS"
                except ValueError as error:
                    message = f"{iid}: {error}"
                    failures.append(message)
                    record["SDF_parse_status"] = "FAIL"
                    record["failure"] = message
                    molecule = None
                if row["SDF_Asset_Type"] == "EXACT_INSTANCE_SDF_AVAILABLE" and molecule:
                    exact_rows += 1
                    mapped = connection.execute(
                        """
                        SELECT instance_sdf_atom_index, x, y, z
                        FROM Ligase_Ligands_Smiles_3DMapped
                        WHERE Recruiter_Instance_ID = ?
                          AND Mapping_Status = 'VALIDATED_CANONICAL_ATOM_MAPPING'
                          AND instance_sdf_atom_index IS NOT NULL
                        ORDER BY atom_id
                        """,
                        (iid,),
                    ).fetchall()
                    record["validated_mapping_atoms"] = len(mapped)
                    if mapped:
                        exact_with_mappings += 1
                        squared, deltas = [], []
                        conformer = molecule.GetConformer()
                        for atom in mapped:
                            index = int(atom["instance_sdf_atom_index"])
                            if index != atom["instance_sdf_atom_index"] or index >= molecule.GetNumAtoms():
                                raise RuntimeError(f"{iid}: invalid mapped SDF atom index")
                            point = conformer.GetAtomPosition(index)
                            delta = math.dist((point.x, point.y, point.z), (atom["x"], atom["y"], atom["z"]))
                            squared.append(delta * delta)
                            deltas.append(delta)
                        rmsd = math.sqrt(sum(squared) / len(squared))
                        maximum = max(deltas)
                        coordinate_deltas.extend(deltas)
                        record["coordinate_rmsd_A"] = f"{rmsd:.9f}"
                        record["coordinate_max_deviation_A"] = f"{maximum:.9f}"
                        # Both generated SDF and exact PDB coordinates use three decimals;
                        # half of the final serialized decimal place is the expected bound.
                        record["coordinate_validation"] = "PASS" if maximum <= 0.000500001 else "FAIL"
                        if record["coordinate_validation"] == "FAIL":
                            message = f"{iid}: mapped coordinate deviation {maximum:.9f} A"
                            failures.append(message)
                            record["failure"] = message
                    else:
                        record["coordinate_validation"] = "NO_VALIDATED_CANONICAL_MAPPING"
        details.append(record)
    connection.close()

    AUDIT.mkdir(parents=True, exist_ok=True)
    output = AUDIT / "V1_Beta_R2_Exact_SDF_Validation.csv"
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=details[0].keys())
        writer.writeheader()
        writer.writerows(details)
    summary = {
        "release": str(RELEASE),
        "sqlite_sha256": sha256(database),
        "active_instances": len(rows),
        "exact_instance_sdf_rows": exact_rows,
        "exact_instance_sdf_rows_with_validated_mapping": exact_with_mappings,
        "mapped_coordinate_comparisons": len(coordinate_deltas),
        "maximum_mapped_coordinate_deviation_A": max(coordinate_deltas, default=0.0),
        "pdb_hash_failures": pdb_hash_failures,
        "sdf_hash_failures": sdf_hash_failures,
        "failures": failures,
    }
    (AUDIT / "V1_Beta_R2_Exact_SDF_Validation.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
