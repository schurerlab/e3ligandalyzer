#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
Build_Ligase_Table_Final.py
===============================================================================
Author: Joseph-Michael Schulz (UM BMB)
Purpose:
    Creates final Ligase-filtered tables by removing BRD Recruiter ligands from
    SASA summary, atoms, and metadata datasets, and exporting cleaned versions
    into ./Ligase_Table/.

Input:
    Ligand_SASA_atoms.csv
    Ligand_SASA_summary.csv
    Ligand_Metadata.csv

Output:
    Ligase_Table/
      ├── Ligase_Ligand_SASA_atoms.csv
      ├── Ligase_Ligand_SASA_summary.csv
      ├── Ligase_Ligand_Metadata.csv

    Ligase_Filter.log  (summary of removals + per-ligase row counts)
-------------------------------------------------------------------------------
"""

import os
import pandas as pd

# ====================== Setup ==========================
summary_file = "Ligand_SASA_summary.csv"
atoms_file   = "Ligand_SASA_atoms.csv"
meta_file    = "Ligand_Metadata.csv"
output_dir   = "Ligase_Table"
log_file     = "Ligase_Filter.log"

os.makedirs(output_dir, exist_ok=True)

# ====================== Load Files =====================
summary_df = pd.read_csv(summary_file)
atoms_df   = pd.read_csv(atoms_file)
meta_df    = pd.read_csv(meta_file)

print(f"📥 Loaded {len(summary_df)} summary rows, "
      f"{len(atoms_df)} atom rows, and {len(meta_df)} metadata rows.")

# ====================== Filter BRD Recruiter =====================
if "Recruiter_Class" in summary_df.columns:
    brd_rows = summary_df[summary_df["Recruiter_Class"]
                          .str.contains("BRD Recruiter", case=False, na=False)]
    brd_ligands = sorted(brd_rows["Ligand"].unique())
else:
    brd_ligands = []
    print("⚠️ No 'Recruiter_Class' column found in summary — skipping BRD filter.")

print(f"🚫 Removing {len(brd_ligands)} BRD Recruiter ligands: {', '.join(brd_ligands) if brd_ligands else 'None'}")

# Filter summary
summary_filtered = summary_df[~summary_df["Ligand"].isin(brd_ligands)].copy()

# Filter atoms
atoms_filtered = atoms_df[~atoms_df["Ligand"].isin(brd_ligands)].copy()

# Filter metadata
meta_filtered = meta_df[~meta_df["Ligand"].isin(brd_ligands)].copy()

# ====================== Save Outputs =====================
summary_out = os.path.join(output_dir, "Ligase_Ligand_SASA_summary.csv")
atoms_out   = os.path.join(output_dir, "Ligase_Ligand_SASA_atoms.csv")
meta_out    = os.path.join(output_dir, "Ligase_Ligand_Metadata.csv")

summary_filtered.to_csv(summary_out, index=False)
atoms_filtered.to_csv(atoms_out, index=False)
meta_filtered.to_csv(meta_out, index=False)

print("✅ Cleaned datasets saved in Ligase_Table/")

# ====================== Per-Ligase Count Summary =====================
ligase_counts = {}
if "Ligase" in summary_filtered.columns:
    ligase_counts = summary_filtered["Ligase"].value_counts().to_dict()

# ====================== Logging =====================
with open(log_file, "w") as log:
    log.write("=== Ligase Table Finalization Log ===\n\n")
    log.write(f"Removed {len(brd_ligands)} BRD Recruiter ligands:\n")
    for lig in brd_ligands:
        log.write(f" - {lig}\n")
    log.write("\n")
    log.write(f"Summary rows after filter: {len(summary_filtered)}\n")
    log.write(f"Atoms rows after filter:   {len(atoms_filtered)}\n")
    log.write(f"Metadata rows after filter:{len(meta_filtered)}\n\n")

    if ligase_counts:
        log.write("=== Remaining Rows per Ligase ===\n")
        for ligase, count in sorted(ligase_counts.items()):
            log.write(f"{ligase:<10} : {count}\n")
        log.write("\n")

print(f"🧾 Log written to {log_file}")
