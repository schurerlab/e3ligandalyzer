# import sqlite3
# import csv

# DB_PATH = "Ligases/Ligase_Recruiter.db"        # ← update path if needed
# OUTPUT_CSV = "fully_exposed_ligands.csv"

# def export_fully_exposed():
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     cur = conn.cursor()

#     print("📘 Connected to database:", DB_PATH)

#     query = """
#         SELECT 
#             Ligase,
#             pdb_id,
#             Ligand,
#             Residue_ID,
#             Variant,
#             MW,
#             Recruiter_Class,
#             Total_atoms,
#             Exposed_atoms,
#             SASA_in_complex_A2,
#             "%Exposed",
#             "%Buried"
#         FROM Ligase_Ligand_SASA_summary
#         WHERE "%Exposed" = 1
#         ORDER BY Ligase, pdb_id, Ligand;
#     """

#     rows = cur.execute(query).fetchall()

#     print(f"🔍 Found {len(rows)} ligands with %Exposed = 1")

#     if not rows:
#         print("⚠️ No fully-exposed ligands found. Nothing to write.")
#         return

#     with open(OUTPUT_CSV, "w", newline="") as csvfile:
#         writer = csv.writer(csvfile)

#         # header
#         writer.writerow([
#             "Ligase",
#             "pdb_id",
#             "Ligand",
#             "Residue_ID",
#             "Variant",
#             "MW",
#             "Recruiter_Class",
#             "Total_atoms",
#             "Exposed_atoms",
#             "SASA_in_complex_A2",
#             "%Exposed",
#             "%Buried"
#         ])

#         # rows
#         for r in rows:
#             writer.writerow([
#                 r["Ligase"],
#                 r["pdb_id"],
#                 r["Ligand"],
#                 r["Residue_ID"],
#                 r["Variant"],
#                 r["MW"],
#                 r["Recruiter_Class"],
#                 r["Total_atoms"],
#                 r["Exposed_atoms"],
#                 r["SASA_in_complex_A2"],
#                 r["%Exposed"],
#                 r["%Buried"]
#             ])

#     print(f"✅ CSV written: {OUTPUT_CSV}")


# if __name__ == "__main__":
#     export_fully_exposed()

import os
import csv
import shutil

CSV_PATH = "fully_exposed_ligands.csv"
BASE_DIR = "Ligases"
OUTPUT_DIR = "Final_Artifacts"

MOVE_FILES = True  # True = move, False = copy


def resolve_pdb_path(ligase, pdb_id, ligand, variant):
    """
    Return the actual path to the correct PDB file:
    - Check for "<pdb>_<ligand>_<variant>.pdb"
    - Fallback to "<pdb>_<ligand>.pdb"
    """
    lig_dir = os.path.join(BASE_DIR, ligase, "PDB")

    variant_file = f"{pdb_id}_{ligand}_{variant}.pdb"
    variantless_file = f"{pdb_id}_{ligand}.pdb"

    variant_path = os.path.join(lig_dir, variant_file)
    variantless_path = os.path.join(lig_dir, variantless_file)

    # 1. Expected variant file exists
    if os.path.exists(variant_path):
        return variant_path, variant_file

    # 2. Missing expected → fallback if variantless exists
    if os.path.exists(variantless_path):
        return variantless_path, variantless_file

    # 3. Nothing found
    return None, None


def move_artifacts():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    moved = 0
    missing = 0

    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            ligase = row["Ligase"]
            pdb_id = row["pdb_id"]
            ligand = row["Ligand"]
            variant = row["Variant"].strip()

            path, original_name = resolve_pdb_path(ligase, pdb_id, ligand, variant)

            if path is None:
                print(f"❌ Missing file for {ligase} {pdb_id} {ligand} (variant {variant})")
                missing += 1
                continue

            # Always rename to a cleaned standardized format
            final_name = f"{ligase}_{pdb_id}_{ligand}_{variant}.pdb"
            dest = os.path.join(OUTPUT_DIR, final_name)

            if MOVE_FILES:
                shutil.move(path, dest)
                action = "Moved"
            else:
                shutil.copy2(path, dest)
                action = "Copied"

            print(f"📦 {action}: {original_name} → {dest}")
            moved += 1

    print("\n============== SUMMARY ===============")
    print(f"📦 Files moved/copied: {moved}")
    print(f"❓ Missing files:       {missing}")
    print(f"📂 Output folder:       {OUTPUT_DIR}")
    print("=======================================")


if __name__ == "__main__":
    move_artifacts()
