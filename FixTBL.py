# import sqlite3
# import pandas as pd
# import os
# import shutil
# import glob

# from rdkit import Chem
# from rdkit.Chem import rdMolDescriptors
# from rdkit.Chem import inchi

# DB_PATH = "Ligases/Ligase_Recruiter.db"
# BASE = "Ligases"
# LOGFILE = "ligand_rewrite.log"


# # ---------------------------------------------------------
# # Helpers: NEW ligand ID generator
# # ---------------------------------------------------------
# def new_ligand_ids(n):
#     """
#     Generates ligand IDs like:
#       A00, A01, ..., A99, B00, ..., B99, ...
#     Enough for n unique entries.
#     """
#     letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
#     out = []
#     for L in letters:
#         for i in range(100):
#             out.append(f"{L}{i:02d}")
#             if len(out) == n:
#                 return out
#     return out


# # ---------------------------------------------------------
# # RDKit Metadata Generator
# # ---------------------------------------------------------
# def compute_metadata(smiles):
#     mol = Chem.MolFromSmiles(smiles)
#     if mol is None:
#         return None

#     try:
#         mf = rdMolDescriptors.CalcMolFormula(mol)
#     except Exception:
#         mf = ""

#     try:
#         can_smi = Chem.MolToSmiles(mol, canonical=True)
#     except Exception:
#         can_smi = smiles

#     try:
#         inch = inchi.MolToInchi(mol)
#         inchikey = inchi.MolToInchiKey(inch)
#     except Exception:
#         inch = ""
#         inchikey = ""

#     aromatic_bonds = sum(1 for b in mol.GetBonds() if b.GetIsAromatic())

#     return {
#         "Name": "",
#         "Formula": mf,
#         "Type": "ligand",
#         "SMILES": smiles,
#         "Canonical_SMILES": can_smi,
#         "InChI": inch,
#         "InChIKey": inchikey,
#         "Formal_Charge": Chem.GetFormalCharge(mol),
#         "Atom_Count": mol.GetNumAtoms(),
#         "Chiral_Atom_Count": rdMolDescriptors.CalcNumAtomStereoCenters(mol),
#         "Bond_Count": mol.GetNumBonds(),
#         "Aromatic_Bond_Count": aromatic_bonds,
#     }


# # ---------------------------------------------------------
# # File Operations
# # ---------------------------------------------------------
# def copy_and_relabel_files(ligase, pdb_id, old_lig, new_lig):
#     lig_dir = os.path.join(BASE, ligase)

#     # --------------------------
#     # PDB FILES
#     # --------------------------
#     pdb_pattern = os.path.join(lig_dir, "PDB", f"{pdb_id}_{old_lig}*.pdb")
#     pdb_files = glob.glob(pdb_pattern)

#     for pdb_src in pdb_files:
#         filename = os.path.basename(pdb_src)
#         suffix = filename.split(old_lig, 1)[1]  # e.g., "_1.pdb" or ".pdb"

#         pdb_dst = os.path.join(lig_dir, "PDB", f"{pdb_id}_{new_lig}{suffix}")

#         with open(pdb_src, "r") as f:
#             text = f.read()

#         # Replace ligand label
#         text = text.replace(f" {old_lig} ", f" {new_lig} ")

#         with open(pdb_dst, "w") as f:
#             f.write(text)

#     # --------------------------
#     # SDF_4Download
#     # --------------------------
#     sdf_pattern = os.path.join(lig_dir, "SDF_4Download", f"{pdb_id}_{old_lig}*.sdf")
#     sdf_files = glob.glob(sdf_pattern)

#     for sdf_src in sdf_files:
#         filename = os.path.basename(sdf_src)
#         suffix = filename.split(old_lig, 1)[1]
#         sdf_dst = os.path.join(lig_dir, "SDF_4Download", f"{pdb_id}_{new_lig}{suffix}")
#         shutil.copy2(sdf_src, sdf_dst)

#     # --------------------------
#     # Ligand-level SDF
#     # --------------------------
#     sdf_lig_pattern = os.path.join(lig_dir, "SDF", f"{ligase}_{old_lig}*.sdf")
#     sdf_lig_files = glob.glob(sdf_lig_pattern)

#     for sdf_src in sdf_lig_files:
#         filename = os.path.basename(sdf_src)
#         suffix = filename.split(old_lig, 1)[1]
#         sdf_dst = os.path.join(lig_dir, "SDF", f"{ligase}_{new_lig}{suffix}")
#         shutil.copy2(sdf_src, sdf_dst)


# # ---------------------------------------------------------
# # Database Updates
# # ---------------------------------------------------------
# def rewrite_in_db(conn, ligase, pdb_id, old_lig, new_lig, mw, recruiter_code):
#     cur = conn.cursor()

#     # SASA atoms
#     cur.execute(
#         """
#         UPDATE Ligase_Ligand_SASA_atoms
#         SET Ligand = ?
#         WHERE Ligase = ? AND pdb_id = ? AND Ligand = ? AND MW = ?
#         """,
#         (new_lig, ligase, pdb_id, old_lig, mw),
#     )

#     # SASA summary
#     cur.execute(
#         """
#         UPDATE Ligase_Ligand_SASA_summary
#         SET Ligand = ?
#         WHERE Ligase = ? AND pdb_id = ? AND Ligand = ? AND MW = ?
#         """,
#         (new_lig, ligase, pdb_id, old_lig, mw),
#     )

#     # 3D-Mapped
#     cur.execute(
#         """
#         UPDATE Ligase_Ligands_Smiles_3DMapped
#         SET Ligand = ?
#         WHERE Ligase = ? AND pdb_id = ? AND Ligand = ? AND RECRUITER_CODE = ?
#         """,
#         (new_lig, ligase, pdb_id, old_lig, recruiter_code),
#     )


# # ---------------------------------------------------------
# # Metadata Insert
# # ---------------------------------------------------------
# def insert_metadata(conn, new_lig, smiles):
#     meta = compute_metadata(smiles)
#     if meta is None:
#         return

#     cur = conn.cursor()
#     cur.execute(
#         """
#         INSERT INTO Ligase_Ligand_Metadata
#         (Ligand, Name, Formula, Type, SMILES, Canonical_SMILES, InChI, InChIKey,
#          Formal_Charge, Atom_Count, Chiral_Atom_Count, Bond_Count, Aromatic_Bond_Count)
#         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
#         """,
#         (
#             new_lig,
#             meta["Name"],
#             meta["Formula"],
#             meta["Type"],
#             meta["SMILES"],
#             meta["Canonical_SMILES"],
#             meta["InChI"],
#             meta["InChIKey"],
#             meta["Formal_Charge"],
#             meta["Atom_Count"],
#             meta["Chiral_Atom_Count"],
#             meta["Bond_Count"],
#             meta["Aromatic_Bond_Count"],
#         ),
#     )


# # ---------------------------------------------------------
# # MAIN PIPELINE
# # ---------------------------------------------------------
# def main():
#     df = pd.read_csv("ligand_duplicates.csv")

#     # Normalize column names
#     df.columns = [c.strip().lower() for c in df.columns]

#     required_cols = {"ligand", "ligase", "pdb_id", "mw", "recruiter_code"}
#     if not required_cols.issubset(df.columns):
#         raise ValueError(f"CSV missing required columns: {required_cols - set(df.columns)}")

#     # Assign unique new ligand IDs
#     df["new_ligand"] = new_ligand_ids(len(df))

#     # Save the mapping
#     df.to_csv("ligand_rewrite_map.csv", index=False)

#     conn = sqlite3.connect(DB_PATH)
#     log = open(LOGFILE, "w")

#     for i, row in df.iterrows():
#         ligase = row["ligase"]
#         pdb_id = row["pdb_id"]
#         old_lig = row["ligand"]
#         rec_code = row["recruiter_code"]
#         mw = row["mw"]
#         new_lig = row["new_ligand"]

#         log.write(
#             f"\n=== Row {i+1} ===\n"
#             f"  Ligase: {ligase}\n"
#             f"  pdb_id: {pdb_id}\n"
#             f"  Old Ligand: {old_lig}\n"
#             f"  New Ligand: {new_lig}\n"
#             f"  MW: {mw}\n"
#             f"  Recruiter Code: {rec_code}\n"
#         )

#         # --- Files ---
#         try:
#             copy_and_relabel_files(ligase, pdb_id, old_lig, new_lig)
#             log.write("  ✔ Files updated\n")
#         except Exception as e:
#             log.write(f"  ⚠ File update error: {e}\n")

#         # --- DB rewrites ---
#         try:
#             rewrite_in_db(conn, ligase, pdb_id, old_lig, new_lig, mw, rec_code)
#             log.write("  ✔ DB updated\n")
#         except Exception as e:
#             log.write(f"  ⚠ DB update error: {e}\n")

#         # --- SMILES fetch & metadata ---
#         try:
#             res = conn.execute(
#                 "SELECT SMILES FROM Ligase_Chemical_Descriptors WHERE RECRUITER_CODE = ?",
#                 (rec_code,),
#             ).fetchone()

#             # Fallback: Ligase_SMILE_Codes
#             if res is None:
#                 res = conn.execute(
#                     "SELECT SMILES FROM Ligase_SMILE_Codes WHERE RECRUITER_CODE = ?",
#                     (rec_code,),
#                 ).fetchone()

#             if res is None:
#                 log.write("  ⚠ No SMILES found in ANY table!\n")
#             else:
#                 smiles = res[0]
#                 insert_metadata(conn, new_lig, smiles)
#                 log.write("  ✔ Metadata inserted\n")

#         except Exception as e:
#             log.write(f"  ⚠ Metadata insert error: {e}\n")

#     conn.commit()
#     conn.close()
#     log.close()

#     print("\n🎉 DONE — All ligands rewritten safely!")
#     print("  ✔ Log file: ligand_rewrite.log")
#     print("  ✔ Mapping:  ligand_rewrite_map.csv")


# if __name__ == "__main__":
#     main()



# # import sqlite3
# # import pandas as pd
# # import os
# # import glob

# # DB_PATH = "Ligases/Ligase_Recruiter.db"
# # BASE = "Ligases"


# # def show_copy_preview(src_file, old_lig, new_lig):
# #     """Show how a filename would change."""
# #     fname = os.path.basename(src_file)

# #     if old_lig not in fname:
# #         print("       ⚠ Could not detect ligand code in filename:", fname)
# #         return

# #     new_fname = fname.replace(old_lig, new_lig, 1)

# #     print(f"       {fname}  →  {new_fname}")


# # def main():
# #     df = pd.read_csv("ligand_rewrite_map.csv")
# #     df.columns = [c.lower() for c in df.columns]

# #     print("\n==============================")
# #     print(" 🚫 DRY RUN — NO CHANGES MADE ")
# #     print("==============================\n")

# #     for i, row in df.iterrows():
# #         ligase = row["ligase"]
# #         pdb_id = row["pdb_id"]
# #         old_lig = row["ligand"]
# #         new_lig = row["new_ligand"]
# #         mw = row["mw"]
# #         rec = row["recruiter_code"]

# #         print(f"\n[{i+1}] Would update ligand: {old_lig} → {new_lig}")
# #         print(f"     Ligase: {ligase}")
# #         print(f"     PDB:    {pdb_id}")
# #         print(f"     MW:     {mw}")
# #         print(f"     RCODE:  {rec}")

# #         lig_dir = os.path.join(BASE, ligase)

# #         # ==========================
# #         # 🔍 PDB FILES
# #         # ==========================
# #         pdb_glob = glob.glob(os.path.join(lig_dir, "PDB", f"{pdb_id}_{old_lig}*.pdb"))
# #         for f in pdb_glob:
# #             print("       PDB rename:")
# #             show_copy_preview(f, old_lig, new_lig)

# #         # ==========================
# #         # 🔍 SDF_4Download
# #         # ==========================
# #         sdf_dl_glob = glob.glob(os.path.join(lig_dir, "SDF_4Download", f"{pdb_id}_{old_lig}*.sdf"))
# #         for f in sdf_dl_glob:
# #             print("       SDF_4Download copy:")
# #             show_copy_preview(f, old_lig, new_lig)

# #         # ==========================
# #         # 🔍 Ligand-level SDF
# #         # ==========================
# #         lig_sdf_glob = glob.glob(os.path.join(lig_dir, "SDF", f"{ligase}_{old_lig}*.sdf"))
# #         for f in lig_sdf_glob:
# #             print("       Ligand SDF copy:")
# #             show_copy_preview(f, old_lig, new_lig)

# #         # ==========================
# #         # 🔍 DATABASE COUNTS
# #         # ==========================
# #         print("     DB rows that *would* be updated:")

# #         conn = sqlite3.connect(DB_PATH)
# #         cur = conn.cursor()

# #         # SASA atoms
# #         n1 = cur.execute("""
# #             SELECT COUNT(*) FROM Ligase_Ligand_SASA_atoms
# #             WHERE Ligase=? AND pdb_id=? AND Ligand=? AND MW=?
# #         """, (ligase, pdb_id, old_lig, mw)).fetchone()[0]
# #         print(f"       SASA_atoms: {n1} rows")

# #         # SASA summary
# #         n2 = cur.execute("""
# #             SELECT COUNT(*) FROM Ligase_Ligand_SASA_summary
# #             WHERE Ligase=? AND pdb_id=? AND Ligand=? AND MW=?
# #         """, (ligase, pdb_id, old_lig, mw)).fetchone()[0]
# #         print(f"       SASA_summary: {n2} rows")

# #         # 3D mapped
# #         n3 = cur.execute("""
# #             SELECT COUNT(*) FROM Ligase_Ligands_Smiles_3DMapped
# #             WHERE Ligase=? AND pdb_id=? AND Ligand=? AND RECRUITER_CODE=?
# #         """, (ligase, pdb_id, old_lig, rec)).fetchone()[0]
# #         print(f"       Smiles_3DMapped: {n3} rows")

# #         conn.close()

# #     print("\n==============================")
# #     print("  DRY RUN COMPLETE — NOTHING WAS MODIFIED")
# #     print("==============================\n")


# # if __name__ == "__main__":
# #     main()


#!/usr/bin/env python3
# import sqlite3
# import pandas as pd

# DB = "Ligases/Ligase_Recruiter.db"
# MAP = "ligand_rewrite_map.csv"

# df = pd.read_csv(MAP)

# conn = sqlite3.connect(DB)
# cur = conn.cursor()

# print("🔍 DRY RUN — Nothing will be deleted\n")

# for _, row in df.iterrows():
#     old = row["Ligand"]
#     new = row["new_ligand"]
#     ligase = row["Ligase"]
#     pdb = row["PDB_ID"]

#     print(f"\n=== {ligase} {pdb} : {old} → {new} ===")

#     # 3DMapped check
#     cur.execute("""
#         SELECT COUNT(*) FROM Ligase_Ligands_Smiles_3DMapped
#         WHERE Ligase=? AND pdb_id=? AND Ligand=?
#     """, (ligase, pdb, old))
#     cnt_map = cur.fetchone()[0]
#     print(f"  3DMapped rows to delete: {cnt_map}")

#     # SASA atoms
#     cur.execute("""
#         SELECT COUNT(*) FROM Ligase_Ligand_SASA_atoms
#         WHERE Ligase=? AND pdb_id=? AND Ligand=?
#     """, (ligase, pdb, old))
#     cnt_atoms = cur.fetchone()[0]
#     print(f"  SASA atom rows to delete: {cnt_atoms}")

#     # SASA summary
#     cur.execute("""
#         SELECT COUNT(*) FROM Ligase_Ligand_SASA_summary
#         WHERE Ligase=? AND pdb_id=? AND Ligand=?
#     """, (ligase, pdb, old))
#     cnt_sum = cur.fetchone()[0]
#     print(f"  SASA summary rows to delete: {cnt_sum}")

# conn.close()





# #!/usr/bin/env python3
# import sqlite3
# import pandas as pd

# DB = "Ligases/Ligase_Recruiter.db"
# MAP = "ligand_rewrite_map.csv"
# df = pd.read_csv(MAP)

# conn = sqlite3.connect(DB)
# cur = conn.cursor()

# deleted_map = deleted_atoms = deleted_summary = 0

# for _, row in df.iterrows():
#     old = row["Ligand"]
#     ligase = row["Ligase"]
#     pdb = row["PDB_ID"]

#     cur.execute("""
#         DELETE FROM Ligase_Ligands_Smiles_3DMapped
#         WHERE Ligase=? AND pdb_id=? AND Ligand=?
#     """, (ligase, pdb, old))
#     deleted_map += cur.rowcount

#     cur.execute("""
#         DELETE FROM Ligase_Ligand_SASA_atoms
#         WHERE Ligase=? AND pdb_id=? AND Ligand=?
#     """, (ligase, pdb, old))
#     deleted_atoms += cur.rowcount

#     cur.execute("""
#         DELETE FROM Ligase_Ligand_SASA_summary
#         WHERE Ligase=? AND pdb_id=? AND Ligand=?
#     """, (ligase, pdb, old))
#     deleted_summary += cur.rowcount

# conn.commit()
# conn.close()

# print("🗑️ DELETE COMPLETED")
# print("  3DMapped rows removed:", deleted_map)
# print("  SASA atom rows removed:", deleted_atoms)
# print("  SASA summary rows removed:", deleted_summary)




#!/usr/bin/env python3
import sqlite3
import csv
import argparse
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# ===============================================================
# CONFIG
# ===============================================================
DB_PATH = "Ligases/Ligase_Recruiter.db"
TABLE_NAME = "Ligase_Ligands_Smiles_3DMapped"
LIGAND_COL = "Ligand"
RECRUITER_COL = "RECRUITER_CODE"

OUTPUT_PREFIX = "duplicate_master_fullmap_UPDATED"

# ===============================================================
# Load all recruiter → ligand mappings from the DB
# ===============================================================
def load_recruiter_ligands():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute(f"""
        SELECT DISTINCT {RECRUITER_COL} AS recruiter,
                        {LIGAND_COL} AS ligand
        FROM {TABLE_NAME};
    """).fetchall()

    conn.close()
    return [(row["recruiter"], row["ligand"]) for row in rows]


# ===============================================================
# Build clusters:
#   ligand → list of recruiters
# ===============================================================
def build_ligand_clusters(pairs):
    clusters = defaultdict(list)

    for recruiter, ligand in pairs:
        ligand = ligand.strip().upper()
        recruiter = recruiter.strip().upper()

        clusters[ligand].append(recruiter)

    return clusters


# ===============================================================
# Decide master recruiter for each ligand cluster
# Rule:
#   - If an L000XX recruiter is present, use that as master
#   - Else use the FIRST recruiter alphabetically
# ===============================================================
def choose_master(recruiters):
    recruiters_sorted = sorted(recruiters)

    # Prefer the original L000XX master if present
    for r in recruiters_sorted:
        if r.startswith("L000"):
            return r

    # Otherwise choose the smallest recruiter code
    return recruiters_sorted[0]


# ===============================================================
# Write final CSV
# ===============================================================
def write_output(clusters, dry_run=False):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_path = f"{OUTPUT_PREFIX}_{timestamp}.csv"

    rows = []

    for ligand, recruiters in sorted(clusters.items()):
        master = choose_master(recruiters)
        recruiter_list = ",".join(sorted(recruiters))

        rows.append([ligand, recruiter_list, master])

    if dry_run:
        print("\n🔍 DRY RUN — WOULD WRITE THIS FILE:")
        print(out_path)
        print("\nShowing first 20 rows:\n")
        for r in rows[:20]:
            print(",".join(r))
        print(f"\nTotal ligand clusters: {len(rows)}")
        return

    # Write CSV
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Ligand", "Recruiters", "MasterRecruiter"])
        writer.writerows(rows)

    print(f"\n✅ Wrote new master cluster file:\n{out_path}")
    print(f"Total ligand clusters: {len(rows)}")


# ===============================================================
# Main
# ===============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Rebuild master recruiter map using updated ligand assignments"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview output without writing file")

    args = parser.parse_args()

    print("📌 Loading recruiter → ligand mapping from DB...")
    pairs = load_recruiter_ligands()
    print(f"   Loaded {len(pairs)} recruiter entries")

    print("\n📦 Building ligand clusters...")
    clusters = build_ligand_clusters(pairs)
    print(f"   Found {len(clusters)} unique ligands")

    print("\n🏷️ Determining master recruiters...")
    write_output(clusters, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
