#!/usr/bin/env python3
"""
SASA_LIGAND_COMPLEX_FINAL.py

Full integrated workflow for ligand SASA analysis, recruiter classification, and cleanup.

Features:
1. Computes ligand SASA within complexes (Shrake–Rupley, parallelized).
2. Removes atoms with Exposure_A2 == 0.0 from atom-level CSV.
3. Cleans & sorts the summary CSV by Ligase and descending %Exposed.
4. Computes ligand molecular weight (MW) using RDKit.
5. Classifies recruiters:
       - Fragment (<200 Da)
       - Drug-like (200–500 Da)
       - Peptide-like (>500 Da)
       - BRD (≥4 total fragments <200 Da in same PDB)
6. Logs BRD candidate PDB IDs with their fragment info for manual review.
7. Overwrites CSVs in place.
"""

import os
import csv
import argparse
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from Bio.PDB import PDBParser, ShrakeRupley
from pathlib import Path
import multiprocessing
from rdkit import Chem
from rdkit.Chem import Descriptors

# ---------- CONFIG ----------
DEFAULT_PROBE = 1.4
ATOM_CSV = "Ligand_SASA_atoms.csv"
SUMMARY_CSV = "Ligand_SASA_summary.csv"
LOG_FILE = "SASA_Report.log"
BRD_REPORT = "BRD_Candidates.txt"


# ---------- UTILITY: Compute MW ----------
def compute_ligand_mw(pdb_path, ligand_tag):
    """Extract ligand HETATM block and compute MW using RDKit."""
    try:
        ligand_lines = []
        with open(pdb_path) as f:
            for line in f:
                if line.startswith("HETATM") and ligand_tag in line[17:20]:
                    ligand_lines.append(line)
        if not ligand_lines:
            return None
        pdb_block = "".join(ligand_lines)
        mol = Chem.MolFromPDBBlock(pdb_block, removeHs=False)
        if mol:
            return round(Descriptors.MolWt(mol), 3)
    except Exception:
        pass
    return None


# ---------- UTILITY: Get all ligands for BRD detection ----------
def get_all_ligands(pdb_path):
    """Return {resname: MW} for all non-water HETATM residues."""
    ligands = {}
    try:
        with open(pdb_path) as f:
            lines = [l for l in f if l.startswith("HETATM") and "HOH" not in l[17:20]]
        for resname in set(l[17:20].strip() for l in lines):
            ligand_lines = [l for l in lines if resname in l[17:20]]
            pdb_block = "".join(ligand_lines)
            mol = Chem.MolFromPDBBlock(pdb_block, removeHs=False)
            if mol:
                ligands[resname] = round(Descriptors.MolWt(mol), 3)
    except Exception:
        pass
    return ligands


# ---------- CORE ANALYSIS ----------
def analyze_pdb(pdb_path, probe_radius=DEFAULT_PROBE, threshold=0.1):
    ligase = pdb_path.parent.parent.name
    pdb_id = pdb_path.stem.split("_")[0]
    ligand_tag = pdb_path.stem.split("_")[1] if "_" in pdb_path.stem else "UNK"
    variant = 1
    if pdb_path.stem.endswith(("_1", "_2", "_3")):
        variant = pdb_path.stem.split("_")[-1]

    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("complex", pdb_path)

    # Remove waters
    for model in structure:
        for chain in model:
            residues_to_remove = [r for r in chain if r.resname == "HOH"]
            for res in residues_to_remove:
                chain.detach_child(res.id)

    # --- Compute SASA ---
    sr = ShrakeRupley(probe_radius=probe_radius)
    sr.compute(structure, level="A")

    # --- Ligand MW + Recruiter class ---
    all_ligs = get_all_ligands(pdb_path)
    small_fragments = [mw for mw in all_ligs.values() if mw < 200]
    brd_flag = len(small_fragments) >= 4

    mw = compute_ligand_mw(pdb_path, ligand_tag)
    if brd_flag:
        recruiter_class = "BRD Recruiter"
    elif mw is None:
        recruiter_class = "Unknown"
    elif mw < 200:
        recruiter_class = "Fragment Recruiter"
    elif mw <= 500:
        recruiter_class = "Drug-like Recruiter"
    else:
        recruiter_class = "Peptide-like Recruiter"

    # --- Collect atom data ---
    ligand_atoms = []
    total_atoms, exposed_atoms, sasa_total = 0, 0, 0.0

    for model in structure:
        for chain in model:
            for residue in chain:
                if residue.resname.strip() == ligand_tag:
                    resnum = residue.id[1]
                    for atom in residue.get_atoms():
                        sasa_val = getattr(atom, "sasa", 0.0)
                        total_atoms += 1
                        if sasa_val > threshold:
                            exposed_atoms += 1
                            sasa_total += sasa_val
                            ligand_atoms.append({
                                "Ligase": ligase,
                                "pdb_id": pdb_id,
                                "Ligand": ligand_tag,
                                "Residue_ID": resnum,
                                "Variant": variant,
                                "MW": mw if mw else "NA",
                                "Recruiter_Class": recruiter_class,
                                "Chain": chain.id,
                                "atom_id": atom.serial_number,
                                "exact_atom": atom.name,
                                "atom_type": atom.element,
                                "x": round(atom.coord[0], 3),
                                "y": round(atom.coord[1], 3),
                                "z": round(atom.coord[2], 3),
                                "Exposure_A2": round(sasa_val, 3)
                            })

    percent_exposed = (exposed_atoms / total_atoms) if total_atoms > 0 else 0.0
    summary = {
        "Ligase": ligase,
        "pdb_id": pdb_id,
        "Ligand": ligand_tag,
        "Residue_ID": resnum if total_atoms > 0 else "NA",
        "Variant": variant,
        "MW": mw if mw else "NA",
        "Recruiter_Class": recruiter_class,
        "Total_atoms": total_atoms,
        "Exposed_atoms": exposed_atoms,
        "SASA_in_complex_A2": round(sasa_total, 3),
        "%Exposed": round(percent_exposed, 3),
        "%Buried": round(1 - percent_exposed, 3)
    }

    # Return BRD metadata if flagged
    brd_info = None
    if brd_flag:
        brd_info = {
            "pdb_id": pdb_id,
            "ligase": ligase,
            "fragment_count": len(small_fragments),
            "ligands": ", ".join([f"{k}({v} Da)" for k, v in all_ligs.items()])
        }

    return ligand_atoms, summary, brd_info


# ---------- WRITE HELPERS ----------
def write_csv_headers():
    if not os.path.exists(ATOM_CSV):
        with open(ATOM_CSV, "w", newline="") as f:
            csv.writer(f).writerow([
                "Ligase","pdb_id","Ligand","Residue_ID","Variant","MW","Recruiter_Class","Chain",
                "atom_id","exact_atom","atom_type","x","y","z","Exposure_A2"
            ])
    if not os.path.exists(SUMMARY_CSV):
        with open(SUMMARY_CSV, "w", newline="") as f:
            csv.writer(f).writerow([
                "Ligase","pdb_id","Ligand","Residue_ID","Variant","MW","Recruiter_Class",
                "Total_atoms","Exposed_atoms","SASA_in_complex_A2","%Exposed","%Buried"
            ])
    if os.path.exists(BRD_REPORT):
        os.remove(BRD_REPORT)  # reset old file


def process_file(pdb_path, probe_radius):
    try:
        ligand_atoms, summary, brd_info = analyze_pdb(pdb_path, probe_radius)

        # Write atom-level data
        with open(ATOM_CSV, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Ligase","pdb_id","Ligand","Residue_ID","Variant","MW","Recruiter_Class","Chain",
                "atom_id","exact_atom","atom_type","x","y","z","Exposure_A2"
            ])
            for row in ligand_atoms:
                writer.writerow(row)

        # Write summary data
        with open(SUMMARY_CSV, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Ligase","pdb_id","Ligand","Residue_ID","Variant","MW","Recruiter_Class",
                "Total_atoms","Exposed_atoms","SASA_in_complex_A2","%Exposed","%Buried"
            ])
            writer.writerow(summary)

        # Log BRD candidates
        if brd_info:
            with open(BRD_REPORT, "a") as log:
                log.write(
                    f"{brd_info['ligase']}: {brd_info['pdb_id']} "
                    f"({brd_info['fragment_count']} fragments) → {brd_info['ligands']}\n"
                )

        msg = f"✅ {pdb_path.name}: {summary['Exposed_atoms']}/{summary['Total_atoms']} exposed ({summary['%Exposed']:.2f})"
    except Exception as e:
        msg = f"❌ {pdb_path.name} failed: {e}"
    print(msg)
    with open(LOG_FILE, "a") as log:
        log.write(msg + "\n")


# ---------- CLEANUP ----------
def clean_outputs():
    print("\n🧹 Cleaning and sorting output files...")

    if os.path.exists(ATOM_CSV):
        atoms = pd.read_csv(ATOM_CSV)
        before = len(atoms)
        atoms = atoms[atoms["Exposure_A2"] > 0.0].reset_index(drop=True)
        after = len(atoms)
        atoms.to_csv(ATOM_CSV, index=False)
        print(f"✅ Atom-level: removed {before - after} zero-exposure atoms.")

    if os.path.exists(SUMMARY_CSV):
        summary = pd.read_csv(SUMMARY_CSV)
        if "%Exposed" in summary.columns:
            summary = summary.sort_values(
                by=["Ligase", "%Exposed"], ascending=[True, False]
            ).reset_index(drop=True)
        summary.to_csv(SUMMARY_CSV, index=False)
        print("✅ Summary: sorted by Ligase and descending %Exposed.")

    print("🎯 Cleanup complete.\n")


# ---------- MAIN ----------
def main():
    parser = argparse.ArgumentParser(description="Compute ligand SASA and classify recruiters.")
    parser.add_argument("--probe", type=float, default=DEFAULT_PROBE,
                        help="Probe radius for SASA calculation (default: 1.4 Å)")
    parser.add_argument("--ligase", type=str, default=None,
                    help="Process only this ligase folder (e.g., VHL)")

    args = parser.parse_args()

    if args.ligase:
        all_pdbs = list(Path(args.ligase).rglob("PDB/*.pdb"))
    else:
        all_pdbs = [p for p in Path(".").rglob("PDB/*.pdb")]

    total_files = len(all_pdbs)
    print(f"🔍 Scanning {total_files} PDB files with probe radius {args.probe} Å\n")

    write_csv_headers()
    max_workers = max(1, multiprocessing.cpu_count() - 1)
    print(f"🧠 Using {max_workers} of {multiprocessing.cpu_count()} CPU cores.\n")

    brd_hits = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_file, pdb, args.probe): pdb for pdb in all_pdbs}
        for i, f in enumerate(as_completed(futures), 1):
            pdb = futures[f]
            try:
                f.result()
            except Exception as e:
                print(f"❌ Error in {pdb.name}: {e}")
            if i % 10 == 0:
                print(f"📊 Progress: {i}/{total_files} processed...")

    # Count BRD hits for summary
    if os.path.exists(BRD_REPORT):
        with open(BRD_REPORT) as f:
            brd_hits = sum(1 for _ in f)

    print("\n🧾 SASA computation complete. Starting cleanup...")
    clean_outputs()
    print(f"✅ All done. Identified {brd_hits} BRD candidate structures.")
    if brd_hits > 0:
        print(f"🧪 See '{BRD_REPORT}' for manual review.\n")


if __name__ == "__main__":
    main()
