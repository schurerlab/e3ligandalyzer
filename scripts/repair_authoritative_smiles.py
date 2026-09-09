#!/usr/bin/env python3
"""Build a verified chemical graph registry from the PDB CCD SMILES export.

The PDB files in this project are coordinate files.  They are intentionally not
used as a source of bond order.  This utility joins each recruiter to the
updated ``Components-smiles-stereo-oe.smi`` file, validates its atom
correspondence to the ligand coordinates, and (only with ``--apply``) records
the result in ``Authoritative_Recruiter_SMILES`` and rewrites safe 2D↔3D atom
indices.

Default mode is read-only.  It produces a CSV audit; nothing in the database
or source tables is changed until ``--apply`` is supplied.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import rdFMCS


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "Ligases" / "Ligase_Recruiter.db"
DEFAULT_COMPONENTS = ROOT / "Components-smiles-stereo-oe.smi"
DEFAULT_REPORT = ROOT / "smiles_repair_audit.csv"

# The CCD includes valid coordination/organometallic entries that RDKit's
# organic valence model declines to sanitize. They are reported as skipped,
# without flooding the repair audit's console output.
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")


@dataclass
class RepairRecord:
    recruiter_code: str
    ligand: str
    pdb_file: str
    smiles: str
    canonical_smiles: str
    inchikey: str
    component_status: str
    mapping_status: str
    component_heavy_atoms: int
    pdb_heavy_atoms: int | None
    mcs_atoms: int | None
    mapping: dict[int, int]
    notes: str


def load_components(path: Path) -> dict[str, str]:
    """Read component ID → canonical isomeric SMILES from the CCD export."""
    components: dict[str, str] = {}
    bad_rows = 0
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 2:
                continue
            raw_smiles, component_id = fields[0].strip(), fields[1].strip().upper()
            if not raw_smiles or not component_id:
                continue
            mol = Chem.MolFromSmiles(raw_smiles)
            if mol is None:
                bad_rows += 1
                continue
            components[component_id] = Chem.MolToSmiles(
                mol, canonical=True, isomericSmiles=True
            )
    print(f"Loaded {len(components):,} valid CCD components ({bad_rows} invalid rows skipped).")
    return components


def ligand_pdb_mol(pdb_file: str, ligand: str) -> Chem.Mol | None:
    """Read exactly one ligand's HETATM block; never infer from the full protein."""
    path = ROOT / pdb_file
    if not path.is_file():
        return None
    lines = [
        line
        for line in path.read_text().splitlines(keepends=True)
        if line.startswith("HETATM") and line[17:20].strip().upper() == ligand
    ]
    if not lines:
        return None
    return Chem.MolFromPDBBlock("".join(lines), sanitize=False, removeHs=False)


def validate_record(recruiter_code: str, ligand: str, pdb_file: str, smiles: str) -> RepairRecord:
    component = Chem.MolFromSmiles(smiles)
    assert component is not None  # guaranteed while loading the CCD export
    heavy_atoms = component.GetNumHeavyAtoms()
    pdb_mol = ligand_pdb_mol(pdb_file, ligand)

    base = RepairRecord(
        recruiter_code=recruiter_code,
        ligand=ligand,
        pdb_file=pdb_file,
        smiles=smiles,
        canonical_smiles=Chem.MolToSmiles(component, canonical=True, isomericSmiles=True),
        inchikey=Chem.MolToInchiKey(component),
        component_status="valid_ccd",
        mapping_status="not_checked",
        component_heavy_atoms=heavy_atoms,
        pdb_heavy_atoms=None,
        mcs_atoms=None,
        mapping={},
        notes="",
    )
    if pdb_mol is None:
        base.mapping_status = "missing_or_unreadable_pdb_ligand"
        base.notes = "Could not isolate ligand HETATM records from PDB_File"
        return base

    pdb_atoms = [atom for atom in pdb_mol.GetAtoms() if atom.GetAtomicNum() > 1]
    base.pdb_heavy_atoms = len(pdb_atoms)
    if len(pdb_atoms) != heavy_atoms:
        base.mapping_status = "heavy_atom_count_mismatch"
        base.notes = "CCD and coordinate ligand have different heavy-atom counts; review manually"
        return base

    mcs = rdFMCS.FindMCS(
        [component, pdb_mol],
        atomCompare=rdFMCS.AtomCompare.CompareElements,
        bondCompare=rdFMCS.BondCompare.CompareAny,
        timeout=20,
    )
    pattern = Chem.MolFromSmarts(mcs.smartsString) if mcs and mcs.smartsString else None
    if pattern is None:
        base.mapping_status = "mcs_failed"
        base.notes = "No element-aware MCS could be constructed"
        return base

    component_match = component.GetSubstructMatch(pattern)
    pdb_match = pdb_mol.GetSubstructMatch(pattern)
    base.mcs_atoms = len(component_match)
    if len(component_match) != heavy_atoms or len(pdb_match) != heavy_atoms:
        base.mapping_status = "incomplete_mcs"
        base.notes = "MCS does not cover every heavy atom"
        return base

    serial_to_smiles_index: dict[int, int] = {}
    for smiles_idx, pdb_idx in zip(component_match, pdb_match):
        pdb_atom = pdb_mol.GetAtomWithIdx(pdb_idx)
        info = pdb_atom.GetPDBResidueInfo()
        if info is None or pdb_atom.GetSymbol() != component.GetAtomWithIdx(smiles_idx).GetSymbol():
            base.mapping_status = "invalid_mcs_atom_assignment"
            base.notes = "MCS returned an invalid atom assignment"
            return base
        serial_to_smiles_index[info.GetSerialNumber()] = smiles_idx

    if len(serial_to_smiles_index) != heavy_atoms:
        base.mapping_status = "ambiguous_pdb_atom_serials"
        base.notes = "PDB serial numbers are not unique for the ligand"
        return base

    base.mapping = serial_to_smiles_index
    base.mapping_status = "full_heavy_atom_mcs"
    base.notes = "CCD graph and coordinate ligand fully mapped; safe for 2D SASA atom indices"
    return base


def load_recruiter_instances(conn: sqlite3.Connection):
    return conn.execute(
        """
        SELECT RECRUITER_CODE, Ligand, PDB_File
        FROM Ligand_Instance_Recruiter_Codes
        WHERE RECRUITER_CODE IS NOT NULL
          AND Ligand IS NOT NULL
          AND PDB_File IS NOT NULL
        ORDER BY RECRUITER_CODE
        """
    ).fetchall()


def write_report(records: list[RepairRecord], path: Path) -> None:
    fields = [
        "RECRUITER_CODE", "Ligand", "PDB_File", "SMILES", "Canonical_SMILES", "InChIKey",
        "Component_Status", "Mapping_Status", "Component_Heavy_Atoms", "PDB_Heavy_Atoms",
        "MCS_Atoms", "Notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow({
                "RECRUITER_CODE": r.recruiter_code,
                "Ligand": r.ligand,
                "PDB_File": r.pdb_file,
                "SMILES": r.smiles,
                "Canonical_SMILES": r.canonical_smiles,
                "InChIKey": r.inchikey,
                "Component_Status": r.component_status,
                "Mapping_Status": r.mapping_status,
                "Component_Heavy_Atoms": r.component_heavy_atoms,
                "PDB_Heavy_Atoms": r.pdb_heavy_atoms or "",
                "MCS_Atoms": r.mcs_atoms or "",
                "Notes": r.notes,
            })
    print(f"Wrote audit report: {path}")


def apply_verified_repairs(conn: sqlite3.Connection, records: list[RepairRecord]) -> None:
    """Persist authoritative graphs and update only fully verified atom indices."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Authoritative_Recruiter_SMILES (
            RECRUITER_CODE TEXT PRIMARY KEY,
            Ligand TEXT NOT NULL,
            SMILES TEXT NOT NULL,
            Canonical_SMILES TEXT NOT NULL,
            InChIKey TEXT NOT NULL,
            Source TEXT NOT NULL,
            Source_File TEXT NOT NULL,
            Mapping_Status TEXT NOT NULL,
            Updated_At TEXT NOT NULL
        )
        """
    )
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    upserted = mapped_rows = 0
    for record in records:
        if record.component_status != "valid_ccd":
            continue
        conn.execute(
            """
            INSERT INTO Authoritative_Recruiter_SMILES
                (RECRUITER_CODE, Ligand, SMILES, Canonical_SMILES, InChIKey,
                 Source, Source_File, Mapping_Status, Updated_At)
            VALUES (?, ?, ?, ?, ?, 'PDB_CCD', ?, ?, ?)
            ON CONFLICT(RECRUITER_CODE) DO UPDATE SET
                Ligand=excluded.Ligand,
                SMILES=excluded.SMILES,
                Canonical_SMILES=excluded.Canonical_SMILES,
                InChIKey=excluded.InChIKey,
                Source=excluded.Source,
                Source_File=excluded.Source_File,
                Mapping_Status=excluded.Mapping_Status,
                Updated_At=excluded.Updated_At
            """,
            (
                record.recruiter_code, record.ligand, record.smiles,
                record.canonical_smiles, record.inchikey,
                str(DEFAULT_COMPONENTS.name), record.mapping_status, timestamp,
            ),
        )
        upserted += 1
        if record.mapping_status != "full_heavy_atom_mcs":
            continue
        for atom_id, smiles_index in record.mapping.items():
            result = conn.execute(
                """
                UPDATE Ligase_Ligands_Smiles_3DMapped
                SET smiles_atom_index = ?,
                    smile_atom = ?
                WHERE RECRUITER_CODE = ?
                  AND atom_id = ?
                """,
                (
                    smiles_index,
                    Chem.MolFromSmiles(record.smiles).GetAtomWithIdx(smiles_index).GetSymbol(),
                    record.recruiter_code,
                    atom_id,
                ),
            )
            mapped_rows += result.rowcount
    conn.commit()
    print(f"Applied {upserted} authoritative graphs and updated {mapped_rows} verified atom-map rows.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--components", type=Path, default=DEFAULT_COMPONENTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--apply", action="store_true", help="Write the verified registry and atom-map repairs to SQLite")
    args = parser.parse_args()

    if not args.db.is_file():
        parser.error(f"Database not found: {args.db}")
    if not args.components.is_file():
        parser.error(f"CCD SMILES file not found: {args.components}")

    components = load_components(args.components)
    conn = sqlite3.connect(args.db)
    rows = load_recruiter_instances(conn)
    records: list[RepairRecord] = []
    missing_component = 0
    for code, ligand, pdb_file in rows:
        ligand = str(ligand).strip().upper()
        smiles = components.get(ligand)
        if not smiles:
            missing_component += 1
            records.append(RepairRecord(
                recruiter_code=str(code).strip().upper(),
                ligand=ligand,
                pdb_file=str(pdb_file),
                smiles="",
                canonical_smiles="",
                inchikey="",
                component_status="missing_ccd_component",
                mapping_status="not_repaired",
                component_heavy_atoms=0,
                pdb_heavy_atoms=None,
                mcs_atoms=None,
                mapping={},
                notes="No matching component ID was found in the CCD SMILES export",
            ))
            continue
        records.append(validate_record(str(code).strip().upper(), ligand, str(pdb_file), smiles))

    write_report(records, args.report)
    counts: dict[str, int] = {}
    for record in records:
        counts[record.mapping_status] = counts.get(record.mapping_status, 0) + 1
    print(f"Instances inspected: {len(rows)}; missing CCD component: {missing_component}")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")

    if args.apply:
        apply_verified_repairs(conn, records)
    else:
        print("Dry run complete: no database changes made. Re-run with --apply after reviewing the audit.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
