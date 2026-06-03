#!/usr/bin/env python3
"""
Sync_Ligase_Data.py
=====================================
Deletes old VHL entries and re-inserts corrected ones
from Ligand_SASA_atoms.csv and Ligand_SASA_summary.csv
into Ligase_Recruiter.db.

Automatically drops extra columns not found in the DB.
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("Ligase_Recruiter.db")
ATOM_CSV = Path("Ligand_SASA_atoms.csv")
SUMMARY_CSV = Path("Ligand_SASA_summary.csv")
TARGET_LIGASE = "VHL"

def get_table_columns(conn, table_name):
    """Return list of column names in an existing SQLite table."""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name});")
    return [r[1] for r in cur.fetchall()]

def main():
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH.resolve()}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # --- Detect table names ---
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cur.fetchall()]
    atom_table = next((t for t in tables if "atoms" in t.lower()), None)
    summary_table = next((t for t in tables if "summary" in t.lower()), None)

    print(f"📋 Found tables: {atom_table}, {summary_table}")

    # --- Delete old VHL rows ---
    deleted = {}
    for table in [atom_table, summary_table]:
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE Ligase=?;", (TARGET_LIGASE,))
        count_before = cur.fetchone()[0]
        cur.execute(f"DELETE FROM {table} WHERE Ligase=?;", (TARGET_LIGASE,))
        conn.commit()
        deleted[table] = count_before
        print(f"🧹 Deleted {count_before} rows from {table}.")

    # --- Load CSVs ---
    atoms_df = pd.read_csv(ATOM_CSV)
    summary_df = pd.read_csv(SUMMARY_CSV)

    # --- Filter ligase rows ---
    atoms_new = atoms_df[atoms_df["Ligase"] == TARGET_LIGASE].copy()
    summary_new = summary_df[summary_df["Ligase"] == TARGET_LIGASE].copy()

    # --- Drop extra columns not in DB ---
    atom_cols = get_table_columns(conn, atom_table)
    summary_cols = get_table_columns(conn, summary_table)

    atoms_final = atoms_new[[c for c in atoms_new.columns if c in atom_cols]]
    summary_final = summary_new[[c for c in summary_new.columns if c in summary_cols]]

    print(f"\n📊 Prepared {len(atoms_final)} atom rows and {len(summary_final)} summary rows for insertion.\n")

    # --- Insert new rows ---
    atoms_final.to_sql(atom_table, conn, if_exists="append", index=False)
    summary_final.to_sql(summary_table, conn, if_exists="append", index=False)

    # --- Verification ---
    cur.execute(f"SELECT COUNT(*) FROM {atom_table} WHERE Ligase=?;", (TARGET_LIGASE,))
    atom_new = cur.fetchone()[0]
    cur.execute(f"SELECT COUNT(*) FROM {summary_table} WHERE Ligase=?;", (TARGET_LIGASE,))
    sum_new = cur.fetchone()[0]

    conn.close()

    print("✅ Database successfully refreshed.\n")
    print(f"🧾 Summary:")
    print(f"   {atom_table}: removed {deleted[atom_table]} → inserted {atom_new}")
    print(f"   {summary_table}: removed {deleted[summary_table]} → inserted {sum_new}")
    print(f"\n💾 Ligase_Recruiter.db now contains updated {TARGET_LIGASE} entries.\n")

if __name__ == "__main__":
    main()
