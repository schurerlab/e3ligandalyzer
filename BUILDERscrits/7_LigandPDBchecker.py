#!/usr/bin/env python3
"""
Ligand_PDB_Index.py

Generates a ranked summary of all ligands and the PDB structures
they appear in, based on frequency of occurrence.

Outputs:
  - Ligand_PDB_Index.csv
  - Ligand_PDB_Index.txt

Columns:
  Rank | Ligand | Count | PDB_List
"""

import pandas as pd
import os

SUMMARY_FILE = "Ligand_SASA_summary.csv"
OUT_CSV = "Ligand_PDB_Index.csv"
OUT_TXT = "Ligand_PDB_Index.txt"

def main():
    if not os.path.exists(SUMMARY_FILE):
        print(f"❌ File not found: {SUMMARY_FILE}")
        return

    df = pd.read_csv(SUMMARY_FILE)
    if "Ligand" not in df.columns or "pdb_id" not in df.columns:
        print("❌ Missing required columns 'Ligand' or 'pdb_id'")
        return

    # Group by ligand → collect unique PDB codes
    grouped = (
        df.groupby("Ligand")["pdb_id"]
        .apply(lambda x: sorted(set(str(i) for i in x)))
        .reset_index()
    )

    # Add count column
    grouped["Count"] = grouped["pdb_id"].apply(len)
    grouped = grouped.rename(columns={"pdb_id": "PDB_List"})

    # Sort by count (descending), then alphabetically
    grouped = grouped.sort_values(by=["Count", "Ligand"], ascending=[False, True]).reset_index(drop=True)

    # Add rank column
    grouped.insert(0, "Rank", range(1, len(grouped) + 1))

    # Write CSV
    grouped.to_csv(OUT_CSV, index=False)
    print(f"💾 Written ranked ligand index: {OUT_CSV} ({len(grouped)} ligands)")

    # Write TXT
    with open(OUT_TXT, "w") as f:
        for _, row in grouped.iterrows():
            ligand = row["Ligand"]
            count = row["Count"]
            pdbs = ", ".join(row["PDB_List"])
            f.write(f"{row['Rank']:>3}. {ligand} ({count} PDBs): {pdbs}\n")

    print(f"🧾 Written ranked list: {OUT_TXT}")
    print("\n🎯 Ligand–PDB frequency mapping complete!")

if __name__ == "__main__":
    main()
