#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FixRecruiterCodes.py
Ensures one recruiter code per unique (Ligase, pdb_id, Ligand, Variant).
If a recruiter code is shared across multiple distinct combos, the first combo
keeps the original code and each additional combo gets a NEW sequential recruiter
code (e.g., L00501, L00502, ...).

Cascades updates to related tables to keep the relational DB consistent:
- UPDATE Ligase_Ligands_Smiles_3DMapped
- INSERT copies into Ligase_SMILE_Codes
- INSERT copies into Recruiter_SMILES_Map
- INSERT copies into Ligase_SMILE_Codes_Atoms
- INSERT copies into Ligase_Chemical_Descriptors
- INSERT copies into Ligase_Recruiters_Scaffold (if table/rows exist)

Also records ligand → matched recruiters in Ligase_Duplicate_Ligands.

Usage:
    python FixRecruiterCodes.py

Set DRY_RUN = False to apply changes.
"""

import re
import sqlite3
from collections import defaultdict

DB_PATH = "Ligases/Ligase_Recruiter.db"
DRY_RUN = False  # <<< set to False to commit changes

RECRUITER_RE = re.compile(r"^L(\d{5})$")

def get_max_recruiter_number(cur):
    """Scan all recruiter-code-bearing tables for the max Lxxxxx number."""
    tables_cols = [
        ("Ligase_Ligands_Smiles_3DMapped", "RECRUITER_CODE"),
        ("Ligase_SMILE_Codes", "RECRUITER_CODE"),
        ("Recruiter_SMILES_Map", "RECRUITER_CODE"),
        ("Ligase_SMILE_Codes_Atoms", "RECRUITER_CODE"),
        ("Ligase_Chemical_Descriptors", "RECRUITER_CODE"),
        ("Ligase_Recruiters_Scaffold", "RECRUITER_CODE"),
    ]
    max_num = -1
    for tbl, col in tables_cols:
        try:
            cur.execute(f"SELECT {col} FROM {tbl}")
            for (code,) in cur.fetchall():
                if not code:
                    continue
                m = RECRUITER_RE.match(code)
                if m:
                    n = int(m.group(1))
                    if n > max_num:
                        max_num = n
        except sqlite3.OperationalError:
            # Table might not exist; skip
            pass
    return max_num if max_num >= 0 else 0

def next_recruiter_code(n):
    return f"L{n:05d}"

def table_exists(cur, name):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def fetch_smiles_for_recruiter(cur, recruiter):
    """Try to resolve SMILES for a recruiter from descriptors, then SMILE_Codes, then map."""
    # 1) Ligase_Chemical_Descriptors
    try:
        cur.execute("SELECT SMILES FROM Ligase_Chemical_Descriptors WHERE RECRUITER_CODE=?", (recruiter,))
        row = cur.fetchone()
        if row and row[0]:
            return row[0]
    except sqlite3.OperationalError:
        pass
    # 2) Ligase_SMILE_Codes
    try:
        cur.execute("SELECT SMILES FROM Ligase_SMILE_Codes WHERE RECRUITER_CODE=?", (recruiter,))
        row = cur.fetchone()
        if row and row[0]:
            return row[0]
    except sqlite3.OperationalError:
        pass
    # 3) Recruiter_SMILES_Map
    try:
        cur.execute("SELECT SMILES FROM Recruiter_SMILES_Map WHERE RECRUITER_CODE=?", (recruiter,))
        row = cur.fetchone()
        if row and row[0]:
            return row[0]
    except sqlite3.OperationalError:
        pass
    return None

def copy_atoms_map(cur, old_rc, new_rc):
    """Duplicate atom map rows from old recruiter to new recruiter in Ligase_SMILE_Codes_Atoms."""
    if not table_exists(cur, "Ligase_SMILE_Codes_Atoms"):
        return
    cur.execute("""
        SELECT smiles_atom_index, smile_atom
        FROM Ligase_SMILE_Codes_Atoms
        WHERE RECRUITER_CODE=?
    """, (old_rc,))
    rows = cur.fetchall()
    for idx, atom in rows:
        cur.execute("""
            INSERT OR IGNORE INTO Ligase_SMILE_Codes_Atoms
            (RECRUITER_CODE, smiles_atom_index, smile_atom)
            VALUES (?, ?, ?)
        """, (new_rc, idx, atom))

def copy_descriptors(cur, old_rc, new_rc):
    """Duplicate descriptors to the new recruiter code (if table exists)."""
    if not table_exists(cur, "Ligase_Chemical_Descriptors"):
        return
    cur.execute("""
        SELECT MW, LogP, TPSA, HBA, HBD, Rotatable_Bonds, Ring_Count, Aromatic_Rings,
               Fraction_CSP3, Heavy_Atom_Count, Chiral_Atoms, Formal_Charge, QED, BertzCT,
               HallKierAlpha, Kappa1, Kappa2, Kappa3, NumSpiroAtoms, NumBridgeheadAtoms,
               NumAliphaticRings, NumAromaticRings, NumSaturatedRings, NumHeteroAtoms,
               MolMR, SA_Score, Lipinski_Pass, Veber_Pass, Egan_Pass, Ghose_Pass,
               Muegge_Pass, SMILES, PAINS_Hits, Brenk_Hits
        FROM Ligase_Chemical_Descriptors
        WHERE RECRUITER_CODE=?
    """, (old_rc,))
    row = cur.fetchone()
    if row:
        cur.execute("""
            INSERT OR IGNORE INTO Ligase_Chemical_Descriptors
            (MW, LogP, TPSA, HBA, HBD, Rotatable_Bonds, Ring_Count, Aromatic_Rings,
             Fraction_CSP3, Heavy_Atom_Count, Chiral_Atoms, Formal_Charge, QED, BertzCT,
             HallKierAlpha, Kappa1, Kappa2, Kappa3, NumSpiroAtoms, NumBridgeheadAtoms,
             NumAliphaticRings, NumAromaticRings, NumSaturatedRings, NumHeteroAtoms,
             MolMR, SA_Score, Lipinski_Pass, Veber_Pass, Egan_Pass, Ghose_Pass,
             Muegge_Pass, RECRUITER_CODE, SMILES, PAINS_Hits, Brenk_Hits)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (*row[:31], new_rc, row[31], row[32], row[33]))

def copy_scaffold_rows(cur, old_rc, new_rc):
    """Duplicate any scaffold rows for old recruiter to new recruiter (if table exists)."""
    if not table_exists(cur, "Ligase_Recruiters_Scaffold"):
        return
    cur.execute("""
        SELECT Ligase, Scaffold_ID, Scaffold_SMILES, Scaffold_Hash
        FROM Ligase_Recruiters_Scaffold
        WHERE RECRUITER_CODE=?
    """, (old_rc,))
    for ligase, scaffold_id, smi, hsh in cur.fetchall():
        cur.execute("""
            INSERT OR IGNORE INTO Ligase_Recruiters_Scaffold
            (Ligase, Scaffold_ID, RECRUITER_CODE, Scaffold_SMILES, Scaffold_Hash)
            VALUES (?, ?, ?, ?, ?)
        """, (ligase, scaffold_id, new_rc, smi, hsh))

def ensure_duplicate_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Ligase_Duplicate_Ligands (
            Ligand TEXT,
            MATCHED_RECRUITERS TEXT
        )
    """)

def upsert_duplicate_ligand(cur, ligand, recruiters):
    """Record ligand → matched recruiters (comma-joined)."""
    ensure_duplicate_table(cur)
    cur.execute("""
        INSERT INTO Ligase_Duplicate_Ligands (Ligand, MATCHED_RECRUITERS)
        VALUES (?, ?)
    """, (ligand, ",".join(sorted(set(recruiters)))))

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print(f"Database: {DB_PATH}")
    print("Scanning for recruiter codes reused across different (Ligase,pdb_id,Ligand,Variant) combos...")

    # Build mapping: recruiter -> list of unique combos
    cur.execute("""
        SELECT DISTINCT RECRUITER_CODE, Ligase, pdb_id, Ligand, Variant
        FROM Ligase_Ligands_Smiles_3DMapped
        ORDER BY RECRUITER_CODE, Ligase, pdb_id, Ligand, Variant
    """)
    rows = cur.fetchall()

    by_recruiter = defaultdict(list)
    for r in rows:
        rc = r["RECRUITER_CODE"]
        by_recruiter[rc].append( (r["Ligase"], r["pdb_id"], r["Ligand"], r["Variant"]) )

    max_num = get_max_recruiter_number(cur)
    print(f"Current max recruiter number: {max_num:05d}")

    # For reporting: ligand -> all recruiters it ends up with
    ligand_to_recruiters = defaultdict(set)

    # Process each recruiter that maps to multiple combos
    for rc, combos in by_recruiter.items():
        unique_combos = list(dict.fromkeys(combos))  # preserve order, deduplicate exactly
        if len(unique_combos) <= 1:
            continue  # this recruiter is fine; only used by one combo

        print(f"⚠️  Recruiter {rc} is used by {len(unique_combos)} distinct combos → will split others")

        # First combo keeps original recruiter code
        keep_combo = unique_combos[0]
        keep_ligand = keep_combo[2]
        ligand_to_recruiters[keep_ligand].add(rc)

        # For each *other* combo, mint a single new recruiter code and update every table once
        for combo in unique_combos[1:]:
            ligase, pdb_id, ligand, variant = combo
            max_num += 1
            new_rc = next_recruiter_code(max_num)

            print(f"   → Assigning {new_rc} to {ligase}/{pdb_id}/{ligand}/{variant} (from {rc})")

            # 1) Update the 3D map table for this combo
            if not DRY_RUN:
                cur.execute("""
                    UPDATE Ligase_Ligands_Smiles_3DMapped
                    SET RECRUITER_CODE=?
                    WHERE Ligase=? AND pdb_id=? AND Ligand=? AND Variant=? AND RECRUITER_CODE=?
                """, (new_rc, ligase, pdb_id, ligand, variant, rc))

            # 2) Ensure SMILES copies exist for the new recruiter
            smi = fetch_smiles_for_recruiter(cur, rc)
            if smi:
                if not DRY_RUN:
                    # Ligase_SMILE_Codes
                    cur.execute("""
                        INSERT OR IGNORE INTO Ligase_SMILE_Codes (SMILES, RECRUITER_CODE)
                        VALUES (?, ?)
                    """, (smi, new_rc))
                    # Recruiter_SMILES_Map
                    cur.execute("""
                        INSERT OR IGNORE INTO Recruiter_SMILES_Map (SMILES, RECRUITER_CODE)
                        VALUES (?, ?)
                    """, (smi, new_rc))
            else:
                print(f"      (warn) No SMILES found for {rc}; skipping SMILES tables for {new_rc}")

            # 3) Copy atom map
            if not DRY_RUN:
                copy_atoms_map(cur, rc, new_rc)

            # 4) Copy descriptors row
            if not DRY_RUN:
                copy_descriptors(cur, rc, new_rc)

            # 5) Copy scaffold rows (if any)
            if not DRY_RUN:
                copy_scaffold_rows(cur, rc, new_rc)

            ligand_to_recruiters[ligand].add(new_rc)

    # Record duplicates summary
    if ligand_to_recruiters:
        print("Recording ligand → matched recruiters in Ligase_Duplicate_Ligands ...")
        if not DRY_RUN:
            ensure_duplicate_table(cur)
            for lig, rset in ligand_to_recruiters.items():
                upsert_duplicate_ligand(cur, lig, sorted(rset))

    if DRY_RUN:
        print("\nDRY-RUN mode: no changes written. Set DRY_RUN = False to apply fixes.")
        conn.rollback()
    else:
        conn.commit()
        print("\nDONE. Changes committed.")

    conn.close()

if __name__ == "__main__":
    main()
