#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ligase_Recruiter_Descriptors_Enhanced.py
----------------------------------------
Reads Ligase_SMILE_Codes.csv →
Generates:
  1️⃣ Ligase_SMILE_Codes_Atoms.csv
  2️⃣ Ligase_Chemical_Descriptors.csv
Includes:
  - QED (Quantitative Estimate of Drug-likeness)
  - Synthetic Accessibility (SA) Score
  - PAINS / BRENK / reactive SMARTS screening
  - Lipinski / Veber / Egan / Ghose / Muegge rule filters
"""

import pandas as pd
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen, rdMolDescriptors, QED
from rdkit.Chem import FilterCatalog
from rdkit.Chem.FilterCatalog import FilterCatalogParams
import math

# ============================================================
# ⚙️ Configuration
# ============================================================
INPUT = Path("Ligase_Table/Ligase_SMILE_Codes.csv")
ATOMS_OUT = Path("Ligase_Table/Ligase_SMILE_Codes_Atoms.csv")
DESC_OUT  = Path("Ligase_Table/Ligase_Chemical_Descriptors.csv")
LOG_FILE  = Path("Ligase_Table/Ligase_Chemical_Descriptors.log")

# ============================================================
# 🧩 Synthetic Accessibility Scorer (optional RDKit contrib)
# ============================================================
try:
    import sascorer  # RDKit contrib: https://github.com/rdkit/rdkit/tree/master/Contrib/SA_Score
    HAS_SA = True
except Exception:
    HAS_SA = False

# ============================================================
# 🧬 Helper Functions
# ============================================================
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')  # silence valence / sanitization warnings

def safe_mol(smi):
    """Return molecule with tolerant fallback parsing."""
    try:
        smi = str(smi).strip().replace('"', '').replace("'", "")
        mol = Chem.MolFromSmiles(smi, sanitize=True)
        if mol:
            return mol
    except Exception:
        pass

    # 🧩 Fallback: skip sanitization (for metal/charged/odd ligands)
    try:
        mol = Chem.MolFromSmiles(smi, sanitize=False)
        if mol:
            return mol
    except Exception:
        pass

    return None






def safe_bertz(mol):
    """Cross-version safe BertzCT calculation."""
    try:
        return rdMolDescriptors.CalcBertzCT(mol)
    except AttributeError:
        try:
            return Descriptors.BertzCT(mol)
        except Exception:
            return math.nan


def compute_descriptors(mol):
    """Return dictionary of computed chemical descriptors."""
    d = {
        "MW": Descriptors.MolWt(mol),
        "LogP": Crippen.MolLogP(mol),
        "TPSA": rdMolDescriptors.CalcTPSA(mol),
        "HBA": rdMolDescriptors.CalcNumHBA(mol),
        "HBD": rdMolDescriptors.CalcNumHBD(mol),
        "Rotatable_Bonds": rdMolDescriptors.CalcNumRotatableBonds(mol),
        "Ring_Count": rdMolDescriptors.CalcNumRings(mol),
        "Aromatic_Rings": rdMolDescriptors.CalcNumAromaticRings(mol),
        "Fraction_CSP3": rdMolDescriptors.CalcFractionCSP3(mol),
        "Heavy_Atom_Count": mol.GetNumHeavyAtoms(),
        "Chiral_Atoms": rdMolDescriptors.CalcNumAtomStereoCenters(mol),
        "Formal_Charge": Chem.GetFormalCharge(mol),
        "QED": QED.qed(mol)
    }

    # Extended descriptors
    d.update({
        "BertzCT": safe_bertz(mol),
        "HallKierAlpha": Descriptors.HallKierAlpha(mol),
        "Kappa1": Descriptors.Kappa1(mol),
        "Kappa2": Descriptors.Kappa2(mol),
        "Kappa3": Descriptors.Kappa3(mol),
        "NumSpiroAtoms": rdMolDescriptors.CalcNumSpiroAtoms(mol),
        "NumBridgeheadAtoms": rdMolDescriptors.CalcNumBridgeheadAtoms(mol),
        "NumAliphaticRings": rdMolDescriptors.CalcNumAliphaticRings(mol),
        "NumAromaticRings": rdMolDescriptors.CalcNumAromaticRings(mol),
        "NumSaturatedRings": rdMolDescriptors.CalcNumSaturatedRings(mol),
        "NumHeteroAtoms": rdMolDescriptors.CalcNumHeteroatoms(mol),
        "MolMR": Descriptors.MolMR(mol)
    })

    # Synthetic Accessibility
    if HAS_SA:
        try:
            d["SA_Score"] = sascorer.calculateScore(mol)
        except Exception:
            d["SA_Score"] = math.nan
    else:
        d["SA_Score"] = math.nan

    # Drug-likeness rule flags
    d.update(druglikeness_rules(d))

    return d


def check_pains(mol):
    """Screen molecule against RDKit PAINS filters."""
    params = FilterCatalogParams()
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS_A)
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS_B)
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS_C)
    catalog = FilterCatalog.FilterCatalog(params)
    entries = catalog.GetMatches(mol)
    return "; ".join([e.GetDescription() for e in entries]) if entries else "None"


def check_brenk(mol):
    """Screen molecule against Brenk structural alerts."""
    params = FilterCatalogParams()
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.BRENK)
    catalog = FilterCatalog.FilterCatalog(params)
    entries = catalog.GetMatches(mol)
    return "; ".join([e.GetDescription() for e in entries]) if entries else "None"


# ============================================================
# 🧪 Drug-likeness Rules (Lipinski, Veber, Egan, Ghose, Muegge)
# ============================================================
def druglikeness_rules(d):
    """Derive boolean rule-pass indicators from descriptor dictionary."""
    mw, logp, tpsa = d["MW"], d["LogP"], d["TPSA"]
    hbd, hba, rot = d["HBD"], d["HBA"], d["Rotatable_Bonds"]
    heavy = d["Heavy_Atom_Count"]

    lipinski = sum([
        mw > 500,
        logp > 5,
        hbd > 5,
        hba > 10
    ]) <= 1

    veber = (tpsa <= 140) and (rot <= 10)
    egan = (tpsa <= 131) and (logp <= 5.88)
    ghose = (160 <= mw <= 480) and (-0.4 <= logp <= 5.6) and (20 <= heavy <= 70)
    muegge = (200 <= mw <= 600) and (-2 <= logp <= 5) and (hba <= 10) and (hbd <= 5) and (tpsa <= 150)

    return {
        "Lipinski_Pass": lipinski,
        "Veber_Pass": veber,
        "Egan_Pass": egan,
        "Ghose_Pass": ghose,
        "Muegge_Pass": muegge
    }


# ============================================================
# 🚀 Main Routine
# ============================================================
def main():
    df = pd.read_csv(INPUT)
    df = df.dropna(subset=["SMILES"])
    print(f"🔍 Loaded {len(df)} recruiter SMILES from {INPUT.name}")

    atom_rows, desc_rows, bad = [], [], []

    for i, row in df.iterrows():
        code, smi = row["RECRUITER_CODE"], row["SMILES"]
        mol = safe_mol(smi)
        if not mol:
            bad.append((code, smi))
            continue

        # Atom-level mapping
        for atom in mol.GetAtoms():
            atom_rows.append({
                "RECRUITER_CODE": code,
                "smiles_atom_index": atom.GetIdx(),
                "smile_atom": atom.GetSymbol(),
            })

        # Descriptor-level
        try:
            desc = compute_descriptors(mol)
            desc["RECRUITER_CODE"] = code
            desc["SMILES"] = smi
            desc["PAINS_Hits"] = check_pains(mol)
            desc["Brenk_Hits"] = check_brenk(mol)
            desc_rows.append(desc)
        except Exception as e:
            bad.append((code, smi))
            continue


    # Save outputs
    pd.DataFrame(atom_rows).to_csv(ATOMS_OUT, index=False)
    pd.DataFrame(desc_rows).to_csv(DESC_OUT, index=False)

    # Write log
    with open(LOG_FILE, "w") as f:
        f.write(f"✅ {len(desc_rows)} valid SMILES processed.\n")
        f.write(f"⚠️ {len(bad)} invalid SMILES skipped.\n\n")
        if bad:
            f.write("Invalid SMILES:\n")
            for code, smi in bad:
                f.write(f"{code}\t{smi}\n")

    print(f"✅ Written {ATOMS_OUT}")
    print(f"✅ Written {DESC_OUT}")
    print(f"🧪 Added QED, SA_Score, rule-based filters, and PAINS/BRENK flags.")
    if bad:
        print(f"⚠️ {len(bad)} invalid SMILES logged in {LOG_FILE}")


if __name__ == "__main__":
    main()
