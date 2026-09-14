#!/usr/bin/env python3
"""Build observed-coordinate SDFs from the R2 mapping/provenance contract.

The builder never requires a pre-existing 3D SDF.  It tries the strongest
available provenance first (an exact source SDF whose mapped coordinates agree
with the deposited instance PDB), then reconstructs an observed-only molecule
from a validated chemistry graph plus deposited PDB coordinates.  The latter
uses canonical or deposited-CIF-derived topology only; its 2D coordinates are
discarded and never exported.

The output root must be a new successor-release asset tree.  Immutable source
releases and builder inputs are read only.
"""
from __future__ import annotations

import argparse
import csv
import math
import sqlite3
from pathlib import Path

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")


def pdb_hetatm_coordinates(path: Path) -> dict[int, tuple[float, float, float, str]]:
    if not path.is_file():
        raise ValueError("MISSING_DEPOSITED_COORDINATES")
    coordinates = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("HETATM"):
                serial = int(line[6:11])
                element = (line[76:78].strip() or line[12:16].strip()[0]).capitalize()
                coordinates[serial] = (float(line[30:38]), float(line[38:46]), float(line[46:54]), element)
    if not coordinates:
        raise ValueError("MISSING_DEPOSITED_COORDINATES")
    return coordinates


def load_sdf(path: Path):
    if not path.is_file():
        raise ValueError("NO_EXACT_SOURCE_SDF")
    molecule = Chem.MolFromMolFile(str(path), sanitize=False, removeHs=False)
    if molecule is None:
        raise ValueError("TOPOLOGY_UNAVAILABLE")
    return molecule


def subset_with_source_coordinates(source: Path, deposited_pdb: Path, mappings: list[sqlite3.Row]):
    """Use a verified exact SDF only after checking it against deposited XYZ."""
    molecule = load_sdf(source)
    if not molecule.GetNumConformers() or not molecule.GetConformer().Is3D():
        raise ValueError("SOURCE_SDF_IS_2D")
    deposited = pdb_hetatm_coordinates(deposited_pdb)
    conformer = molecule.GetConformer()
    selected = []
    for row in mappings:
        source_index = row["instance_sdf_atom_index"]
        if source_index is None:
            raise ValueError("NO_ATOM_MAP")
        source_index = int(source_index)
        serial = int(row["atom_id"])
        if not 0 <= source_index < molecule.GetNumAtoms() or serial not in deposited:
            raise ValueError("ATOM_NAME_MISMATCH")
        point = conformer.GetAtomPosition(source_index)
        if math.dist((point.x, point.y, point.z), deposited[serial][:3]) > 0.001:
            raise ValueError("COORDINATE_MISMATCH")
        selected.append(source_index)
    return observed_subset(molecule, selected, {index: conformer.GetAtomPosition(index) for index in selected})


def subset_with_mapped_topology(topology: Path, deposited_pdb: Path, mappings: list[sqlite3.Row]):
    """Apply validated chemistry indices to deposited XYZ; source coordinates are ignored."""
    molecule = load_sdf(topology)
    deposited = pdb_hetatm_coordinates(deposited_pdb)
    selected, positions = [], {}
    for row in mappings:
        chemistry_index = row["chemistry_atom_index"]
        serial = int(row["atom_id"])
        if chemistry_index is None:
            raise ValueError("NO_ATOM_MAP")
        chemistry_index = int(chemistry_index)
        if not 0 <= chemistry_index < molecule.GetNumAtoms() or serial not in deposited:
            raise ValueError("ATOM_NAME_MISMATCH")
        atom = molecule.GetAtomWithIdx(chemistry_index)
        xyz = deposited[serial]
        if atom.GetSymbol() != xyz[3]:
            raise ValueError("ATOM_NAME_MISMATCH")
        selected.append(chemistry_index)
        positions[chemistry_index] = xyz[:3]
    return observed_subset(molecule, selected, positions)


def observed_subset(molecule, selected: list[int], positions):
    if len(selected) != len(set(selected)):
        raise ValueError("AMBIGUOUS_ATOM_MAP")
    selected_set = set(selected)
    editable = Chem.RWMol(molecule)
    for index in sorted(set(range(molecule.GetNumAtoms())) - selected_set, reverse=True):
        editable.RemoveAtom(index)
    result = editable.GetMol()
    if result.GetNumAtoms() != len(selected):
        raise ValueError("TOPOLOGY_UNAVAILABLE")
    old_to_new = {old: new for new, old in enumerate(sorted(selected_set))}
    conformer = Chem.Conformer(result.GetNumAtoms())
    for old_index, xyz in positions.items():
        conformer.SetAtomPosition(old_to_new[old_index], xyz)
    conformer.Set3D(True)
    result.RemoveAllConformers()
    result.AddConformer(conformer, assignId=True)
    return result, molecule.GetNumAtoms() - result.GetNumAtoms()


def write_sdf(path: Path, molecule) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing asset: {path}")
    writer = Chem.SDWriter(str(path))
    # An observed-only subset can legitimately retain an aromatic system whose
    # unobserved atoms were removed.  Preserve the validated R2 aromatic bond
    # flags instead of asking the writer to invent a kekule assignment.
    writer.SetKekulize(False)
    writer.SetProps(list(molecule.GetPropNames(includePrivate=False, includeComputed=False)))
    writer.write(molecule)
    writer.close()


def r2_topology_paths(database: Path, instance_id: str, source: str) -> list[Path]:
    paths = []
    if source:
        paths.append(Path(source))
    # This is the materialized R2 chemistry graph.  Its coordinates are not
    # consulted, but it is the correct fallback when the original source is a
    # CIF rather than an SDF.
    paths.append(database.parent / "WebAssets" / "chemistry" / instance_id / "structure_2d.sdf")
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path, help="R2 SQLite candidate/release database")
    parser.add_argument("--asset-root", required=True, type=Path, help="new successor-release asset root")
    parser.add_argument("--instance", action="append", dest="instances", help="limit to an exact instance ID (repeatable)")
    parser.add_argument("--write", action="store_true", help="write assets; default is a validation-only dry run")
    parser.add_argument("--report", required=True, type=Path, help="CSV audit report")
    args = parser.parse_args()
    if not args.database.is_file():
        raise SystemExit(f"database not found: {args.database}")

    database = sqlite3.connect(f"file:{args.database.resolve()}?mode=ro", uri=True)
    database.row_factory = sqlite3.Row
    table = database.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='R2_2D_Chemistry_Assets'").fetchone()
    if not table:
        raise SystemExit("R2_2D_Chemistry_Assets is required")
    requested = args.instances or [row[0] for row in database.execute("SELECT Recruiter_Instance_ID FROM Recruiter_Instance_Catalog WHERE Registry_Status='ACTIVE' ORDER BY Recruiter_Instance_ID")]
    rows = []
    for instance_id in requested:
        record = database.execute("""
            SELECT i.Recruiter_Instance_ID, i.pdb_id, i.Source_Entity_ID, i.Source_SDF,
                   i.Step4_PDB, a.Chemistry_Source_Class, a.chemistry_source_path,
                   a.coordinate_source_path
            FROM Recruiter_Instance_Catalog AS i
            JOIN R2_2D_Chemistry_Assets AS a USING (Recruiter_Instance_ID)
            WHERE i.Recruiter_Instance_ID = ? AND i.Registry_Status = 'ACTIVE'
        """, (instance_id,)).fetchone()
        destination = args.asset_root / "coordinates" / instance_id / "structure_observed_3d.sdf"
        status, reason, strategy, molecule, omitted = "FAILED", "OTHER", "", None, ""
        if record is None:
            reason = "UNKNOWN_INSTANCE"
        else:
            mappings = database.execute("""
                SELECT atom_id, instance_sdf_atom_index, chemistry_atom_index
                FROM Ligase_Ligands_Smiles_3DMapped
                WHERE Recruiter_Instance_ID = ?
                ORDER BY atom_id
            """, (instance_id,)).fetchall()
            if not mappings:
                reason = "NO_ATOM_MAP"
            else:
                # Tier 1: exact 3D source SDF, verified against deposited PDB.
                try:
                    molecule, omitted = subset_with_source_coordinates(
                        Path(str(record["Source_SDF"] or "")), Path(str(record["Step4_PDB"] or "")), mappings
                    )
                    strategy = "EXACT_INSTANCE_SDF_VERIFIED_AGAINST_DEPOSITED_PDB"
                except ValueError as exact_error:
                    reason = str(exact_error)
                    # Tier 2: chemistry topology + mapped deposited coordinates.
                    topology_errors = []
                    for topology in r2_topology_paths(args.database, instance_id, str(record["chemistry_source_path"] or "")):
                        try:
                            molecule, omitted = subset_with_mapped_topology(
                                topology, Path(str(record["coordinate_source_path"] or record["Step4_PDB"] or "")), mappings
                            )
                            strategy = f"R2_VALIDATED_TOPOLOGY_PLUS_DEPOSITED_PDB:{topology.name}"
                            reason = ""
                            break
                        except ValueError as topology_error:
                            topology_errors.append(str(topology_error))
                    if molecule is None:
                        reason = topology_errors[-1] if topology_errors else reason
                if molecule is not None:
                    molecule.SetProp("_Name", f"{instance_id} observed deposited structure")
                    molecule.SetProp("RECRUITER_INSTANCE_ID", instance_id)
                    molecule.SetProp("PDB_ID", record["pdb_id"])
                    molecule.SetProp("SOURCE_ENTITY_ID", record["Source_Entity_ID"])
                    molecule.SetProp("COORDINATE_PROVENANCE", "DEPOSITED_OBSERVED_COORDINATES")
                    molecule.SetProp("CHEMISTRY_SCOPE", "OBSERVED_ATOMS_ONLY")
                    molecule.SetProp("STRUCTURAL_SDF_STRATEGY", strategy)
                    molecule.SetProp("OMITTED_UNOBSERVED_CHEMISTRY_ATOMS", str(omitted))
                    status = "VALIDATED"
                    if args.write:
                        write_sdf(destination, molecule)
                        status = "WRITTEN"
        rows.append({
            "Recruiter_Instance_ID": instance_id,
            "PDB_ID": record["pdb_id"] if record else "",
            "Source_Entity_ID": record["Source_Entity_ID"] if record else "",
            "Chemistry_Source_Class": record["Chemistry_Source_Class"] if record else "",
            "Output_Path": str(destination), "Status": status, "Reason_Category": reason,
            "Strategy": strategy, "Observed_Atom_Count": molecule.GetNumAtoms() if molecule else "",
            "Bond_Count": molecule.GetNumBonds() if molecule else "", "Omitted_Chemistry_Atoms": omitted,
        })
    database.close()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    successes = sum(row["Status"] in {"VALIDATED", "WRITTEN"} for row in rows)
    print({"instances": len(rows), "successes": successes, "written": sum(row["Status"] == "WRITTEN" for row in rows), "failed": len(rows) - successes})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
