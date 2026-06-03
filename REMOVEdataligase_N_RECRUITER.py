#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3

DB_PATH = "Ligases/Ligase_Recruiter.db"

RECRUITER_CODE = "L0087"
TARGET_LIGASE  = "CIAP2"

LIGASE_SCOPED_TABLES = [
    "Ligase_Ligand_SASA_atoms",
    "Ligase_Ligand_SASA_summary",
    "Ligase_Ligands_Smiles_3DMapped",
    "Ligase_Recruiters_Scaffold",
]

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print(f"\n🧼 Removing recruiter {RECRUITER_CODE} from ligase {TARGET_LIGASE}\n")

    for table in LIGASE_SCOPED_TABLES:
        try:
            cur.execute(
                f"""
                DELETE FROM {table}
                WHERE RECRUITER_CODE = ?
                  AND Ligase = ?
                """,
                (RECRUITER_CODE, TARGET_LIGASE)
            )
            print(f"✔ Cleaned {table}")

        except sqlite3.OperationalError:
            # Some tables don’t carry RECRUITER_CODE directly
            try:
                cur.execute(
                    f"""
                    DELETE FROM {table}
                    WHERE Ligase = ?
                      AND Ligand IN (
                          SELECT Ligand
                          FROM Recruiter_Master_Map
                          WHERE RECRUITER_CODE = ?
                      )
                    """,
                    (TARGET_LIGASE, RECRUITER_CODE)
                )
                print(f"✔ Cleaned {table} (via Ligand)")

            except Exception as e:
                print(f"⚠ Skipped {table}: {e}")

    conn.commit()
    conn.close()

    print(f"\n✅ {RECRUITER_CODE} removed from {TARGET_LIGASE} only.\n")

if __name__ == "__main__":
    main()
