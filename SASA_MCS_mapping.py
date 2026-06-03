# # # # # # # # # #!/usr/bin/env python3
# # # # # # # # # # -*- coding: utf-8 -*-
# # # # # # # # # """
# # # # # # # # # SASA_MCS_mapping.py
# # # # # # # # # --------------------------------------------------------
# # # # # # # # # Self-contained repair script for missing SASA + MCS data.

# # # # # # # # # Modes:
# # # # # # # # #   1) Auto-detect missing SASA/MCS from the DB:
# # # # # # # # #        --dry-run
# # # # # # # # #        --repair

# # # # # # # # #   2) Force recompute for ligands listed in a rewrite map:
# # # # # # # # #        --from-rewrite-map ligand_rewrite_map.csv --dry-run
# # # # # # # # #        --from-rewrite-map ligand_rewrite_map.csv --repair

# # # # # # # # # The rewrite map is expected to have columns:
# # # # # # # # #   Ligand, Ligase, PDB_ID, MW, Recruiter_Code, new_ligand

# # # # # # # # # Joseph-Michael Schulz | University of Miami BMB
# # # # # # # # # """

# # # # # # # # # import os
# # # # # # # # # import re
# # # # # # # # # import sqlite3
# # # # # # # # # import pandas as pd
# # # # # # # # # from pathlib import Path
# # # # # # # # # from Bio.PDB import PDBParser, ShrakeRupley
# # # # # # # # # from rdkit import Chem
# # # # # # # # # from rdkit.Chem import rdFMCS, Descriptors, rdMolDescriptors
# # # # # # # # # from rdkit.Chem import inchi
# # # # # # # # # from concurrent.futures import ProcessPoolExecutor, as_completed
# # # # # # # # # import multiprocessing
# # # # # # # # # import argparse
# # # # # # # # # from tqdm import tqdm

# # # # # # # # # DB_PATH = Path("Ligases/Ligase_Recruiter.db")

# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # 🧩 Utility
# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # def tuple_key(df, cols):
# # # # # # # # #     return set(tuple(x) for x in df[cols].to_numpy())

# # # # # # # # # def safe_rdkit_from_smiles(smiles):
# # # # # # # # #     try:
# # # # # # # # #         return Chem.MolFromSmiles(smiles)
# # # # # # # # #     except Exception:
# # # # # # # # #         return None

# # # # # # # # # def pdb_to_mol(pdb_path):
# # # # # # # # #     try:
# # # # # # # # #         return Chem.MolFromPDBFile(str(pdb_path), sanitize=False, removeHs=False)
# # # # # # # # #     except Exception:
# # # # # # # # #         return None

# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # 🔍 Detect missing SASA entries (DB-driven mode)
# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # def detect_missing(conn):
# # # # # # # # #     mapped = pd.read_sql_query(
# # # # # # # # #         "SELECT Ligase,pdb_id,Ligand,Variant,RECRUITER_CODE "
# # # # # # # # #         "FROM Ligase_Ligands_Smiles_3DMapped;",
# # # # # # # # #         conn,
# # # # # # # # #     )
# # # # # # # # #     sasa_sum = pd.read_sql_query(
# # # # # # # # #         "SELECT Ligase,pdb_id,Ligand,Variant "
# # # # # # # # #         "FROM Ligase_Ligand_SASA_summary;",
# # # # # # # # #         conn,
# # # # # # # # #     )
# # # # # # # # #     sasa_atoms = pd.read_sql_query(
# # # # # # # # #         "SELECT Ligase,pdb_id,Ligand,Variant "
# # # # # # # # #         "FROM Ligase_Ligand_SASA_atoms;",
# # # # # # # # #         conn,
# # # # # # # # #     )

# # # # # # # # #     keys_all   = tuple_key(mapped,    ["Ligase", "pdb_id", "Ligand", "Variant"])
# # # # # # # # #     keys_sum   = tuple_key(sasa_sum,  ["Ligase", "pdb_id", "Ligand", "Variant"])
# # # # # # # # #     keys_atoms = tuple_key(sasa_atoms,["Ligase", "pdb_id", "Ligand", "Variant"])

# # # # # # # # #     missing = []
# # # # # # # # #     for tup in keys_all:
# # # # # # # # #         if tup not in keys_sum or tup not in keys_atoms:
# # # # # # # # #             row = mapped.loc[
# # # # # # # # #                 (mapped["Ligase"]  == tup[0]) &
# # # # # # # # #                 (mapped["pdb_id"]  == tup[1]) &
# # # # # # # # #                 (mapped["Ligand"]  == tup[2]) &
# # # # # # # # #                 (mapped["Variant"] == tup[3])
# # # # # # # # #             ].iloc[0]
# # # # # # # # #             missing.append(dict(
# # # # # # # # #                 Ligase         = tup[0],
# # # # # # # # #                 pdb_id         = tup[1],
# # # # # # # # #                 Ligand         = tup[2],
# # # # # # # # #                 Variant        = tup[3],
# # # # # # # # #                 RECRUITER_CODE = row["RECRUITER_CODE"],
# # # # # # # # #             ))
# # # # # # # # #     return pd.DataFrame(missing)

# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # 🔍 Build target list from rewrite map (mapping-driven)
# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # def build_from_rewrite_map(conn, map_path):
# # # # # # # # #     """
# # # # # # # # #     Uses ligand_rewrite_map.csv (or similar) to build a list of
# # # # # # # # #     (Ligase, pdb_id, Ligand=new_ligand, Variant, RECRUITER_CODE)
# # # # # # # # #     that we will recompute SASA/MCS for.

# # # # # # # # #     Expected columns in map CSV:
# # # # # # # # #       Ligand, Ligase, PDB_ID, MW, Recruiter_Code, new_ligand
# # # # # # # # #     """
# # # # # # # # #     m = pd.read_csv(map_path)

# # # # # # # # #     required_cols = {"Ligand", "Ligase", "PDB_ID", "Recruiter_Code", "new_ligand"}
# # # # # # # # #     missing_cols  = required_cols - set(m.columns)
# # # # # # # # #     if missing_cols:
# # # # # # # # #         raise SystemExit(
# # # # # # # # #             f"❌ Rewrite map missing columns: {', '.join(sorted(missing_cols))}"
# # # # # # # # #         )

# # # # # # # # #     rows = []
# # # # # # # # #     cur  = conn.cursor()

# # # # # # # # #     for _, row in m.iterrows():
# # # # # # # # #         ligase   = row["Ligase"]
# # # # # # # # #         pdb_id   = row["PDB_ID"]
# # # # # # # # #         new_lig  = row["new_ligand"]
# # # # # # # # #         rcode    = row["Recruiter_Code"]

# # # # # # # # #         # Find which Variants actually exist for this combo in 3DMapped
# # # # # # # # #         variants = cur.execute(
# # # # # # # # #             """
# # # # # # # # #             SELECT DISTINCT Variant
# # # # # # # # #             FROM Ligase_Ligands_Smiles_3DMapped
# # # # # # # # #             WHERE Ligase = ? AND pdb_id = ? AND Ligand = ? AND RECRUITER_CODE = ?
# # # # # # # # #             """,
# # # # # # # # #             (ligase, pdb_id, new_lig, rcode),
# # # # # # # # #         ).fetchall()

# # # # # # # # #         if not variants:
# # # # # # # # #             # If there is no 3DMapped row yet (rare), assume Variant=1 so that
# # # # # # # # #             # at least SASA can be computed & inserted.
# # # # # # # # #             variants = [(1,)]

# # # # # # # # #         for (v,) in variants:
# # # # # # # # #             rows.append(
# # # # # # # # #                 dict(
# # # # # # # # #                     Ligase         = ligase,
# # # # # # # # #                     pdb_id         = pdb_id,
# # # # # # # # #                     Ligand         = new_lig,
# # # # # # # # #                     Variant        = v,
# # # # # # # # #                     RECRUITER_CODE = rcode,
# # # # # # # # #                 )
# # # # # # # # #             )

# # # # # # # # #     df = pd.DataFrame(rows).drop_duplicates()
# # # # # # # # #     return df

# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # 🧮 Compute SASA (from SASA_LIGAND_COMPLEX_FINAL.py)
# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # def compute_sasa(pdb_path, probe_radius=1.4):
# # # # # # # # #     parser = PDBParser(QUIET=True)
# # # # # # # # #     structure = parser.get_structure("complex", pdb_path)

# # # # # # # # #     # remove water
# # # # # # # # #     for model in structure:
# # # # # # # # #         for chain in model:
# # # # # # # # #             for res in list(chain):
# # # # # # # # #                 if res.resname == "HOH":
# # # # # # # # #                     chain.detach_child(res.id)

# # # # # # # # #     sr = ShrakeRupley(probe_radius=probe_radius)
# # # # # # # # #     sr.compute(structure, level="A")

# # # # # # # # #     stem = Path(pdb_path).stem  # e.g. 9GFK_A1B_2
# # # # # # # # #     parts = stem.split("_")
# # # # # # # # #     pdb_id    = parts[0]
# # # # # # # # #     ligand_tag = parts[1]
# # # # # # # # #     # variant might be suffix _2, _3, etc.
# # # # # # # # #     variant_match = re.search(r"_(\d+)$", stem)
# # # # # # # # #     variant = int(variant_match.group(1)) if variant_match else 1

# # # # # # # # #     ligase = pdb_path.parent.parent.name

# # # # # # # # #     ligand_atoms = []
# # # # # # # # #     total = 0
# # # # # # # # #     exposed = 0
# # # # # # # # #     sasa_total = 0.0
# # # # # # # # #     last_resnum = None

# # # # # # # # #     for model in structure:
# # # # # # # # #         for chain in model:
# # # # # # # # #             for residue in chain:
# # # # # # # # #                 if residue.resname.strip() == ligand_tag:
# # # # # # # # #                     resnum = residue.id[1]
# # # # # # # # #                     last_resnum = resnum
# # # # # # # # #                     for atom in residue.get_atoms():
# # # # # # # # #                         sasa_val = getattr(atom, "sasa", 0.0)
# # # # # # # # #                         total += 1
# # # # # # # # #                         if sasa_val > 0.1:
# # # # # # # # #                             exposed += 1
# # # # # # # # #                             sasa_total += sasa_val
# # # # # # # # #                             ligand_atoms.append(
# # # # # # # # #                                 {
# # # # # # # # #                                     "Ligase":      ligase,
# # # # # # # # #                                     "pdb_id":      pdb_id,
# # # # # # # # #                                     "Ligand":      ligand_tag,
# # # # # # # # #                                     "Residue_ID":  resnum,
# # # # # # # # #                                     "Variant":     variant,
# # # # # # # # #                                     "Chain":       chain.id,
# # # # # # # # #                                     "atom_id":     atom.serial_number,
# # # # # # # # #                                     "exact_atom":  atom.name,
# # # # # # # # #                                     "atom_type":   atom.element,
# # # # # # # # #                                     "x":           round(atom.coord[0], 3),
# # # # # # # # #                                     "y":           round(atom.coord[1], 3),
# # # # # # # # #                                     "z":           round(atom.coord[2], 3),
# # # # # # # # #                                     "Exposure_A2": round(sasa_val, 3),
# # # # # # # # #                                 }
# # # # # # # # #                             )

# # # # # # # # #     mw = None
# # # # # # # # #     try:
# # # # # # # # #         # crude MW estimate from ligand HETATM
# # # # # # # # #         het_lines = [
# # # # # # # # #             l
# # # # # # # # #             for l in open(pdb_path)
# # # # # # # # #             if l.startswith("HETATM") and ligand_tag in l[17:20]
# # # # # # # # #         ]
# # # # # # # # #         mol = Chem.MolFromPDBBlock("".join(het_lines), removeHs=False)
# # # # # # # # #         if mol:
# # # # # # # # #             mw = round(Descriptors.MolWt(mol), 3)
# # # # # # # # #     except Exception:
# # # # # # # # #         pass

# # # # # # # # #     percent_exposed = (exposed / total) if total else 0.0
# # # # # # # # #     recruiter_class = (
# # # # # # # # #         "Fragment Recruiter"
# # # # # # # # #         if mw and mw < 200
# # # # # # # # #         else "Drug-like Recruiter"
# # # # # # # # #         if mw and mw <= 500
# # # # # # # # #         else "Peptide-like Recruiter"
# # # # # # # # #         if mw and mw > 500
# # # # # # # # #         else "Unknown"
# # # # # # # # #     )

# # # # # # # # #     summary = {
# # # # # # # # #         "Ligase":              ligase,
# # # # # # # # #         "pdb_id":              pdb_id,
# # # # # # # # #         "Ligand":              ligand_tag,
# # # # # # # # #         "Residue_ID":          last_resnum if total else "NA",
# # # # # # # # #         "Variant":             variant,
# # # # # # # # #         "MW":                  mw if mw else "NA",
# # # # # # # # #         "Recruiter_Class":     recruiter_class,
# # # # # # # # #         "Total_atoms":         total,
# # # # # # # # #         "Exposed_atoms":       exposed,
# # # # # # # # #         "SASA_in_complex_A2":  round(sasa_total, 3),
# # # # # # # # #         "%Exposed":            round(percent_exposed, 3),
# # # # # # # # #         "%Buried":             round(1 - percent_exposed, 3),
# # # # # # # # #     }
# # # # # # # # #     return ligand_atoms, summary

# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # 🔗 Perform MCS Mapping (based on MCS_mapping.py)
# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # def perform_mcs(pdb_path, smiles, recruiter_code):
# # # # # # # # #     pdb_mol    = pdb_to_mol(pdb_path)
# # # # # # # # #     smiles_mol = safe_rdkit_from_smiles(smiles)
# # # # # # # # #     if not pdb_mol or not smiles_mol:
# # # # # # # # #         return []

# # # # # # # # #     mcs = rdFMCS.FindMCS(
# # # # # # # # #         [smiles_mol, pdb_mol],
# # # # # # # # #         completeRingsOnly=False,
# # # # # # # # #         ringMatchesRingOnly=False,
# # # # # # # # #         timeout=10,
# # # # # # # # #     )
# # # # # # # # #     if not mcs.smartsString:
# # # # # # # # #         return []

# # # # # # # # #     patt = Chem.MolFromSmarts(mcs.smartsString)
# # # # # # # # #     match_2d = smiles_mol.GetSubstructMatch(patt)
# # # # # # # # #     match_3d = pdb_mol.GetSubstructMatch(patt)
# # # # # # # # #     if not match_2d or not match_3d:
# # # # # # # # #         return []

# # # # # # # # #     conf = pdb_mol.GetConformer()
# # # # # # # # #     stem = Path(pdb_path).stem
# # # # # # # # #     parts = stem.split("_")
# # # # # # # # #     pdb_id    = parts[0]
# # # # # # # # #     ligand    = parts[1]
# # # # # # # # #     variant_match = re.search(r"_(\d+)$", stem)
# # # # # # # # #     variant = int(variant_match.group(1)) if variant_match else 1
# # # # # # # # #     ligase  = pdb_path.parent.parent.name

# # # # # # # # #     rows = []
# # # # # # # # #     for idx2d, idx3d in zip(match_2d, match_3d):
# # # # # # # # #         atom3d = pdb_mol.GetAtomWithIdx(idx3d)
# # # # # # # # #         pos    = conf.GetAtomPosition(idx3d)
# # # # # # # # #         info   = atom3d.GetPDBResidueInfo()
# # # # # # # # #         chain_id   = info.GetChainId() if info else ""
# # # # # # # # #         exact_atom = info.GetName().strip() if info else ""
# # # # # # # # #         rows.append(
# # # # # # # # #             {
# # # # # # # # #                 "Ligase":           ligase,
# # # # # # # # #                 "pdb_id":           pdb_id,
# # # # # # # # #                 "Ligand":           ligand,
# # # # # # # # #                 "Variant":          variant,
# # # # # # # # #                 "RECRUITER_CODE":   recruiter_code,
# # # # # # # # #                 "Chain":            chain_id,
# # # # # # # # #                 "atom_id":          idx3d,
# # # # # # # # #                 "exact_atom":       exact_atom,
# # # # # # # # #                 "atom_type":        atom3d.GetSymbol(),
# # # # # # # # #                 "x":                pos.x,
# # # # # # # # #                 "y":                pos.y,
# # # # # # # # #                 "z":                pos.z,
# # # # # # # # #                 "smiles_atom_index": idx2d,
# # # # # # # # #                 "smile_atom":       smiles_mol.GetAtomWithIdx(idx2d).GetSymbol(),
# # # # # # # # #             }
# # # # # # # # #         )
# # # # # # # # #     return rows

# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # 💾 Insert helpers
# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # def insert_rows(conn, table, rows):
# # # # # # # # #     if not rows:
# # # # # # # # #         return
# # # # # # # # #     df = pd.DataFrame(rows)
# # # # # # # # #     df.to_sql(table, conn, if_exists="append", index=False)

# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # 🧠 Main Repair Logic
# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # def repair_missing(conn, missing_df, probe_radius=1.4):
# # # # # # # # #     print(f"🧩 Repairing {len(missing_df)} entries...")

# # # # # # # # #     smiles_map = pd.read_sql_query(
# # # # # # # # #         "SELECT SMILES,RECRUITER_CODE FROM Ligase_SMILE_Codes;", conn
# # # # # # # # #     )
# # # # # # # # #     smi_lookup = dict(zip(smiles_map["RECRUITER_CODE"], smiles_map["SMILES"]))

# # # # # # # # #     max_workers = max(1, multiprocessing.cpu_count() - 1)
# # # # # # # # #     failed = []

# # # # # # # # #     with ProcessPoolExecutor(max_workers=max_workers) as executor:
# # # # # # # # #         futures = {}
# # # # # # # # #         for _, row in missing_df.iterrows():
# # # # # # # # #             ligase   = row["Ligase"]
# # # # # # # # #             pdb_id   = row["pdb_id"]
# # # # # # # # #             ligand   = row["Ligand"]
# # # # # # # # #             rcode    = row["RECRUITER_CODE"]

# # # # # # # # #             # try standard and variant-suffixed filenames
# # # # # # # # #             base = Path(f"Ligases/{ligase}/PDB/{pdb_id}_{ligand}.pdb")
# # # # # # # # #             if not base.exists():
# # # # # # # # #                 alt_files = list(base.parent.glob(f"{pdb_id}_{ligand}_*.pdb"))
# # # # # # # # #                 if alt_files:
# # # # # # # # #                     pdb_path = alt_files[0]
# # # # # # # # #                 else:
# # # # # # # # #                     print(f"⚠️ Missing PDB file (no variants found): {base}")
# # # # # # # # #                     failed.append((ligase, pdb_id, ligand))
# # # # # # # # #                     continue
# # # # # # # # #             else:
# # # # # # # # #                 pdb_path = base

# # # # # # # # #             futures[executor.submit(compute_sasa, pdb_path, probe_radius)] = (
# # # # # # # # #                 ligase,
# # # # # # # # #                 pdb_id,
# # # # # # # # #                 ligand,
# # # # # # # # #                 rcode,
# # # # # # # # #                 pdb_path,
# # # # # # # # #             )

# # # # # # # # #         for f in tqdm(as_completed(futures), total=len(futures)):
# # # # # # # # #             ligase, pdb_id, ligand, rcode, pdb_path = futures[f]
# # # # # # # # #             try:
# # # # # # # # #                 ligand_atoms, summary = f.result()
# # # # # # # # #                 insert_rows(conn, "Ligase_Ligand_SASA_atoms", ligand_atoms)
# # # # # # # # #                 insert_rows(conn, "Ligase_Ligand_SASA_summary", [summary])

# # # # # # # # #                 smiles = smi_lookup.get(rcode, None)
# # # # # # # # #                 if smiles:
# # # # # # # # #                     mcs_rows = perform_mcs(pdb_path, smiles, rcode)
# # # # # # # # #                     insert_rows(conn, "Ligase_Ligands_Smiles_3DMapped", mcs_rows)

# # # # # # # # #             except Exception as e:
# # # # # # # # #                 print(f"❌ {ligase} {pdb_id}_{ligand} failed: {e}")
# # # # # # # # #                 failed.append((ligase, pdb_id, ligand))

# # # # # # # # #     conn.commit()
# # # # # # # # #     print(f"\n✅ Patched {len(futures) - len(failed)} entries. {len(failed)} failed.")
# # # # # # # # #     if failed:
# # # # # # # # #         pd.DataFrame(failed, columns=["Ligase", "pdb_id", "Ligand"]).to_csv(
# # # # # # # # #             "SASA_Failed_Repairs.csv", index=False
# # # # # # # # #         )
# # # # # # # # #         print("🧾 Written SASA_Failed_Repairs.csv")

# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # 🚀 Entry Point
# # # # # # # # # # -----------------------------------------------------
# # # # # # # # # def main():
# # # # # # # # #     parser = argparse.ArgumentParser(
# # # # # # # # #         description="Repair or recompute SASA + MCS data in Ligase_Recruiter.db."
# # # # # # # # #     )
# # # # # # # # #     parser.add_argument(
# # # # # # # # #         "--dry-run",
# # # # # # # # #         action="store_true",
# # # # # # # # #         help="List target entries only; do not modify the DB.",
# # # # # # # # #     )
# # # # # # # # #     parser.add_argument(
# # # # # # # # #         "--repair",
# # # # # # # # #         action="store_true",
# # # # # # # # #         help="Compute and insert SASA+MCS for target entries.",
# # # # # # # # #     )
# # # # # # # # #     parser.add_argument(
# # # # # # # # #         "--probe",
# # # # # # # # #         type=float,
# # # # # # # # #         default=1.4,
# # # # # # # # #         help="Probe radius (Å) for Shrake–Rupley.",
# # # # # # # # #     )
# # # # # # # # #     parser.add_argument(
# # # # # # # # #         "--from-rewrite-map",
# # # # # # # # #         type=str,
# # # # # # # # #         default=None,
# # # # # # # # #         help="Optional: path to ligand_rewrite_map.csv to drive recomputation.",
# # # # # # # # #     )

# # # # # # # # #     args = parser.parse_args()

# # # # # # # # #     if not DB_PATH.exists():
# # # # # # # # #         raise SystemExit(f"❌ Database not found: {DB_PATH}")

# # # # # # # # #     conn = sqlite3.connect(DB_PATH)

# # # # # # # # #     # Decide which entries to target
# # # # # # # # #     if args.from_rewrite_map:
# # # # # # # # #         print(f"📌 Building target list from rewrite map: {args.from_rewrite_map}")
# # # # # # # # #         missing_df = build_from_rewrite_map(conn, args.from_rewrite_map)
# # # # # # # # #     else:
# # # # # # # # #         print("📌 Detecting missing SASA/MCS entries from the DB...")
# # # # # # # # #         missing_df = detect_missing(conn)

# # # # # # # # #     print(f"📊 Found {len(missing_df)} target entries.\n")

# # # # # # # # #     # Always save a report of what we plan to touch
# # # # # # # # #     missing_df.to_csv("SASA_Targets_Report.csv", index=False)
# # # # # # # # #     print("🧾 Written SASA_Targets_Report.csv\n")

# # # # # # # # #     if args.dry_run and not args.repair:
# # # # # # # # #         print("🔍 DRY RUN ONLY — no changes will be made.\n")
# # # # # # # # #         print(missing_df)
# # # # # # # # #     elif args.repair:
# # # # # # # # #         repair_missing(conn, missing_df, probe_radius=args.probe)
# # # # # # # # #     else:
# # # # # # # # #         print("⚠️ No action taken. Use --dry-run or --repair.\n")

# # # # # # # # #     conn.close()


# # # # # # # # # if __name__ == "__main__":
# # # # # # # # #     main()












# # # # # # # # # # #!/usr/bin/env python3
# # # # # # # # # # # -*- coding: utf-8 -*-
# # # # # # # # # # """
# # # # # # # # # # RepairMissingSASA_Full.py
# # # # # # # # # # --------------------------------------------------------
# # # # # # # # # # Self-contained repair script for missing SASA + MCS data.

# # # # # # # # # # Performs:
# # # # # # # # # #   1. Detection of missing SASA entries.
# # # # # # # # # #   2. SASA computation using Shrake–Rupley.
# # # # # # # # # #   3. 2D↔3D mapping via RDKit MCS.
# # # # # # # # # #   4. Direct database patching (no deletions).

# # # # # # # # # # Joseph-Michael Schulz | University of Miami BMB
# # # # # # # # # # """

# # # # # # # # # # import os
# # # # # # # # # # import re
# # # # # # # # # # import sqlite3
# # # # # # # # # # import pandas as pd
# # # # # # # # # # from pathlib import Path
# # # # # # # # # # from Bio.PDB import PDBParser, ShrakeRupley
# # # # # # # # # # from rdkit import Chem
# # # # # # # # # # from rdkit.Chem import rdFMCS, Descriptors
# # # # # # # # # # from concurrent.futures import ProcessPoolExecutor, as_completed
# # # # # # # # # # import multiprocessing
# # # # # # # # # # import argparse
# # # # # # # # # # from tqdm import tqdm

# # # # # # # # # # DB_PATH = Path("Ligases/Ligase_Recruiter.db")

# # # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # # 🧩 Utility
# # # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # def tuple_key(df, cols):
# # # # # # # # # #     return set(tuple(x) for x in df[cols].to_numpy())

# # # # # # # # # # def safe_rdkit_from_smiles(smiles):
# # # # # # # # # #     try:
# # # # # # # # # #         return Chem.MolFromSmiles(smiles)
# # # # # # # # # #     except Exception:
# # # # # # # # # #         return None

# # # # # # # # # # def pdb_to_mol(pdb_path):
# # # # # # # # # #     try:
# # # # # # # # # #         return Chem.MolFromPDBFile(str(pdb_path), sanitize=False, removeHs=False)
# # # # # # # # # #     except Exception:
# # # # # # # # # #         return None

# # # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # # 🔍 Detect missing SASA entries
# # # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # def detect_missing(conn):
# # # # # # # # # #     mapped = pd.read_sql_query("SELECT Ligase,pdb_id,Ligand,Variant,RECRUITER_CODE FROM Ligase_Ligands_Smiles_3DMapped;", conn)
# # # # # # # # # #     sasa_sum = pd.read_sql_query("SELECT Ligase,pdb_id,Ligand,Variant FROM Ligase_Ligand_SASA_summary;", conn)
# # # # # # # # # #     sasa_atoms = pd.read_sql_query("SELECT Ligase,pdb_id,Ligand,Variant FROM Ligase_Ligand_SASA_atoms;", conn)

# # # # # # # # # #     keys_all = tuple_key(mapped, ["Ligase","pdb_id","Ligand","Variant"])
# # # # # # # # # #     keys_sum = tuple_key(sasa_sum, ["Ligase","pdb_id","Ligand","Variant"])
# # # # # # # # # #     keys_atoms = tuple_key(sasa_atoms, ["Ligase","pdb_id","Ligand","Variant"])

# # # # # # # # # #     missing = []
# # # # # # # # # #     for tup in keys_all:
# # # # # # # # # #         if tup not in keys_sum or tup not in keys_atoms:
# # # # # # # # # #             row = mapped.loc[
# # # # # # # # # #                 (mapped["Ligase"]==tup[0]) &
# # # # # # # # # #                 (mapped["pdb_id"]==tup[1]) &
# # # # # # # # # #                 (mapped["Ligand"]==tup[2]) &
# # # # # # # # # #                 (mapped["Variant"]==tup[3])
# # # # # # # # # #             ].iloc[0]
# # # # # # # # # #             missing.append(dict(
# # # # # # # # # #                 Ligase=tup[0], pdb_id=tup[1], Ligand=tup[2],
# # # # # # # # # #                 Variant=tup[3], RECRUITER_CODE=row["RECRUITER_CODE"]
# # # # # # # # # #             ))
# # # # # # # # # #     return pd.DataFrame(missing)

# # # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # # 🧮 Compute SASA (from SASA_LIGAND_COMPLEX_FINAL.py)
# # # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # def compute_sasa(pdb_path, probe_radius=1.4):
# # # # # # # # # #     parser = PDBParser(QUIET=True)
# # # # # # # # # #     structure = parser.get_structure("complex", pdb_path)

# # # # # # # # # #     # remove water
# # # # # # # # # #     for model in structure:
# # # # # # # # # #         for chain in model:
# # # # # # # # # #             for res in list(chain):
# # # # # # # # # #                 if res.resname == "HOH":
# # # # # # # # # #                     chain.detach_child(res.id)

# # # # # # # # # #     sr = ShrakeRupley(probe_radius=probe_radius)
# # # # # # # # # #     sr.compute(structure, level="A")

# # # # # # # # # #     ligand_tag = Path(pdb_path).stem.split("_")[1]
# # # # # # # # # #     ligase = pdb_path.parent.parent.name
# # # # # # # # # #     pdb_id = Path(pdb_path).stem.split("_")[0]
# # # # # # # # # #     variant_match = re.search(r"_(\d+)\.pdb$", str(pdb_path))
# # # # # # # # # #     variant = int(variant_match.group(1)) if variant_match else 1

# # # # # # # # # #     ligand_atoms, total, exposed, sasa_total = [], 0, 0, 0.0
# # # # # # # # # #     for model in structure:
# # # # # # # # # #         for chain in model:
# # # # # # # # # #             for residue in chain:
# # # # # # # # # #                 if residue.resname.strip() == ligand_tag:
# # # # # # # # # #                     resnum = residue.id[1]
# # # # # # # # # #                     for atom in residue.get_atoms():
# # # # # # # # # #                         sasa_val = getattr(atom, "sasa", 0.0)
# # # # # # # # # #                         total += 1
# # # # # # # # # #                         if sasa_val > 0.1:
# # # # # # # # # #                             exposed += 1
# # # # # # # # # #                             sasa_total += sasa_val
# # # # # # # # # #                             ligand_atoms.append({
# # # # # # # # # #                                 "Ligase": ligase, "pdb_id": pdb_id, "Ligand": ligand_tag,
# # # # # # # # # #                                 "Residue_ID": resnum, "Variant": variant,
# # # # # # # # # #                                 "Chain": chain.id, "atom_id": atom.serial_number,
# # # # # # # # # #                                 "exact_atom": atom.name, "atom_type": atom.element,
# # # # # # # # # #                                 "x": round(atom.coord[0], 3),
# # # # # # # # # #                                 "y": round(atom.coord[1], 3),
# # # # # # # # # #                                 "z": round(atom.coord[2], 3),
# # # # # # # # # #                                 "Exposure_A2": round(sasa_val, 3)
# # # # # # # # # #                             })
# # # # # # # # # #     mw = None
# # # # # # # # # #     try:
# # # # # # # # # #         het_lines = [l for l in open(pdb_path) if l.startswith("HETATM") and ligand_tag in l[17:20]]
# # # # # # # # # #         mol = Chem.MolFromPDBBlock("".join(het_lines), removeHs=False)
# # # # # # # # # #         if mol:
# # # # # # # # # #             mw = round(Descriptors.MolWt(mol), 3)
# # # # # # # # # #     except Exception:
# # # # # # # # # #         pass

# # # # # # # # # #     percent_exposed = (exposed / total) if total else 0.0
# # # # # # # # # #     recruiter_class = (
# # # # # # # # # #         "Fragment Recruiter" if mw and mw < 200 else
# # # # # # # # # #         "Drug-like Recruiter" if mw and mw <= 500 else
# # # # # # # # # #         "Peptide-like Recruiter" if mw and mw > 500 else
# # # # # # # # # #         "Unknown"
# # # # # # # # # #     )
# # # # # # # # # #     summary = {
# # # # # # # # # #         "Ligase": ligase, "pdb_id": pdb_id, "Ligand": ligand_tag,
# # # # # # # # # #         "Residue_ID": resnum if total else "NA", "Variant": variant,
# # # # # # # # # #         "MW": mw if mw else "NA", "Recruiter_Class": recruiter_class,
# # # # # # # # # #         "Total_atoms": total, "Exposed_atoms": exposed,
# # # # # # # # # #         "SASA_in_complex_A2": round(sasa_total, 3),
# # # # # # # # # #         "%Exposed": round(percent_exposed, 3),
# # # # # # # # # #         "%Buried": round(1 - percent_exposed, 3)
# # # # # # # # # #     }
# # # # # # # # # #     return ligand_atoms, summary

# # # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # # 🔗 Perform MCS Mapping (based on MCS_mapping.py)
# # # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # def perform_mcs(pdb_path, smiles, recruiter_code):
# # # # # # # # # #     pdb_mol = pdb_to_mol(pdb_path)
# # # # # # # # # #     smiles_mol = safe_rdkit_from_smiles(smiles)
# # # # # # # # # #     if not pdb_mol or not smiles_mol:
# # # # # # # # # #         return []

# # # # # # # # # #     mcs = rdFMCS.FindMCS([smiles_mol, pdb_mol],
# # # # # # # # # #                          completeRingsOnly=False,
# # # # # # # # # #                          ringMatchesRingOnly=False,
# # # # # # # # # #                          timeout=10)
# # # # # # # # # #     if not mcs.smartsString:
# # # # # # # # # #         return []

# # # # # # # # # #     patt = Chem.MolFromSmarts(mcs.smartsString)
# # # # # # # # # #     match_2d = smiles_mol.GetSubstructMatch(patt)
# # # # # # # # # #     match_3d = pdb_mol.GetSubstructMatch(patt)
# # # # # # # # # #     if not match_2d or not match_3d:
# # # # # # # # # #         return []

# # # # # # # # # #     conf = pdb_mol.GetConformer()
# # # # # # # # # #     ligase = pdb_path.parent.parent.name
# # # # # # # # # #     pdb_id = Path(pdb_path).stem.split("_")[0]
# # # # # # # # # #     ligand = Path(pdb_path).stem.split("_")[1]
# # # # # # # # # #     variant = int(re.search(r"_(\d+)\.pdb$", str(pdb_path)).group(1)) if re.search(r"_(\d+)\.pdb$", str(pdb_path)) else 1

# # # # # # # # # #     rows = []
# # # # # # # # # #     for idx2d, idx3d in zip(match_2d, match_3d):
# # # # # # # # # #         atom3d = pdb_mol.GetAtomWithIdx(idx3d)
# # # # # # # # # #         pos = conf.GetAtomPosition(idx3d)
# # # # # # # # # #         chain_id = atom3d.GetPDBResidueInfo().GetChainId() if atom3d.GetPDBResidueInfo() else ""
# # # # # # # # # #         exact_atom = atom3d.GetPDBResidueInfo().GetName().strip() if atom3d.GetPDBResidueInfo() else ""
# # # # # # # # # #         rows.append({
# # # # # # # # # #             "Ligase": ligase, "pdb_id": pdb_id, "Ligand": ligand,
# # # # # # # # # #             "Variant": variant, "RECRUITER_CODE": recruiter_code,
# # # # # # # # # #             "Chain": chain_id, "atom_id": idx3d, "exact_atom": exact_atom,
# # # # # # # # # #             "atom_type": atom3d.GetSymbol(), "x": pos.x, "y": pos.y, "z": pos.z,
# # # # # # # # # #             "smiles_atom_index": idx2d, "smile_atom": smiles_mol.GetAtomWithIdx(idx2d).GetSymbol()
# # # # # # # # # #         })
# # # # # # # # # #     return rows

# # # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # # 💾 Insert functions
# # # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # def insert_rows(conn, table, rows):
# # # # # # # # # #     if not rows:
# # # # # # # # # #         return
# # # # # # # # # #     df = pd.DataFrame(rows)
# # # # # # # # # #     df.to_sql(table, conn, if_exists="append", index=False)

# # # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # # 🧠 Main Repair Logic
# # # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # def repair_missing(conn, missing_df, probe_radius=1.4):
# # # # # # # # # #     print(f"🧩 Repairing {len(missing_df)} missing entries...")
# # # # # # # # # #     smiles_map = pd.read_sql_query("SELECT SMILES,RECRUITER_CODE FROM Ligase_SMILE_Codes;", conn)
# # # # # # # # # #     smi_lookup = dict(zip(smiles_map["RECRUITER_CODE"], smiles_map["SMILES"]))

# # # # # # # # # #     max_workers = max(1, multiprocessing.cpu_count() - 1)
# # # # # # # # # #     failed = []

# # # # # # # # # #     with ProcessPoolExecutor(max_workers=max_workers) as executor:
# # # # # # # # # #         futures = {}
# # # # # # # # # #         for _, row in missing_df.iterrows():
# # # # # # # # # #             ligase, pdb_id, ligand, recruiter_code = row["Ligase"], row["pdb_id"], row["Ligand"], row["RECRUITER_CODE"]
# # # # # # # # # #             # try standard and variant-suffixed filenames
# # # # # # # # # #             base = Path(f"Ligases/{ligase}/PDB/{pdb_id}_{ligand}.pdb")
# # # # # # # # # #             if not base.exists():
# # # # # # # # # #                 # find variant candidates (e.g. _1.pdb, _2.pdb)
# # # # # # # # # #                 alt_files = list(base.parent.glob(f"{pdb_id}_{ligand}_*.pdb"))
# # # # # # # # # #                 if alt_files:
# # # # # # # # # #                     pdb_path = alt_files[0]  # pick first variant
# # # # # # # # # #                 else:
# # # # # # # # # #                     print(f"⚠️ Missing PDB file (no variants found): {base}")
# # # # # # # # # #                     failed.append((ligase, pdb_id, ligand))
# # # # # # # # # #                     continue
# # # # # # # # # #             else:
# # # # # # # # # #                 pdb_path = base

# # # # # # # # # #             futures[executor.submit(compute_sasa, pdb_path, probe_radius)] = (ligase, pdb_id, ligand, recruiter_code, pdb_path)

# # # # # # # # # #         for f in tqdm(as_completed(futures), total=len(futures)):
# # # # # # # # # #             ligase, pdb_id, ligand, recruiter_code, pdb_path = futures[f]
# # # # # # # # # #             try:
# # # # # # # # # #                 ligand_atoms, summary = f.result()
# # # # # # # # # #                 insert_rows(conn, "Ligase_Ligand_SASA_atoms", ligand_atoms)
# # # # # # # # # #                 insert_rows(conn, "Ligase_Ligand_SASA_summary", [summary])

# # # # # # # # # #                 smiles = smi_lookup.get(recruiter_code, None)
# # # # # # # # # #                 if smiles:
# # # # # # # # # #                     mcs_rows = perform_mcs(pdb_path, smiles, recruiter_code)
# # # # # # # # # #                     insert_rows(conn, "Ligase_Ligands_Smiles_3DMapped", mcs_rows)

# # # # # # # # # #             except Exception as e:
# # # # # # # # # #                 print(f"❌ {ligase} {pdb_id}_{ligand} failed: {e}")
# # # # # # # # # #                 failed.append((ligase, pdb_id, ligand))

# # # # # # # # # #     conn.commit()
# # # # # # # # # #     print(f"\n✅ Patched {len(futures)-len(failed)} entries. {len(failed)} failed.")
# # # # # # # # # #     if failed:
# # # # # # # # # #         pd.DataFrame(failed, columns=["Ligase","pdb_id","Ligand"]).to_csv("SASA_Failed_Repairs.csv", index=False)
# # # # # # # # # #         print("🧾 Written SASA_Failed_Repairs.csv")

# # # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # # 🚀 Entry Point
# # # # # # # # # # # -----------------------------------------------------
# # # # # # # # # # def main():
# # # # # # # # # #     parser = argparse.ArgumentParser(description="Repair missing SASA + MCS data directly in SQLite DB.")
# # # # # # # # # #     parser.add_argument("--dry-run", action="store_true", help="List missing SASA entries only.")
# # # # # # # # # #     parser.add_argument("--repair", action="store_true", help="Compute and insert SASA+MCS for missing entries.")
# # # # # # # # # #     parser.add_argument("--probe", type=float, default=1.4, help="Probe radius (Å).")
# # # # # # # # # #     args = parser.parse_args()

# # # # # # # # # #     if not DB_PATH.exists():
# # # # # # # # # #         raise SystemExit(f"❌ Database not found: {DB_PATH}")

# # # # # # # # # #     conn = sqlite3.connect(DB_PATH)
# # # # # # # # # #     missing_df = detect_missing(conn)
# # # # # # # # # #     print(f"📊 Found {len(missing_df)} missing entries.\n")

# # # # # # # # # #     if args.dry_run:
# # # # # # # # # #         print(missing_df)
# # # # # # # # # #         missing_df.to_csv("Missing_SASA_Report.csv", index=False)
# # # # # # # # # #         print("🧾 Written Missing_SASA_Report.csv")
# # # # # # # # # #     elif args.repair:
# # # # # # # # # #         repair_missing(conn, missing_df, probe_radius=args.probe)
# # # # # # # # # #     else:
# # # # # # # # # #         print("⚠️ No action taken. Use --dry-run or --repair.\n")

# # # # # # # # # #     conn.close()

# # # # # # # # # # if __name__ == "__main__":
# # # # # # # # # #     main()

# # # # # # # # import sqlite3
# # # # # # # # from collections import Counter

# # # # # # # # DB = "Ligases/Ligase_Recruiter.db"
# # # # # # # # conn = sqlite3.connect(DB)
# # # # # # # # cur = conn.cursor()

# # # # # # # # print("\n🔎 Inspecting SASA tables...\n")

# # # # # # # # # Unique values in SASA atoms
# # # # # # # # atoms = cur.execute("""
# # # # # # # #     SELECT Ligand, Ligase, pdb_id
# # # # # # # #     FROM Ligase_Ligand_SASA_atoms
# # # # # # # #     LIMIT 20000;
# # # # # # # # """).fetchall()

# # # # # # # # ligs = Counter([r[0] for r in atoms])
# # # # # # # # e3s  = Counter([r[1] for r in atoms])
# # # # # # # # pdbs = Counter([r[2] for r in atoms])

# # # # # # # # print("🔹 Unique Ligands (first 50):")
# # # # # # # # print(list(ligs.keys())[:50])

# # # # # # # # print("\n🔹 Unique Ligases (first 50):")
# # # # # # # # print(list(e3s.keys())[:50])

# # # # # # # # print("\n🔹 Unique PDB IDs (first 50):")
# # # # # # # # print(list(pdbs.keys())[:50])

# # # # # # # # conn.close()




# # # # # # # import sqlite3
# # # # # # # import csv
# # # # # # # import os

# # # # # # # DB = "Ligases/Ligase_Recruiter.db"
# # # # # # # BASE = "Ligases"

# # # # # # # missing_list = "Ligase_MISSING_MCS.csv"

# # # # # # # def find_pdb_path(ligase, pdb, ligand, variant):
# # # # # # #     """Return correct PDB file path using naming rules."""
# # # # # # #     path1 = f"{BASE}/{ligase}/PDB/{pdb}_{ligand}.pdb"
# # # # # # #     path2 = f"{BASE}/{ligase}/PDB/{pdb}_{ligand}_{variant}.pdb"

# # # # # # #     if os.path.exists(path1):
# # # # # # #         return path1
# # # # # # #     if os.path.exists(path2):
# # # # # # #         return path2

# # # # # # #     return None


# # # # # # # def run_diagnostics():
# # # # # # #     conn = sqlite3.connect(DB)
# # # # # # #     cur = conn.cursor()

# # # # # # #     with open(missing_list) as f:
# # # # # # #         next(f)  # skip header
# # # # # # #         missing_codes = [line.strip() for line in f]

# # # # # # #     for code in missing_codes:
# # # # # # #         print("\n" + "="*80)
# # # # # # #         print(f"🔎 Checking recruiter: {code}")
# # # # # # #         print("="*80)

# # # # # # #         # Get mapping-row info
# # # # # # #         rows = cur.execute("""
# # # # # # #             SELECT Ligase, pdb_id, Ligand, Variant
# # # # # # #             FROM Ligase_Ligands_Smiles_3DMapped
# # # # # # #             WHERE RECRUITER_CODE = ?
# # # # # # #         """, (code,)).fetchall()

# # # # # # #         if not rows:
# # # # # # #             print("❌ No 3D mapping rows found in table.")
# # # # # # #             continue

# # # # # # #         ligase, pdb_id, ligand, variant = rows[0]
# # # # # # #         print(f"Ligase: {ligase}")
# # # # # # #         print(f"PDB: {pdb_id}")
# # # # # # #         print(f"Ligand: {ligand}")
# # # # # # #         print(f"Variant: {variant}")

# # # # # # #         # Count mapping-table atoms
# # # # # # #         count_map = cur.execute("""
# # # # # # #             SELECT COUNT(*) FROM Ligase_Ligands_Smiles_3DMapped
# # # # # # #             WHERE RECRUITER_CODE = ?
# # # # # # #         """, (code,)).fetchone()[0]
# # # # # # #         print(f"🧬 3D-MAPPED atoms: {count_map}")

# # # # # # #         # Count SASA atoms
# # # # # # #         count_sasa = cur.execute("""
# # # # # # #             SELECT COUNT(*) FROM Ligase_Ligand_SASA_atoms
# # # # # # #             WHERE Ligase=? AND pdb_id=? AND Ligand=?
# # # # # # #         """, (ligase, pdb_id, ligand)).fetchone()[0]
# # # # # # #         print(f"💧 SASA atoms: {count_sasa}")

# # # # # # #         # Find PDB file
# # # # # # #         pdb_path = find_pdb_path(ligase, pdb_id, ligand, variant)
# # # # # # #         if pdb_path:
# # # # # # #             print(f"📁 PDB file found: {pdb_path}")
# # # # # # #         else:
# # # # # # #             print(f"❌ No PDB file found for: {pdb_id}_{ligand} or with variant.")

# # # # # # #     conn.close()


# # # # # # # if __name__ == "__main__":
# # # # # # #     run_diagnostics()



# # # # # # #!/usr/bin/env python3

# # # # # # import pandas as pd
# # # # # # from pathlib import Path
# # # # # # from rdkit import Chem
# # # # # # from rdkit.Chem.Scaffolds import MurckoScaffold
# # # # # # import hashlib, math
# # # # # # from collections import Counter

# # # # # # # ============================================================
# # # # # # # Paths (no old table used)
# # # # # # # ============================================================
# # # # # # BASE = Path(".")   # your working directory

# # # # # # MISSING = BASE / "missing_descriptors.csv"
# # # # # # MAP3D = BASE / "Ligase_Table" / "Ligase_Ligands_Smiles_3DMapped.csv"
# # # # # # SMILES = BASE / "Ligase_Table" / "Ligase_SMILE_Codes.csv"

# # # # # # OUT1 = BASE / "Ligase_Table" / "Ligase_Recruiters_Scaffold.csv"
# # # # # # OUT2 = BASE / "Ligase_Table" / "Ligase_Scaffold_Summary.csv"
# # # # # # OUT3 = BASE / "Ligase_Table" / "Ligase_Scaffold_Frequency.csv"


# # # # # # # ============================================================
# # # # # # # Helper functions
# # # # # # # ============================================================
# # # # # # def safe_mol(smi):
# # # # # #     try:
# # # # # #         return Chem.MolFromSmiles(smi)
# # # # # #     except:
# # # # # #         return None

# # # # # # def scaffold_smiles(smi):
# # # # # #     mol = safe_mol(smi)
# # # # # #     if not mol:
# # # # # #         return None
# # # # # #     try:
# # # # # #         scaf = MurckoScaffold.GetScaffoldForMol(mol)
# # # # # #         return Chem.MolToSmiles(scaf, canonical=True) if scaf else None
# # # # # #     except:
# # # # # #         return None

# # # # # # def hash_string(text):
# # # # # #     return hashlib.sha1(str(text).encode()).hexdigest()[:8]

# # # # # # def shannon_diversity(counts):
# # # # # #     total = sum(counts.values())
# # # # # #     if total == 0:
# # # # # #         return 0
# # # # # #     return -sum((n/total) * math.log(n/total) for n in counts.values() if n > 0)


# # # # # # # ============================================================
# # # # # # # Main
# # # # # # # ============================================================
# # # # # # def main():

# # # # # #     print(f"📥 Loading missing list from → {MISSING}")
# # # # # #     missing_df = pd.read_csv(MISSING)
# # # # # #     missing_codes = set(missing_df["RECRUITER_CODE"])

# # # # # #     print(f"🔍 Missing recruiters: {len(missing_codes)}")

# # # # # #     map3d = pd.read_csv(MAP3D)
# # # # # #     smiles = pd.read_csv(SMILES)

# # # # # #     # Build working DF
# # # # # #     df = map3d[map3d["RECRUITER_CODE"].isin(missing_codes)]
# # # # # #     df = pd.merge(df, smiles, on="RECRUITER_CODE", how="left")
# # # # # #     df = df.dropna(subset=["SMILES"])

# # # # # #     print(f"🧪 Will compute scaffolds for {len(df)} recruiters.\n")

# # # # # #     new_rows = []

# # # # # #     # ============================================================
# # # # # #     # Compute scaffolds for ALL input recruiters
# # # # # #     # ============================================================
# # # # # #     for _, row in df.iterrows():
# # # # # #         lig = row["Ligase"]
# # # # # #         code = row["RECRUITER_CODE"]
# # # # # #         smi = row["SMILES"]

# # # # # #         # Generate scaffold
# # # # # #         scaf_smi = scaffold_smiles(smi)
# # # # # #         if scaf_smi:
# # # # # #             scaf_hash = hash_string(scaf_smi)
# # # # # #         else:
# # # # # #             scaf_smi = smi
# # # # # #             scaf_hash = hash_string(smi)

# # # # # #         new_rows.append({
# # # # # #             "Ligase": lig,
# # # # # #             "Scaffold_SMILES": scaf_smi,
# # # # # #             "Scaffold_Hash": scaf_hash,
# # # # # #             "RECRUITER_CODE": code
# # # # # #         })

# # # # # #     new_df = pd.DataFrame(new_rows)

# # # # # #     # Assign sequential scaffold IDs *per ligase*
# # # # # #     final_rows = []
# # # # # #     for ligase, sub in new_df.groupby("Ligase"):
# # # # # #         sub = sub.copy()
# # # # # #         unique_hashes = sub["Scaffold_Hash"].unique()

# # # # # #         hash_to_id = {
# # # # # #             h: f"{ligase}_SCAF_{i+1}"
# # # # # #             for i, h in enumerate(unique_hashes)
# # # # # #         }

# # # # # #         for _, r in sub.iterrows():
# # # # # #             final_rows.append({
# # # # # #                 "Ligase": ligase,
# # # # # #                 "Scaffold_ID": hash_to_id[r["Scaffold_Hash"]],
# # # # # #                 "RECRUITER_CODE": r["RECRUITER_CODE"],
# # # # # #                 "Scaffold_SMILES": r["Scaffold_SMILES"],
# # # # # #                 "Scaffold_Hash": r["Scaffold_Hash"]
# # # # # #             })

# # # # # #     final_df = pd.DataFrame(final_rows)

# # # # # #     # ============================================================
# # # # # #     # Write NEW scaffold table
# # # # # #     # ============================================================
# # # # # #     final_df.to_csv(OUT1, index=False)
# # # # # #     print(f"💾 NEW scaffold table written → {OUT1}")

# # # # # #     # ============================================================
# # # # # #     # Build NEW summary & frequency tables
# # # # # #     # ============================================================
# # # # # #     freq_rows = []
# # # # # #     summary_rows = []

# # # # # #     for ligase, sub in final_df.groupby("Ligase"):
# # # # # #         freq = (
# # # # # #             sub.groupby("Scaffold_ID")
# # # # # #                .size()
# # # # # #                .reset_index(name="Recruiter_Count")
# # # # # #         )
# # # # # #         freq_rows.extend(freq.assign(Ligase=ligase).to_dict("records"))

# # # # # #         counts = Counter(freq["Recruiter_Count"])
# # # # # #         total = freq["Recruiter_Count"].sum()
# # # # # #         uniq = len(freq)

# # # # # #         summary_rows.append({
# # # # # #             "Ligase": ligase,
# # # # # #             "Unique_Scaffolds": uniq,
# # # # # #             "Total_Recruiters": total,
# # # # # #             "Diversity_Score": round(uniq/total if total>0 else 0, 3),
# # # # # #             "Shannon_Index": round(shannon_diversity(counts), 3)
# # # # # #         })

# # # # # #     pd.DataFrame(freq_rows).to_csv(OUT3, index=False)
# # # # # #     pd.DataFrame(summary_rows).to_csv(OUT2, index=False)

# # # # # #     print(f"📊 Summary written → {OUT2}")
# # # # # #     print(f"📈 Frequency written → {OUT3}")

# # # # # #     print("\n🎉 DONE — new scaffold tables built from scratch.")


# # # # # # if __name__ == "__main__":
# # # # # #     main()


# # # # # # #!/usr/bin/env python3
# # # # # # # -*- coding: utf-8 -*-
# # # # # # """
# # # # # # Compute_Advanced_Scaffold_Data.py
# # # # # # ---------------------------------
# # # # # # Enhances Ligase_Scaffold_Frequency.csv with:
# # # # # #   ✅ Bemis–Murcko scaffold classification
# # # # # #   ✅ Canonical Murcko_SMILES (core framework)
# # # # # #   ✅ Scaffold_Center_of_Mass_X/Y/Z
# # # # # #   ✅ Ligase_Scaffold_Connectivity
# # # # # #   ✅ Recruiter_Density_Score
# # # # # #   ✅ Shannon_Diversity_Index + Normalized_Diversity

# # # # # # Outputs:
# # # # # #   Ligase_Table/Ligase_Scaffold_Data.csv
# # # # # # """

# # # # # # import pandas as pd
# # # # # # from rdkit import Chem
# # # # # # from rdkit.Chem import AllChem
# # # # # # from rdkit.Chem.Scaffolds import MurckoScaffold
# # # # # # import numpy as np
# # # # # # import networkx as nx
# # # # # # from math import log
# # # # # # from pathlib import Path

# # # # # # # ============================================================
# # # # # # # ⚙️ Configuration
# # # # # # # ============================================================
# # # # # # INPUT = Path("Ligase_Table/Ligase_Scaffold_Frequency.csv")
# # # # # # OUTPUT = Path("Ligase_Table/Ligase_Scaffold_Data.csv")

# # # # # # # ============================================================
# # # # # # # 🧩 Generate Bemis–Murcko Scaffold + Classify
# # # # # # # ============================================================
# # # # # # def generate_murcko(smiles):
# # # # # #     """Return (Murcko_SMILES, Scaffold_Class) from input SMILES."""
# # # # # #     mol = Chem.MolFromSmiles(smiles)
# # # # # #     if mol is None:
# # # # # #         return "", "Unknown"
# # # # # #     try:
# # # # # #         core = MurckoScaffold.GetScaffoldForMol(mol)
# # # # # #         if core.GetNumAtoms() == 0:
# # # # # #             return "", "Acyclic"
# # # # # #         murcko_smi = Chem.MolToSmiles(core, canonical=True)
# # # # # #         ring_info = core.GetRingInfo()
# # # # # #         ring_count = ring_info.NumRings()
# # # # # #         heteroatoms = sum(1 for a in core.GetAtoms() if a.GetAtomicNum() not in (6, 1))

# # # # # #         if ring_count == 0:
# # # # # #             cls = "Acyclic"
# # # # # #         elif ring_count == 1:
# # # # # #             cls = "Monocyclic_Hetero" if heteroatoms > 0 else "Monocyclic"
# # # # # #         elif ring_count == 2:
# # # # # #             cls = "Bicyclic_Hetero" if heteroatoms > 0 else "Bicyclic"
# # # # # #         else:
# # # # # #             cls = "Polycyclic_Hetero" if heteroatoms > 0 else "Polycyclic"

# # # # # #         return murcko_smi, cls
# # # # # #     except Exception:
# # # # # #         return "", "Unknown"

# # # # # # # ============================================================
# # # # # # # ⚛️ Compute Scaffold Center of Mass
# # # # # # # ============================================================
# # # # # # def scaffold_center_of_mass(smiles):
# # # # # #     mol = Chem.MolFromSmiles(smiles)
# # # # # #     if mol is None:
# # # # # #         return np.nan, np.nan, np.nan
# # # # # #     mol = Chem.AddHs(mol)
# # # # # #     try:
# # # # # #         AllChem.EmbedMolecule(mol, randomSeed=42)
# # # # # #         conf = mol.GetConformer()
# # # # # #         coords = np.array([list(conf.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())])
# # # # # #         center = coords.mean(axis=0)
# # # # # #         return tuple(center)
# # # # # #     except Exception:
# # # # # #         return np.nan, np.nan, np.nan

# # # # # # # ============================================================
# # # # # # # 🔗 Ligase_Scaffold_Connectivity
# # # # # # # ============================================================
# # # # # # def compute_connectivity(df):
# # # # # #     G = nx.Graph()
# # # # # #     for _, row in df.iterrows():
# # # # # #         G.add_edge(row["Ligase"], row["Scaffold_ID"])
# # # # # #     connectivity = {node: G.degree(node) for node in G.nodes() if "_SCAF_" in node}
# # # # # #     df["Ligase_Scaffold_Connectivity"] = df["Scaffold_ID"].map(connectivity)
# # # # # #     return df

# # # # # # # ============================================================
# # # # # # # 📈 Recruiter_Density_Score
# # # # # # # ============================================================
# # # # # # def compute_density(df):
# # # # # #     ligase_totals = df.groupby("Ligase")["Recruiter_Count"].sum()
# # # # # #     df["Total_Recruiters"] = df["Ligase"].map(ligase_totals)
# # # # # #     df["Recruiter_Density_Score"] = df["Recruiter_Count"] / df["Total_Recruiters"]
# # # # # #     return df

# # # # # # # ============================================================
# # # # # # # 🔢 Shannon Diversity Index + Normalized Diversity
# # # # # # # ============================================================
# # # # # # def compute_shannon_index(df):
# # # # # #     ligase_groups = df.groupby("Ligase")
# # # # # #     shannon = {}
# # # # # #     normalized = {}
# # # # # #     for ligase, group in ligase_groups:
# # # # # #         counts = group["Recruiter_Count"].values
# # # # # #         total = counts.sum()
# # # # # #         p = counts / total
# # # # # #         H = -sum(p_i * log(p_i) for p_i in p if p_i > 0)
# # # # # #         Hmax = log(len(p)) if len(p) > 1 else 0
# # # # # #         shannon[ligase] = H
# # # # # #         normalized[ligase] = H / Hmax if Hmax > 0 else 0
# # # # # #     df["Shannon_Diversity_Index"] = df["Ligase"].map(shannon)
# # # # # #     df["Normalized_Diversity"] = df["Ligase"].map(normalized)
# # # # # #     return df

# # # # # # # ============================================================
# # # # # # # 🚀 Main Routine
# # # # # # # ============================================================
# # # # # # def main():
# # # # # #     df = pd.read_csv(INPUT)
# # # # # #     print(f"🔍 Loaded {len(df)} scaffolds from {INPUT.name}")

# # # # # #     smiles_file = Path("Ligase_Table/Ligase_Recruiters_Scaffold.csv")
# # # # # #     smiles_map = {}
# # # # # #     if smiles_file.exists():
# # # # # #         sdf = pd.read_csv(smiles_file)
# # # # # #         if "Scaffold_SMILES" in sdf.columns:
# # # # # #             smiles_map = dict(zip(sdf["Scaffold_ID"], sdf["Scaffold_SMILES"]))

# # # # # #     df["Scaffold_SMILES"] = df["Scaffold_ID"].map(smiles_map).fillna("")

# # # # # #     # Generate Murcko scaffold + classification
# # # # # #     murcko_smiles, scaffold_class = [], []
# # # # # #     com_x, com_y, com_z = [], [], []
# # # # # #     for smi in df["Scaffold_SMILES"]:
# # # # # #         murcko, cls = generate_murcko(smi)
# # # # # #         murcko_smiles.append(murcko)
# # # # # #         scaffold_class.append(cls)
# # # # # #         x, y, z = scaffold_center_of_mass(smi)
# # # # # #         com_x.append(x)
# # # # # #         com_y.append(y)
# # # # # #         com_z.append(z)

# # # # # #     df["Murcko_SMILES"] = murcko_smiles
# # # # # #     df["Scaffold_Class"] = scaffold_class
# # # # # #     df["Scaffold_Center_of_Mass_X"] = com_x
# # # # # #     df["Scaffold_Center_of_Mass_Y"] = com_y
# # # # # #     df["Scaffold_Center_of_Mass_Z"] = com_z

# # # # # #     df = compute_connectivity(df)
# # # # # #     df = compute_density(df)
# # # # # #     df = compute_shannon_index(df)

# # # # # #     df.to_csv(OUTPUT, index=False)
# # # # # #     print(f"✅ Saved enhanced scaffold data → {OUTPUT}")
# # # # # #     print("🧪 Added: Murcko_SMILES, Scaffold_Class, Center_of_Mass_(X/Y/Z), "
# # # # # #           "Connectivity, Recruiter_Density_Score, Shannon_Diversity_Index, Normalized_Diversity")

# # # # # # if __name__ == "__main__":
# # # # # #     main()


# # # # # #!/usr/bin/env python3
# # # # # # -*- coding: utf-8 -*-









# # # # # """
# # # # # Rebuild_All_Scaffold_Data.py
# # # # # ----------------------------
# # # # # Full scaffold pipeline from scratch.

# # # # # Inputs (in Ligase_Table/):
# # # # #   - Ligase_Ligands_Smiles_3DMapped.csv  (for Ligase–RECRUITER_CODE mapping; deduplicated)
# # # # #   - Recruiter_SMILES_Map.csv           (for RECRUITER_CODE → SMILES)

# # # # # Outputs (in Ligase_Table/):
# # # # #   1) Ligase_Recruiters_Scaffold.csv
# # # # #      Columns:
# # # # #        - Ligase
# # # # #        - Scaffold_ID
# # # # #        - RECRUITER_CODE
# # # # #        - Scaffold_SMILES
# # # # #        - Scaffold_Hash

# # # # #   2) Ligase_Scaffold_Frequency.csv
# # # # #      Columns:
# # # # #        - Ligase
# # # # #        - Scaffold_ID
# # # # #        - Recruiter_Count

# # # # #   3) Ligase_Scaffold_Summary.csv
# # # # #      Columns:
# # # # #        - Ligase
# # # # #        - Unique_Scaffolds
# # # # #        - Total_Recruiters
# # # # #        - Diversity_Score
# # # # #        - Shannon_Index

# # # # #   4) Ligase_Scaffold_Data.csv
# # # # #      Columns:
# # # # #        - Ligase
# # # # #        - Scaffold_ID
# # # # #        - Recruiter_Count
# # # # #        - Scaffold_SMILES
# # # # #        - Murcko_SMILES
# # # # #        - Scaffold_Class
# # # # #        - Scaffold_Center_of_Mass_X
# # # # #        - Scaffold_Center_of_Mass_Y
# # # # #        - Scaffold_Center_of_Mass_Z
# # # # #        - Ligase_Scaffold_Connectivity
# # # # #        - Total_Recruiters
# # # # #        - Recruiter_Density_Score
# # # # #        - Shannon_Diversity_Index
# # # # #        - Normalized_Diversity
# # # # # """

# # # # # import pandas as pd
# # # # # import numpy as np
# # # # # from pathlib import Path
# # # # # from math import log
# # # # # from collections import Counter

# # # # # from rdkit import Chem
# # # # # from rdkit.Chem import AllChem
# # # # # from rdkit.Chem.Scaffolds import MurckoScaffold
# # # # # import networkx as nx
# # # # # import hashlib


# # # # # # ============================================================
# # # # # # ⚙ PATHS
# # # # # # ============================================================
# # # # # BASE = Path(__file__).resolve().parent
# # # # # TABLE_DIR = BASE / "Ligase_Table"

# # # # # MAP3D = TABLE_DIR / "Ligase_Ligands_Smiles_3DMapped.csv"
# # # # # SMILES_MAP_FILE = TABLE_DIR / "Recruiter_SMILES_Map.csv"

# # # # # OUT_RECRUITERS = TABLE_DIR / "Ligase_Recruiters_Scaffold.csv"
# # # # # OUT_FREQ = TABLE_DIR / "Ligase_Scaffold_Frequency.csv"
# # # # # OUT_SUMMARY = TABLE_DIR / "Ligase_Scaffold_Summary.csv"
# # # # # OUT_DATA = TABLE_DIR / "Ligase_Scaffold_Data.csv"


# # # # # # ============================================================
# # # # # # 🔧 UTILITY FUNCTIONS
# # # # # # ============================================================
# # # # # def safe_mol(smi):
# # # # #     try:
# # # # #         return Chem.MolFromSmiles(smi)
# # # # #     except Exception:
# # # # #         return None


# # # # # def scaffold_from_smiles(smi):
# # # # #     """Return Bemis–Murcko scaffold SMILES for a given ligand SMILES (or None)."""
# # # # #     mol = safe_mol(smi)
# # # # #     if mol is None:
# # # # #         return None
# # # # #     try:
# # # # #         scaf = MurckoScaffold.GetScaffoldForMol(mol)
# # # # #         return Chem.MolToSmiles(scaf, canonical=True) if scaf else None
# # # # #     except Exception:
# # # # #         return None


# # # # # def hash_string(text):
# # # # #     return hashlib.sha1(str(text).encode()).hexdigest()[:8]


# # # # # def murcko_and_class(smiles):
# # # # #     """From full scaffold SMILES, return (Murcko_SMILES, Scaffold_Class)."""
# # # # #     mol = Chem.MolFromSmiles(smiles)
# # # # #     if mol is None:
# # # # #         return "", "Unknown"
# # # # #     try:
# # # # #         core = MurckoScaffold.GetScaffoldForMol(mol)
# # # # #         if core.GetNumAtoms() == 0:
# # # # #             return "", "Acyclic"

# # # # #         murcko = Chem.MolToSmiles(core, canonical=True)
# # # # #         ring_info = core.GetRingInfo()
# # # # #         ring_count = ring_info.NumRings()
# # # # #         hetero = sum(a.GetAtomicNum() not in (1, 6) for a in core.GetAtoms())

# # # # #         if ring_count == 0:
# # # # #             cls = "Acyclic"
# # # # #         elif ring_count == 1:
# # # # #             cls = "Monocyclic_Hetero" if hetero else "Monocyclic"
# # # # #         elif ring_count == 2:
# # # # #             cls = "Bicyclic_Hetero" if hetero else "Bicyclic"
# # # # #         else:
# # # # #             cls = "Polycyclic_Hetero" if hetero else "Polycyclic"

# # # # #         return murcko, cls
# # # # #     except Exception:
# # # # #         return "", "Unknown"


# # # # # def center_of_mass(smiles):
# # # # #     """Rough 3D center of mass from RDKit embedding. Returns (x,y,z) or (nan, nan, nan)."""
# # # # #     mol = Chem.MolFromSmiles(smiles)
# # # # #     if mol is None:
# # # # #         return np.nan, np.nan, np.nan
# # # # #     mol = Chem.AddHs(mol)
# # # # #     try:
# # # # #         AllChem.EmbedMolecule(mol, randomSeed=42)
# # # # #         conf = mol.GetConformer()
# # # # #         coords = np.array(
# # # # #             [
# # # # #                 [conf.GetAtomPosition(i).x,
# # # # #                  conf.GetAtomPosition(i).y,
# # # # #                  conf.GetAtomPosition(i).z]
# # # # #                 for i in range(mol.GetNumAtoms())
# # # # #             ]
# # # # #         )
# # # # #         return coords.mean(axis=0)
# # # # #     except Exception:
# # # # #         return np.nan, np.nan, np.nan


# # # # # # ============================================================
# # # # # # 🚀 MAIN PIPELINE
# # # # # # ============================================================
# # # # # def main():
# # # # #     print("\n📥 Loading mapping tables...")

# # # # #     # 1) Unique ligase–recruiter mapping from MAP3D
# # # # #     map3d_raw = pd.read_csv(MAP3D)
# # # # #     ligase_map = (
# # # # #         map3d_raw[["Ligase", "RECRUITER_CODE"]]
# # # # #         .drop_duplicates()
# # # # #         .reset_index(drop=True)
# # # # #     )
# # # # #     print(f"🔗 Unique Ligase–RECRUITER_CODE pairs: {len(ligase_map)}")

# # # # #     # 2) Recruiter → SMILES mapping (canonical source)
# # # # #     smi_map = pd.read_csv(SMILES_MAP_FILE)
# # # # #     if not {"RECRUITER_CODE", "SMILES"}.issubset(smi_map.columns):
# # # # #         raise ValueError("Recruiter_SMILES_Map.csv must contain RECRUITER_CODE and SMILES columns.")

# # # # #     # 3) Merge to get full dataset: Ligase, RECRUITER_CODE, SMILES
# # # # #     df = pd.merge(ligase_map, smi_map, on="RECRUITER_CODE", how="inner")
# # # # #     print(f"🧪 Total recruiters with SMILES: {len(df)}")

# # # # #     # ============================================================
# # # # #     # 1️⃣ PRIMARY RECRUITER–SCAFFOLD TABLE
# # # # #     # ============================================================
# # # # #     print("\n🧬 Computing primary scaffolds per recruiter...")

# # # # #     primary_rows = []
# # # # #     for _, r in df.iterrows():
# # # # #         lig = r["Ligase"]
# # # # #         code = r["RECRUITER_CODE"]
# # # # #         smi = r["SMILES"]

# # # # #         scaf_smi = scaffold_from_smiles(smi)
# # # # #         if scaf_smi:
# # # # #             scaf_hash = hash_string(scaf_smi)
# # # # #         else:
# # # # #             # Fallback: use full SMILES to define a unique pseudo-scaffold
# # # # #             scaf_smi = smi
# # # # #             scaf_hash = hash_string(smi)

# # # # #         primary_rows.append({
# # # # #             "Ligase": lig,
# # # # #             "RECRUITER_CODE": code,
# # # # #             "Scaffold_SMILES": scaf_smi,
# # # # #             "Scaffold_Hash": scaf_hash
# # # # #         })

# # # # #     df_scaff = pd.DataFrame(primary_rows)

# # # # #     # Assign scaffold IDs per ligase
# # # # #     final_rows = []
# # # # #     for ligase, group in df_scaff.groupby("Ligase"):
# # # # #         unique_hashes = list(group["Scaffold_Hash"].unique())
# # # # #         id_map = {h: f"{ligase}_SCAF_{i+1}" for i, h in enumerate(unique_hashes)}

# # # # #         for _, r in group.iterrows():
# # # # #             final_rows.append({
# # # # #                 "Ligase": ligase,
# # # # #                 "Scaffold_ID": id_map[r["Scaffold_Hash"]],
# # # # #                 "RECRUITER_CODE": r["RECRUITER_CODE"],
# # # # #                 "Scaffold_SMILES": r["Scaffold_SMILES"],
# # # # #                 "Scaffold_Hash": r["Scaffold_Hash"]
# # # # #             })

# # # # #     df_primary = pd.DataFrame(final_rows)
# # # # #     df_primary.to_csv(OUT_RECRUITERS, index=False)
# # # # #     print(f"💾 Ligase_Recruiters_Scaffold.csv written → {OUT_RECRUITERS}")

# # # # #     # ============================================================
# # # # #     # 2️⃣ FREQUENCY TABLE
# # # # #     # ============================================================
# # # # #     print("\n📊 Building scaffold frequency table...")
# # # # #     freq = (
# # # # #         df_primary.groupby(["Ligase", "Scaffold_ID"])
# # # # #                   .size()
# # # # #                   .reset_index(name="Recruiter_Count")
# # # # #     )
# # # # #     freq.to_csv(OUT_FREQ, index=False)
# # # # #     print(f"💾 Ligase_Scaffold_Frequency.csv written → {OUT_FREQ}")

# # # # #     # ============================================================
# # # # #     # 3️⃣ SUMMARY TABLE
# # # # #     # ============================================================
# # # # #     print("\n📈 Building ligase summary table...")
# # # # #     summary_rows = []
# # # # #     for ligase, sub in freq.groupby("Ligase"):
# # # # #         total = sub["Recruiter_Count"].sum()
# # # # #         uniq = len(sub)
# # # # #         diversity_score = uniq / total if total > 0 else 0.0

# # # # #         counts = sub["Recruiter_Count"].values
# # # # #         p = counts / total if total > 0 else np.zeros_like(counts, dtype=float)
# # # # #         H = -sum(pi * log(pi) for pi in p if pi > 0)

# # # # #         summary_rows.append({
# # # # #             "Ligase": ligase,
# # # # #             "Unique_Scaffolds": int(uniq),
# # # # #             "Total_Recruiters": int(total),
# # # # #             "Diversity_Score": round(diversity_score, 3),
# # # # #             "Shannon_Index": round(H, 3)
# # # # #         })

# # # # #     df_summary = pd.DataFrame(summary_rows)
# # # # #     df_summary.to_csv(OUT_SUMMARY, index=False)
# # # # #     print(f"💾 Ligase_Scaffold_Summary.csv written → {OUT_SUMMARY}")

# # # # #     # ============================================================
# # # # #     # 4️⃣ ADVANCED SCAFFOLD DATA TABLE
# # # # #     # ============================================================
# # # # #     print("\n🧮 Building advanced scaffold data table...")

# # # # #     df_data = freq.copy()

# # # # #     # Map Scaffold_SMILES from primary table
# # # # #     id_to_smiles = dict(zip(df_primary["Scaffold_ID"], df_primary["Scaffold_SMILES"]))
# # # # #     df_data["Scaffold_SMILES"] = df_data["Scaffold_ID"].map(id_to_smiles)

# # # # #     # Murcko / class / COM
# # # # #     murcko_list, class_list = [], []
# # # # #     cmx, cmy, cmz = [], [], []

# # # # #     print("   → Computing Murcko scaffolds, classes, and centers of mass...")
# # # # #     for smi in df_data["Scaffold_SMILES"]:
# # # # #         if isinstance(smi, float) and np.isnan(smi):
# # # # #             murcko_list.append("")
# # # # #             class_list.append("Unknown")
# # # # #             cmx.append(np.nan); cmy.append(np.nan); cmz.append(np.nan)
# # # # #             continue

# # # # #         m, c = murcko_and_class(smi)
# # # # #         murcko_list.append(m)
# # # # #         class_list.append(c)
# # # # #         x, y, z = center_of_mass(smi)
# # # # #         cmx.append(x); cmy.append(y); cmz.append(z)

# # # # #     df_data["Murcko_SMILES"] = murcko_list
# # # # #     df_data["Scaffold_Class"] = class_list
# # # # #     df_data["Scaffold_Center_of_Mass_X"] = cmx
# # # # #     df_data["Scaffold_Center_of_Mass_Y"] = cmy
# # # # #     df_data["Scaffold_Center_of_Mass_Z"] = cmz

# # # # #     # Connectivity: bipartite graph (Ligase – Scaffold_ID), one edge per recruiter
# # # # #     print("   → Computing ligase–scaffold connectivity...")
# # # # #     G = nx.Graph()
# # # # #     for _, r in df_primary.iterrows():
# # # # #         G.add_edge(r["Ligase"], r["Scaffold_ID"])
# # # # #     connectivity = {n: G.degree(n) for n in G.nodes() if "_SCAF_" in n}
# # # # #     df_data["Ligase_Scaffold_Connectivity"] = df_data["Scaffold_ID"].map(connectivity)

# # # # #     # Total recruiters per ligase & density
# # # # #     print("   → Computing density and diversity metrics...")
# # # # #     totals = df_data.groupby("Ligase")["Recruiter_Count"].sum()
# # # # #     df_data["Total_Recruiters"] = df_data["Ligase"].map(totals)
# # # # #     df_data["Recruiter_Density_Score"] = df_data["Recruiter_Count"] / df_data["Total_Recruiters"]

# # # # #     # Shannon per ligase & normalized
# # # # #     shannon = {}
# # # # #     normalized = {}
# # # # #     for ligase, sub in df_data.groupby("Ligase"):
# # # # #         counts = sub["Recruiter_Count"].values
# # # # #         total = counts.sum()
# # # # #         if total <= 0:
# # # # #             shannon[ligase] = 0.0
# # # # #             normalized[ligase] = 0.0
# # # # #             continue
# # # # #         p = counts / total
# # # # #         H = -sum(pi * log(pi) for pi in p if pi > 0)
# # # # #         Hmax = log(len(p)) if len(p) > 1 else 0.0
# # # # #         shannon[ligase] = H
# # # # #         normalized[ligase] = H / Hmax if Hmax > 0 else 0.0

# # # # #     df_data["Shannon_Diversity_Index"] = df_data["Ligase"].map(shannon)
# # # # #     df_data["Normalized_Diversity"] = df_data["Ligase"].map(normalized)

# # # # #     df_data.to_csv(OUT_DATA, index=False)
# # # # #     print(f"💾 Ligase_Scaffold_Data.csv written → {OUT_DATA}")

# # # # #     print("\n🎉 COMPLETE: all scaffold tables rebuilt from Recruiter_SMILES_Map + deduplicated MAP3D.\n")


# # # # # if __name__ == "__main__":
# # # # #     main()







# # # # import sqlite3
# # # # from rdkit import Chem
# # # # from rdkit.Chem.Scaffolds import MurckoScaffold

# # # # DB = "Ligases/Ligase_Recruiter.db"

# # # # def murcko(smiles):
# # # #     mol = Chem.MolFromSmiles(smiles)
# # # #     if not mol:
# # # #         return None
# # # #     scaffold = MurckoScaffold.GetScaffoldForMol(mol)
# # # #     return Chem.MolToSmiles(scaffold, canonical=True)

# # # # def get_ligase_for_recruiter(cur, code):
# # # #     row = cur.execute("""
# # # #         SELECT DISTINCT Ligase
# # # #         FROM Ligase_Ligands_Smiles_3DMapped
# # # #         WHERE RECRUITER_CODE = ?
# # # #     """, (code,)).fetchone()
# # # #     return row[0] if row else None

# # # # def get_smiles_for_recruiter(cur, code):
# # # #     row = cur.execute("""
# # # #         SELECT SMILES
# # # #         FROM Ligase_SMILE_Codes
# # # #         WHERE RECRUITER_CODE = ?
# # # #     """, (code,)).fetchone()
# # # #     return row[0] if row else None

# # # # def main():
# # # #     conn = sqlite3.connect(DB)
# # # #     cur = conn.cursor()

# # # #     missing = [
# # # #         r[0] for r in cur.execute("""
# # # #             SELECT DISTINCT sc.RECRUITER_CODE
# # # #             FROM Ligase_SMILE_Codes sc
# # # #             WHERE sc.RECRUITER_CODE NOT IN (
# # # #                 SELECT DISTINCT RECRUITER_CODE
# # # #                 FROM Ligase_Recruiters_Scaffold
# # # #             );
# # # #         """)
# # # #     ]


# # # #     print(f"⚙️ Generating scaffolds for {len(missing)} recruiters...")

# # # #     inserts = []

# # # #     for code in missing:
# # # #         smiles = get_smiles_for_recruiter(cur, code)
# # # #         if not smiles:
# # # #             print(f"❌ No SMILES for {code}")
# # # #             continue

# # # #         scaffold = murcko(smiles)
# # # #         if not scaffold:
# # # #             print(f"❌ Scaffold failed for {code}")
# # # #             continue

# # # #         ligase = get_ligase_for_recruiter(cur, code)
# # # #         if not ligase:
# # # #             print(f"❌ No ligase for {code}")
# # # #             continue

# # # #         scaffold_id = f"{ligase}_SCAF_{abs(hash(scaffold)) % 100000}"  # stable ID
# # # #         scaffold_hash = hex(abs(hash(scaffold)))[2:]

# # # #         inserts.append((ligase, scaffold_id, code, scaffold, scaffold_hash))

# # # #         print(f"✔️ {code}: {ligase}, {scaffold_id}")

# # # #     # Insert all
# # # #     cur.executemany("""
# # # #         INSERT INTO Ligase_Recruiters_Scaffold
# # # #         (Ligase, Scaffold_ID, RECRUITER_CODE, Scaffold_SMILES, Scaffold_Hash)
# # # #         VALUES (?, ?, ?, ?, ?)
# # # #     """, inserts)

# # # #     conn.commit()
# # # #     conn.close()

# # # #     print(f"🎉 Added {len(inserts)} new scaffolds successfully!")


# # # # if __name__ == "__main__":
# # # #     main()





# # # import sqlite3
# # # import csv
# # # from collections import defaultdict

# # # # Path to database
# # # DB_PATH = "Ligases/Ligase_Recruiter.db"

# # # # Output CSV
# # # OUTPUT = "scaffold_hash_groups.csv"

# # # conn = sqlite3.connect(DB_PATH)
# # # cur = conn.cursor()

# # # # Query all scaffold hash → ID pairs
# # # cur.execute("""
# # #     SELECT Scaffold_Hash, Scaffold_ID
# # #     FROM Ligase_Recruiters_Scaffold
# # #     WHERE Scaffold_Hash IS NOT NULL AND Scaffold_ID IS NOT NULL
# # # """)

# # # rows = cur.fetchall()

# # # # Group by hash
# # # groups = defaultdict(set)

# # # for scaffold_hash, scaffold_id in rows:
# # #     groups[scaffold_hash].add(scaffold_id)

# # # # Write CSV
# # # with open(OUTPUT, "w", newline="") as f:
# # #     writer = csv.writer(f)
# # #     writer.writerow(["Scaffold_Hash", "Scaffold_ID_Group"])

# # #     for scaffold_hash, ids in groups.items():
# # #         writer.writerow([scaffold_hash, ", ".join(sorted(ids))])

# # # conn.close()

# # # print(f"✅ CSV written: {OUTPUT}")

# # import csv
# # from collections import defaultdict

# # INPUT = "scaffold_hash_groups.csv"
# # OUTPUT = "scaffold_unified_map.csv"

# # # ---------------------------------------------------------
# # # 1. Read CSV and group scaffold IDs by hash
# # # ---------------------------------------------------------
# # hash_to_ids = defaultdict(list)

# # with open(INPUT, newline='') as f:
# #     reader = csv.DictReader(f)
# #     for r in reader:
# #         scaffold_hash = r["Scaffold_Hash"].strip()
# #         id_group = r["Scaffold_ID_Group"].strip()

# #         # Split multi-entries like "A, B, C"
# #         scaffold_ids = [
# #             s.strip() for s in id_group.split(",")
# #             if s.strip()
# #         ]

# #         hash_to_ids[scaffold_hash].extend(scaffold_ids)

# # # ---------------------------------------------------------
# # # 2. Assign one unified ID PER UNIQUE HASH
# # # ---------------------------------------------------------
# # output_rows = []

# # for idx, (scaffold_hash, id_list) in enumerate(hash_to_ids.items(), start=1):
# #     unified_id = f"LR-SCAF{idx:05d}"

# #     # Expand into individual rows
# #     for original_id in id_list:
# #         output_rows.append([
# #             unified_id,
# #             scaffold_hash,
# #             original_id
# #         ])

# # # ---------------------------------------------------------
# # # 3. Write output CSV
# # # ---------------------------------------------------------
# # with open(OUTPUT, "w", newline='') as f:
# #     writer = csv.writer(f)
# #     writer.writerow(["Unified_Scaffold_ID", "Scaffold_Hash", "Original_Scaffold_ID"])
# #     writer.writerows(output_rows)

# # print(f"✅ Wrote {len(output_rows)} rows to {OUTPUT}")
# # print(f"✅ Unique hashes: {len(hash_to_ids)}")





# import sqlite3

# DB_PATH = "Ligases/Ligase_Recruiter.db"

# # The two RECRUITER_CODE values to swap
# A = "L00126"
# B = "L00759"
# TMP = "__TMP_RECRUITER_SWAP__"

# print(f"\n🔄 Swapping RECRUITER_CODE '{A}' ↔ '{B}'...\n")

# conn = sqlite3.connect(DB_PATH)
# cur = conn.cursor()

# # Get all tables
# cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
# tables = [row[0] for row in cur.fetchall()]

# affected_tables = []

# for table in tables:
#     # Check table columns
#     cur.execute(f"PRAGMA table_info({table})")
#     cols = {c[1] for c in cur.fetchall()}

#     # Only apply to tables that contain EXACT column name 'RECRUITER_CODE'
#     if "RECRUITER_CODE" not in cols:
#         continue

#     affected_tables.append(table)
#     print(f"🧬 Updating RECRUITER_CODE in table: {table}")

#     # SAFE 3-step swap
#     cur.execute(f"""
#         UPDATE {table}
#         SET RECRUITER_CODE = ?
#         WHERE RECRUITER_CODE = ?
#     """, (TMP, A))

#     cur.execute(f"""
#         UPDATE {table}
#         SET RECRUITER_CODE = ?
#         WHERE RECRUITER_CODE = ?
#     """, (A, B))

#     cur.execute(f"""
#         UPDATE {table}
#         SET RECRUITER_CODE = ?
#         WHERE RECRUITER_CODE = ?
#     """, (B, TMP))

# conn.commit()
# conn.close()

# print("\n✅ Swap complete.")
# print("📌 RECRUITER_CODE updated in:", affected_tables)
# print("\n🎉 All done! Only RECRUITER_CODE columns were modified.\n")




import os
import csv
import argparse
from pathlib import Path
from collections import defaultdict

"""
Duplicate-removal logic:

For each ligand entry in ligand_rewrite_map.csv:
  - Multiple PDBs may exist for the same ligand (same recruiter_code)
  - We KEEP the PDB whose suffix matches the FINAL 'new_ligand' code (A98, B04, etc.)
  - We DELETE the “older” or undesired ones (e.g., A1I_1.pdb) if both exist.

Example:
    9QE5_A1I_1.pdb   ← delete
    9QE5_A98_1.pdb   ← KEEP
"""

# ----------------------------------------------------------------------
# Load ligand_rewrite_map.csv
# ----------------------------------------------------------------------
def load_mapping(csv_path):
    mapping = defaultdict(lambda: {"keep": None, "others": []})

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lig = row["Ligand"].strip()
            new_code = row["new_ligand"].strip()
            pdb = row["PDB_ID"].strip()

            key = f"{pdb}"
            mapping[key]["others"].append(lig)
            mapping[key]["keep"] = new_code   # final name

    return mapping


# ----------------------------------------------------------------------
# Identify duplicates in the filesystem
# ----------------------------------------------------------------------
def scan_pdb_files(base_dir, mapping):
    delete_candidates = []
    keep_map = {}

    # Build set of desired final filenames
    for pdb_id, info in mapping.items():
        keep_map[pdb_id] = info["keep"]

    # Walk all ligase PDB directories
    for root, dirs, files in os.walk(base_dir):
        for fname in files:
            if not fname.lower().endswith(".pdb"):
                continue

            # File example: 9QE5_A1I_1.pdb
            parts = fname.split("_")
            if len(parts) < 2:
                continue

            pdb_core = parts[0]       # e.g., 9QE5
            tag = parts[1]            # e.g., A1I, A98, B06 etc.

            if pdb_core not in keep_map:
                continue

            keep_code = keep_map[pdb_core]

            # If this file does NOT match the final "keep" code → mark for delete
            if not tag.startswith(keep_code):
                delete_candidates.append(os.path.join(root, fname))

    return delete_candidates


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove duplicate PDBs based on ligand rewrite map.")
    parser.add_argument("--apply", action="store_true", help="Actually delete the files (default = dry run).")
    args = parser.parse_args()

    base_dir = Path("Ligases")            # <--- adjust if needed
    csv_path = Path("ligand_rewrite_map.csv")

    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        exit(1)

    print("📁 Loading ligand rewrite map…")
    mapping = load_mapping(csv_path)

    print("🔍 Scanning for PDB duplicates…")
    duplicates = scan_pdb_files(base_dir, mapping)

    if not duplicates:
        print("✅ No duplicates found. All clean!")
        exit(0)

    print("\n===============================")
    print("     DUPLICATES DETECTED")
    print("===============================")
    for f in duplicates:
        print("🗑️ WOULD DELETE →", f)

    print("\nTotal:", len(duplicates))

    if args.apply:
        print("\n⚠️ APPLY MODE ENABLED — deleting files…")
        for f in duplicates:
            try:
                os.remove(f)
                print("✔ Deleted", f)
            except Exception as e:
                print("❌ Failed to delete", f, ":", e)
        print("\n🎉 Cleanup complete!")
    else:
        print("\n✨ Dry run only — no files were deleted.")
        print("Run with --apply to remove duplicates:")
        print("   python remove_duplicate_pdbs.py --apply")
