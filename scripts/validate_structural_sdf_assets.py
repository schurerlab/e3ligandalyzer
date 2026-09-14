#!/usr/bin/env python3
"""Validate structural-SDF derived assets and write an additive manifest."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import math
import sqlite3
from collections import Counter
from pathlib import Path

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("structural_builder", ROOT / "scripts" / "materialize_observed_structural_sdfs.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def graph_signature(molecule):
    return (
        tuple(atom.GetSymbol() for atom in molecule.GetAtoms()),
        tuple(sorted((min(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()), max(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()), str(bond.GetBondType()), bond.GetIsAromatic()) for bond in molecule.GetBonds())),
    )


def coordinate_error(actual, expected) -> tuple[float, float]:
    distances = []
    for index in range(actual.GetNumAtoms()):
        a, b = actual.GetConformer().GetAtomPosition(index), expected.GetConformer().GetAtomPosition(index)
        distances.append(math.dist((a.x, a.y, a.z), (b.x, b.y, b.z)))
    return math.sqrt(sum(distance * distance for distance in distances) / len(distances)), max(distances)


def expected_molecule(database_path: Path, record, mappings):
    source = Path(str(record["Source_SDF"] or ""))
    try:
        molecule, omitted = builder.subset_with_source_coordinates(source, Path(record["Step4_PDB"]), mappings)
        return molecule, omitted, "VERIFIED_EXACT_SDF", str(source)
    except ValueError:
        errors = []
        for topology in builder.r2_topology_paths(database_path, record["Recruiter_Instance_ID"], str(record["chemistry_source_path"] or "")):
            try:
                molecule, omitted = builder.subset_with_mapped_topology(topology, Path(str(record["coordinate_source_path"] or record["Step4_PDB"])), mappings)
                return molecule, omitted, "TOPOLOGY_PLUS_DEPOSITED_XYZ", str(topology)
            except ValueError as error:
                errors.append(str(error))
        raise ValueError(errors[-1])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--asset-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    database = sqlite3.connect(f"file:{args.database.resolve()}?mode=ro", uri=True)
    database.row_factory = sqlite3.Row
    records = database.execute("""
        SELECT i.Recruiter_Instance_ID, i.Ligase, i.pdb_id, i.Source_Entity_ID,
               i.Recruiter_Entity_Type, i.Source_SDF, i.Step4_PDB,
               a.Chemistry_Source_Class, a.chemistry_source_path, a.coordinate_source_path
        FROM Recruiter_Instance_Catalog AS i
        JOIN R2_2D_Chemistry_Assets AS a USING (Recruiter_Instance_ID)
        WHERE i.Registry_Status = 'ACTIVE' AND a.Asset_Status = 'READY'
        ORDER BY i.Recruiter_Instance_ID
    """).fetchall()
    rows, failures = [], []
    for record in records:
        instance_id = record["Recruiter_Instance_ID"]
        output = args.asset_root / "coordinates" / instance_id / "structure_observed_3d.sdf"
        try:
            mappings = database.execute("""
                SELECT atom_id, instance_sdf_atom_index, chemistry_atom_index,
                       mapping_source_class
                FROM Ligase_Ligands_Smiles_3DMapped
                WHERE Recruiter_Instance_ID = ? ORDER BY atom_id
            """, (instance_id,)).fetchall()
            expected, omitted, route, topology_source = expected_molecule(args.database, record, mappings)
            supplier = Chem.SDMolSupplier(str(output), sanitize=False, removeHs=False)
            actual = next((molecule for molecule in supplier if molecule is not None), None)
            if actual is None or not actual.GetNumAtoms() or not actual.GetNumConformers() or not actual.GetConformer().Is3D():
                raise ValueError("PARSE_OR_3D_CONFORMER_FAILURE")
            if actual.GetProp("RECRUITER_INSTANCE_ID") != instance_id or actual.GetProp("PDB_ID") != record["pdb_id"]:
                raise ValueError("INSTANCE_OR_PDB_IDENTITY_MISMATCH")
            if graph_signature(actual) != graph_signature(expected):
                raise ValueError("TOPOLOGY_MISMATCH")
            rmsd, maximum = coordinate_error(actual, expected)
            if maximum > 0.001:
                raise ValueError("DEPOSITED_COORDINATE_MISMATCH")
            positions = [actual.GetConformer().GetAtomPosition(index).z for index in range(actual.GetNumAtoms())]
            rows.append({
                "Recruiter_Instance_ID": instance_id, "Ligase": record["Ligase"], "PDB_ID": record["pdb_id"],
                "Source_Entity_ID": record["Source_Entity_ID"], "Recruiter_Entity_Type": record["Recruiter_Entity_Type"],
                "R2_Chemistry_Source_Class": record["Chemistry_Source_Class"], "Structural_SDF_Construction_Route": route,
                "Observed_Atom_Count": actual.GetNumAtoms(), "Chemistry_Atom_Count": actual.GetNumAtoms() + omitted,
                "Omitted_Unobserved_Atom_Count": omitted, "Bond_Count": actual.GetNumBonds(),
                "Coordinate_Source": record["coordinate_source_path"] or record["Step4_PDB"], "Topology_Source": topology_source,
                "Atom_Mapping_Source": ";".join(sorted({str(row["mapping_source_class"] or "") for row in mappings})),
                "Coordinate_Validation": "PASS", "Coordinate_RMSD_A": f"{rmsd:.6f}", "Coordinate_Max_Deviation_A": f"{maximum:.6f}",
                "Z_Min_A": f"{min(positions):.6f}", "Z_Max_A": f"{max(positions):.6f}", "Z_Range_A": f"{max(positions)-min(positions):.6f}",
                "Observed_vs_Complete": "OBSERVED_ONLY; complete chemistry retained separately" if record["Recruiter_Entity_Type"] == "BIRD_PRD" else "OBSERVED_INSTANCE_STRUCTURE",
                "Output_Structural_SDF": str(output), "SHA256": sha256(output), "Validation_Status": "PASS",
            })
        except Exception as error:
            failures.append({"Recruiter_Instance_ID": instance_id, "Validation_Status": "FAIL", "Reason": str(error)})
    database.close()
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["Recruiter_Instance_ID", "Validation_Status"]
    with args.manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    failure_path = args.manifest.with_name(args.manifest.stem + "_Failures.csv")
    with failure_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Recruiter_Instance_ID", "Validation_Status", "Reason"]); writer.writeheader(); writer.writerows(failures)
    print({"ready": len(records), "passed": len(rows), "failed": len(failures), "routes": dict(Counter(row["Structural_SDF_Construction_Route"] for row in rows))})
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
