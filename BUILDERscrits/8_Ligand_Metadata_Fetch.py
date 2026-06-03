#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
Fetch_Ligand_Metadata_RDKit_Local.py
===============================================================================
Author: Joseph-Michael Schulz (UM BMB)
Purpose:
    Builds a full ligand metadata table by combining:
      - RCSB chem_comp info (name, formula, type)
      - SMILES from components-smiles-stereo-oe.smi
      - RDKit-derived chemical descriptors (canonical SMILES, InChI, InChIKey,
        formal charge, atom counts, aromatic bonds, etc.)

Outputs:
    Ligand_Metadata.csv  (appended in real time)
-------------------------------------------------------------------------------
Dependencies:
    pip install rdkit-pypi requests pandas tqdm
-------------------------------------------------------------------------------
"""

import os
import csv
import time
import json
import requests
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors
from tqdm import tqdm

# ============================ Configuration ==================================
INPUT_LIGANDS = "Ligand_PDB_Index.csv"
SMILES_FILE   = "components-smiles-stereo-oe.smi"
OUTPUT_FILE   = "Ligand_Metadata.csv"

RCSB_API = "https://data.rcsb.org/rest/v1/core/chemcomp/{}"

# ============================ Load SMILES file ===============================
print(f"📂 Loading SMILES mapping from: {SMILES_FILE}")
smiles_map = {}
with open(SMILES_FILE, "r") as f:
    for line in f:
        parts = line.strip().split("\t")
        if len(parts) >= 2:
            smi, lig = parts[0], parts[1].upper().strip()
            smiles_map[lig] = smi

print(f"✅ Loaded {len(smiles_map):,} SMILES entries")

# ============================ Resume-safe setup ==============================
existing = set()
if os.path.exists(OUTPUT_FILE):
    existing = {row["Ligand"] for row in csv.DictReader(open(OUTPUT_FILE))}
    print(f"🔁 Found existing {len(existing)} ligands in {OUTPUT_FILE}")

# ============================ Prepare Output =================================
header = [
    "Ligand", "Name", "Formula", "Type",
    "SMILES", "Canonical_SMILES", "InChI", "InChIKey",
    "Formal_Charge", "Atom_Count", "Chiral_Atom_Count",
    "Bond_Count", "Aromatic_Bond_Count"
]

if not os.path.exists(OUTPUT_FILE):
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()

# ============================ Load Ligand List ===============================
ligands = pd.read_csv(INPUT_LIGANDS)
ligands = ligands["Ligand"].dropna().unique()
print(f"🧪 Total ligands to process: {len(ligands)}")

# ============================ Helper Functions ===============================
def fetch_rcsb(ligand):
    """Get name, formula, type from RCSB chem_comp."""
    try:
        r = requests.get(RCSB_API.format(ligand), timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {
                "Name": data.get("chem_comp", {}).get("name", ""),
                "Formula": data.get("chem_comp", {}).get("formula", ""),
                "Type": data.get("chem_comp", {}).get("type", "")
            }
    except Exception as e:
        print(f"⚠️ RCSB fetch failed for {ligand}: {e}")
    return {"Name": "", "Formula": "", "Type": ""}

def compute_rdkit(smiles):
    """Compute descriptors from SMILES using RDKit."""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return {}
        return {
            "Canonical_SMILES": Chem.MolToSmiles(mol, canonical=True),
            "InChI": Chem.MolToInchi(mol),
            "InChIKey": Chem.InchiToInchiKey(Chem.MolToInchi(mol)),
            "Formal_Charge": Chem.GetFormalCharge(mol),
            "Atom_Count": mol.GetNumAtoms(),
            "Chiral_Atom_Count": len([a for a in mol.GetAtoms() if a.HasProp('_CIPCode')]),
            "Bond_Count": mol.GetNumBonds(),
            "Aromatic_Bond_Count": len([b for b in mol.GetBonds() if b.GetIsAromatic()])
        }
    except Exception:
        return {}

# ============================ Main Loop ======================================
with open(OUTPUT_FILE, "a", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=header)

    for lig in tqdm(ligands, desc="Processing ligands"):
        lig = lig.strip().upper()
        if lig in existing:
            continue

        smiles = smiles_map.get(lig, "")
        if not smiles:
            print(f"⚠️ No SMILES found for {lig}, skipping.")
            continue

        rc = fetch_rcsb(lig)
        rd = compute_rdkit(smiles)

        row = {
            "Ligand": lig,
            "Name": rc["Name"],
            "Formula": rc["Formula"],
            "Type": rc["Type"],
            "SMILES": smiles,
            **{k: rd.get(k, "") for k in header if k not in ["Ligand", "Name", "Formula", "Type", "SMILES"]}
        }

        writer.writerow(row)
        f.flush()
        existing.add(lig)

print("\n✅ Done! Metadata appended to", OUTPUT_FILE)
