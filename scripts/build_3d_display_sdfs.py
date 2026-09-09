#!/usr/bin/env python3
"""Create bond-order-correct ligand SDFs without moving their PDB coordinates.

Each output is a separate, display-only ligand component:

* bond graph: authoritative PDB Chemical Component Dictionary SMILES;
* coordinates: corresponding HETATM records from the deposited PDB;
* eligibility: only ``full_heavy_atom_mcs`` mappings produced by
  ``repair_authoritative_smiles.py``.

The source PDB is never modified.  NGL can load the generated SDF beside the
PDB protein component, showing correct multiple bonds while existing SASA
spheres continue to use their original PDB XYZ coordinates.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from rdkit import Chem, RDLogger


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "Ligases" / "Ligase_Recruiter.db"
DEFAULT_MANIFEST = ROOT / "corrected_3d_sdf_manifest.csv"

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")


@dataclass(frozen=True)
class DisplayLigand:
    recruiter_code: str
    ligase: str
    pdb_id: str
    ligand: str
    variant: int
    pdb_file: Path
    smiles: str


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true", help="Process every fully validated recruiter")
    selection.add_argument("--codes", help="Comma-separated recruiter codes, e.g. LR00023,LR00122")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--write", action="store_true", help="Write SDF files; default is a dry run")
    return parser.parse_args()


def selected_ligands(conn: sqlite3.Connection, codes: set[str] | None) -> list[DisplayLigand]:
    rows = conn.execute(
        """
        SELECT a.RECRUITER_CODE, i.Ligase, i.pdb_id, i.Ligand, i.Variant,
               i.PDB_File, a.SMILES
        FROM Authoritative_Recruiter_SMILES AS a
        JOIN Ligand_Instance_Recruiter_Codes AS i
          ON i.RECRUITER_CODE = a.RECRUITER_CODE
        WHERE a.Mapping_Status = 'full_heavy_atom_mcs'
        ORDER BY a.RECRUITER_CODE
        """
    ).fetchall()
    records = []
    for code, ligase, pdb_id, ligand, variant, pdb_file, smiles in rows:
        code = str(code).strip().upper()
        if codes is not None and code not in codes:
            continue
        records.append(DisplayLigand(
            recruiter_code=code,
            ligase=str(ligase).strip(),
            pdb_id=str(pdb_id).strip().upper(),
            ligand=str(ligand).strip().upper(),
            variant=int(variant or 1),
            pdb_file=ROOT / str(pdb_file),
            smiles=str(smiles).strip(),
        ))
    return records


def pdb_ligand_coordinates(pdb_file: Path, ligand: str) -> dict[int, tuple[str, tuple[float, float, float]]]:
    """Return PDB serial → (element, XYZ) for the requested ligand only."""
    coordinates = {}
    with pdb_file.open() as handle:
        for line in handle:
            if not line.startswith("HETATM") or line[17:20].strip().upper() != ligand:
                continue
            serial = int(line[6:11])
            element = line[76:78].strip() or line[12:16].strip()[0]
            xyz = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
            coordinates[serial] = (element.capitalize(), xyz)
    return coordinates


def atom_mapping(conn: sqlite3.Connection, recruiter_code: str) -> dict[int, int]:
    rows = conn.execute(
        """
        SELECT atom_id, smiles_atom_index
        FROM Ligase_Ligands_Smiles_3DMapped
        WHERE RECRUITER_CODE = ?
          AND atom_id IS NOT NULL
          AND smiles_atom_index IS NOT NULL
        """,
        [recruiter_code],
    ).fetchall()
    return {int(atom_id): int(smiles_index) for atom_id, smiles_index in rows}


def make_coordinate_sdf(record: DisplayLigand, serial_to_smiles: dict[int, int]):
    """Return a conformer-bearing CCD molecule, or an explicit validation error."""
    if not record.pdb_file.is_file():
        return None, "missing_pdb"

    source_mol = Chem.MolFromSmiles(record.smiles)
    if source_mol is None:
        return None, "invalid_authoritative_smiles"

    # The PDB has no hydrogen coordinates. Remove explicit hydrogen atoms while
    # retaining its correct heavy-atom bond graph and translate stored indices.
    original_to_display = {}
    display_index = 0
    for atom in source_mol.GetAtoms():
        if atom.GetAtomicNum() > 1:
            original_to_display[atom.GetIdx()] = display_index
            display_index += 1
    mol = Chem.RemoveHs(source_mol)

    coordinates = pdb_ligand_coordinates(record.pdb_file, record.ligand)
    if len(serial_to_smiles) != mol.GetNumAtoms():
        return None, "mapping_atom_count_mismatch"
    if len(coordinates) != mol.GetNumAtoms():
        return None, "pdb_coordinate_atom_count_mismatch"

    conformer = Chem.Conformer(mol.GetNumAtoms())
    assigned = set()
    for serial, original_smiles_index in serial_to_smiles.items():
        display_smiles_index = original_to_display.get(original_smiles_index)
        coordinate = coordinates.get(serial)
        if display_smiles_index is None or coordinate is None:
            return None, "missing_atom_coordinate_or_index"
        pdb_element, xyz = coordinate
        molecule_element = mol.GetAtomWithIdx(display_smiles_index).GetSymbol()
        if pdb_element != molecule_element:
            return None, "element_mismatch"
        conformer.SetAtomPosition(display_smiles_index, xyz)
        assigned.add(display_smiles_index)

    if len(assigned) != mol.GetNumAtoms():
        return None, "incomplete_coordinate_assignment"

    conformer.Set3D(True)
    mol.AddConformer(conformer, assignId=True)
    mol.SetProp("_Name", f"{record.pdb_id}_{record.ligand}_{record.variant} | {record.recruiter_code} | PDB_CCD")
    mol.SetProp("RECRUITER_CODE", record.recruiter_code)
    mol.SetProp("LIGAND_COMPONENT_ID", record.ligand)
    mol.SetProp("PDB_SOURCE", record.pdb_file.relative_to(ROOT).as_posix())
    mol.SetProp("SMILES_SOURCE", "PDB_CCD")
    return mol, "ready"


def output_path(record: DisplayLigand) -> Path:
    return ROOT / "Ligases" / record.ligase / "SDF_3DDisplay" / f"{record.pdb_file.stem}.sdf"


def write_manifest(rows: list[dict[str, str]], path: Path) -> None:
    fields = [
        "RECRUITER_CODE", "Ligase", "PDB_ID", "Ligand", "Variant", "PDB_File",
        "Output_SDF", "Status", "Atom_Count", "Bond_Count",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote manifest: {path}")


def main() -> int:
    args = parse_args()
    if not args.db.is_file():
        raise SystemExit(f"Database not found: {args.db}")
    requested_codes = None
    if args.codes:
        requested_codes = {code.strip().upper() for code in args.codes.split(",") if code.strip()}

    conn = sqlite3.connect(args.db)
    records = selected_ligands(conn, requested_codes)
    if not records:
        raise SystemExit("No fully validated recruiter records matched the requested selection.")

    manifest_rows = []
    created = failed = 0
    for record in records:
        molecule, status = make_coordinate_sdf(record, atom_mapping(conn, record.recruiter_code))
        destination = output_path(record)
        row = {
            "RECRUITER_CODE": record.recruiter_code,
            "Ligase": record.ligase,
            "PDB_ID": record.pdb_id,
            "Ligand": record.ligand,
            "Variant": str(record.variant),
            "PDB_File": record.pdb_file.relative_to(ROOT).as_posix(),
            "Output_SDF": destination.relative_to(ROOT).as_posix(),
            "Status": status,
            "Atom_Count": str(molecule.GetNumAtoms()) if molecule else "",
            "Bond_Count": str(molecule.GetNumBonds()) if molecule else "",
        }
        if molecule is None:
            failed += 1
        else:
            created += 1
            if args.write:
                destination.parent.mkdir(parents=True, exist_ok=True)
                writer = Chem.SDWriter(str(destination))
                writer.write(molecule)
                writer.close()
        manifest_rows.append(row)

    write_manifest(manifest_rows, args.manifest)
    mode = "wrote" if args.write else "validated (dry run)"
    print(f"{mode.capitalize()} {created} display SDFs; {failed} records were skipped.")
    conn.close()
    # Some records are intentionally withheld when their atoms cannot be mapped
    # unambiguously.  They retain the existing PDB-renderer fallback; a partial
    # safe build should not make the batch command fail.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
