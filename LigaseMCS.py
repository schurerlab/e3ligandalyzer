#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ligase_MCS_Rebuild_Missing.py

Rebuilds 2D–3D MCS mappings ONLY for a subset of recruiter codes
given in an input CSV (e.g., Ligase_MISSING_MCS.csv).

- Uses true rdFMCS between:
    SMILES (from Recruiter_SMILES_Map)
    vs
    PDB ligand (from Ligases/<Ligase>/PDB/<pdbid>_<Ligand>[_Variant].pdb)

- Reads existing metadata from:
    Table: Ligase_Ligands_Smiles_3DMapped
        (for Ligase, pdb_id, Ligand, Variant, Chain)
    Table: Recruiter_SMILES_Map
        (for SMILES)

- Outputs:
    rebuilt_MCS_missing.csv
      Columns:
        Ligase, pdb_id, Ligand, Variant, RECRUITER_CODE, Chain,
        atom_id, exact_atom, atom_type, x, y, z,
        smiles_atom_index, smile_atom

No database writes are performed.
"""

import os
import csv
import sqlite3
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import rdFMCS

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------
DB_PATH = "Ligases/Ligase_Recruiter.db"
PDB_BASE = Path("Ligases")  # Ligases/<Ligase>/PDB/*.pdb
DEFAULT_MISSING_CSV = "Ligase_MISSING_MCS.csv"
OUTPUT_CSV = "rebuilt_MCS_missing.csv"


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def load_missing_codes(csv_path: str):
    """Load RECRUITER_CODE values from a CSV with a 'RECRUITER_CODE' column."""
    codes = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        if "RECRUITER_CODE" not in reader.fieldnames:
            raise ValueError(f"'RECRUITER_CODE' column not found in {csv_path}")
        for row in reader:
            code = row["RECRUITER_CODE"].strip()
            if code:
                codes.append(code)
    return codes


def get_metadata_for_code(cur, recruiter_code: str):
    """
    Pull Ligase, pdb_id, Ligand, Variant, Chain
    from Ligase_Ligands_Smiles_3DMapped for this recruiter.
    """
    row = cur.execute(
        """
        SELECT Ligase, pdb_id, Ligand, Variant, Chain
        FROM Ligase_Ligands_Smiles_3DMapped
        WHERE RECRUITER_CODE = ?
        LIMIT 1
        """,
        (recruiter_code,),
    ).fetchone()

    if not row:
        return None

    ligase, pdb_id, ligand, variant, chain = row
    return {
        "Ligase": ligase,
        "pdb_id": pdb_id,
        "Ligand": ligand,
        "Variant": int(variant) if variant is not None else 1,
        "Chain": chain if chain else "",
    }


def get_smiles_for_code(cur, recruiter_code: str):
    """Get SMILES from Recruiter_SMILES_Map for this recruiter code."""
    row = cur.execute(
        """
        SELECT SMILES
        FROM Recruiter_SMILES_Map
        WHERE RECRUITER_CODE = ?
        """,
        (recruiter_code,),
    ).fetchone()
    return row[0] if row else None


def find_pdb_file(meta: dict) -> Path | None:
    """
    Find the corresponding PDB file, handling variants:
      <pdb_id>_<Ligand>.pdb  OR  <pdb_id>_<Ligand>_<Variant>.pdb
    """
    ligase = meta["Ligase"]
    pdb_id = meta["pdb_id"]
    ligand = meta["Ligand"]
    variant = meta["Variant"]

    pdb_dir = PDB_BASE / ligase / "PDB"
    path1 = pdb_dir / f"{pdb_id}_{ligand}.pdb"
    path2 = pdb_dir / f"{pdb_id}_{ligand}_{variant}.pdb"

    if path1.exists():
        return path1
    if path2.exists():
        return path2
    return None


def get_ligand_residue_id_from_pdb(pdb_path: Path, ligand: str, chain: str | None = None):
    """
    Scan PDB text to find the residue ID for the given ligand.
    Assumes only one ligand of that resname per structure (your case).
    """
    ligand = ligand.strip()
    chain = (chain or "").strip()
    residue_ids = set()

    with open(pdb_path) as f:
        for line in f:
            if not line.startswith(("ATOM", "HETATM")):
                continue
            resname = line[17:20].strip()
            chain_id = line[21].strip()
            resid = int(line[22:26])

            if resname == ligand and (not chain or chain_id == chain):
                residue_ids.add(resid)

    if not residue_ids:
        return None

    if len(residue_ids) > 1:
        # Still pick one, but flagging this could be useful for debugging.
        # You can print or log if needed.
        pass

    return sorted(residue_ids)[0]


def rdkit_mol_from_pdb(pdb_path: Path):
    """Load a PDB as RDKit Mol (no sanitization to tolerate weird chemistry)."""
    try:
        mol = Chem.MolFromPDBFile(str(pdb_path), sanitize=False, removeHs=False)
        return mol
    except Exception:
        return None


def rdkit_mol_from_smiles(smiles: str):
    """Safely construct RDKit Mol from SMILES."""
    try:
        mol = Chem.MolFromSmiles(smiles)
        return mol
    except Exception:
        return None


def run_mcs(smiles_mol, pdb_mol, timeout: int = 20):
    """
    Run rdFMCS between SMILES mol and PDB ligand mol.
    Returns (match_2d_indices, match_3d_indices) or (None, None) on failure.
    """
    mcs = rdFMCS.FindMCS(
        [smiles_mol, pdb_mol],
        completeRingsOnly=False,
        ringMatchesRingOnly=False,
        timeout=timeout,
    )
    if not mcs or not mcs.smartsString:
        return None, None

    patt = Chem.MolFromSmarts(mcs.smartsString)
    if patt is None:
        return None, None

    match_2d = smiles_mol.GetSubstructMatch(patt)
    match_3d = pdb_mol.GetSubstructMatch(patt)

    if not match_2d or not match_3d:
        return None, None

    return match_2d, match_3d


# -------------------------------------------------------------------
# Main driver
# -------------------------------------------------------------------

def rebuild_missing_mcs(missing_csv: str = DEFAULT_MISSING_CSV,
                        out_csv: str = OUTPUT_CSV):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    codes = load_missing_codes(missing_csv)
    print(f"\n🔧 Rebuilding MCS for {len(codes)} recruiter codes from {missing_csv}\n")

    out_rows = []
    skipped = []

    for code in codes:
        print("=" * 80)
        print(f"🔎 Processing recruiter: {code}")

        meta = get_metadata_for_code(cur, code)
        if not meta:
            print("   ❌ No metadata row found in Ligase_Ligands_Smiles_3DMapped — skipping.")
            skipped.append((code, "no_metadata"))
            continue

        ligase = meta["Ligase"]
        pdb_id = meta["pdb_id"]
        ligand = meta["Ligand"]
        variant = meta["Variant"]
        chain_hint = meta["Chain"]

        print(f"   Ligase: {ligase}")
        print(f"   PDB:    {pdb_id}")
        print(f"   Ligand: {ligand}")
        print(f"   Variant:{variant}")
        print(f"   Chain:  {chain_hint or '(none)'}")

        pdb_path = find_pdb_file(meta)
        if not pdb_path:
            print("   ❌ No matching PDB file found — skipping.")
            skipped.append((code, "no_pdb"))
            continue

        print(f"   📁 PDB file: {pdb_path}")

        # Get SMILES
        smiles = get_smiles_for_code(cur, code)
        if not smiles:
            print("   ❌ No SMILES found in Recruiter_SMILES_Map — skipping.")
            skipped.append((code, "no_smiles"))
            continue

        print(f"   🧪 SMILES: {smiles}")

        # Load RDKit molecules
        smiles_mol = rdkit_mol_from_smiles(smiles)
        pdb_mol = rdkit_mol_from_pdb(pdb_path)

        if smiles_mol is None:
            print("   ❌ RDKit failed to parse SMILES — skipping.")
            skipped.append((code, "smiles_parse_fail"))
            continue
        if pdb_mol is None:
            print("   ❌ RDKit failed to load PDB — skipping.")
            skipped.append((code, "pdb_parse_fail"))
            continue

        # OPTIONAL: residue ID from PDB for debug / consistency
        resid = get_ligand_residue_id_from_pdb(pdb_path, ligand, chain_hint)
        if resid is not None:
            print(f"   📍 Ligand residue ID in PDB: {resid}")
        else:
            print("   ⚠️ Could not determine unique ligand residue ID (continuing anyway).")

        # Run MCS
        match_2d, match_3d = run_mcs(smiles_mol, pdb_mol, timeout=20)
        if match_2d is None or match_3d is None:
            print("   ❌ MCS failed or no substructure match — skipping.")
            skipped.append((code, "mcs_fail"))
            continue

        print(f"   ✅ MCS match size: {len(match_2d)} atoms")

        conf = pdb_mol.GetConformer()
        for idx2d, idx3d in zip(match_2d, match_3d):
            atom3d = pdb_mol.GetAtomWithIdx(idx3d)
            pos = conf.GetAtomPosition(idx3d)
            ri = atom3d.GetPDBResidueInfo()

            atom_serial = ri.GetSerialNumber() if ri is not None else atom3d.GetIdx()
            atom_name = ri.GetName().strip() if ri is not None else atom3d.GetSymbol()
            chain_id = ri.GetChainId().strip() if ri is not None else (chain_hint or "")

            out_rows.append({
                "Ligase": ligase,
                "pdb_id": pdb_id,
                "Ligand": ligand,
                "Variant": variant,
                "RECRUITER_CODE": code,
                "Chain": chain_id,
                "atom_id": atom_serial,
                "exact_atom": atom_name,
                "atom_type": atom3d.GetSymbol(),
                "x": pos.x,
                "y": pos.y,
                "z": pos.z,
                "smiles_atom_index": idx2d,
                "smile_atom": smiles_mol.GetAtomWithIdx(idx2d).GetSymbol(),
            })

        print(f"   ✅ Added {len(match_2d)} mapping rows for {code}")

    conn.close()

    # Write output CSV
    if out_rows:
        fieldnames = [
            "Ligase", "pdb_id", "Ligand", "Variant", "RECRUITER_CODE", "Chain",
            "atom_id", "exact_atom", "atom_type", "x", "y", "z",
            "smiles_atom_index", "smile_atom"
        ]
        with open(out_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(out_rows)
        print(f"\n🎉 COMPLETE — wrote {len(out_rows)} rows to {out_csv}\n")
    else:
        print("\n⚠️ No rows were generated — nothing written.\n")

    if skipped:
        print("⚠️ Skipped recruiters:")
        for code, reason in skipped:
            print(f"   - {code}: {reason}")


if __name__ == "__main__":
    # If you want to hard-code the CSV, leave as is.
    # If later you want argparse, easy to swap in.
    rebuild_missing_mcs()
