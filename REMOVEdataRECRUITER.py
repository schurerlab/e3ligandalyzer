#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3

DB_PATH = "Ligases/Ligase_Recruiter.db"
RECRUITER_CODE = "L00381"

TABLES = [
    "Ligase_Chemical_Descriptors",
    "Ligase_Ligand_Metadata",
    "Ligase_Ligand_SASA_atoms",
    "Ligase_Ligand_SASA_summary",
    "Ligase_Ligands_Smiles",
    "Ligase_Ligands_Smiles_3DMapped",
    "Recruiter_Master_Map",
    "Recruiter_SMILES_Map",
    "Ligase_SMILE_Codes",
    "Ligase_SMILE_Codes_Atoms",
    "Ligase_Recruiters_Scaffold",
    "Ligase_Duplicate_Ligands",
]

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print(f"\n🔥 Purging recruiter {RECRUITER_CODE}\n")

    for table in TABLES:
        try:
            cur.execute(
                f"DELETE FROM {table} WHERE RECRUITER_CODE = ?",
                (RECRUITER_CODE,)
            )
            print(f"✔ Cleared {table}")
        except sqlite3.OperationalError:
            # Some tables key by Ligand instead of recruiter
            try:
                cur.execute(
                    f"""
                    DELETE FROM {table}
                    WHERE Ligand IN (
                        SELECT Ligand
                        FROM Recruiter_Master_Map
                        WHERE RECRUITER_CODE = ?
                    )
                    """,
                    (RECRUITER_CODE,)
                )
                print(f"✔ Cleared {table} (via Ligand)")
            except Exception as e:
                print(f"⚠ Skipped {table}: {e}")

    conn.commit()
    conn.close()

    print(f"\n✅ Recruiter {RECRUITER_CODE} fully removed.\n")

if __name__ == "__main__":
    main()
