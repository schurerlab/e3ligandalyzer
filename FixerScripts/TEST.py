# from Ligases.routes import query_db
# rows = query_db("""
# SELECT a.Ligase,a.pdb_id,a.Ligand,a.atom_id,a.x,a.y,a.z,a.Exposure_A2
# FROM Ligase_Ligand_SASA_atoms a
# JOIN Ligase_Ligands_Smiles_3DMapped m
#   ON a.Ligase=m.Ligase AND a.Ligand=m.Ligand AND a.atom_id=m.atom_id
# WHERE m.RECRUITER_CODE='L00896' LIMIT 5;
# """)
# print(len(rows), [dict(r) for r in rows[:2]])


# import os
# import csv
# import shutil

# def move_multiligand_from_csv(csv_path, base_dir):
#     retired_dir = os.path.join(base_dir, "RetiredPDBs")
#     os.makedirs(retired_dir, exist_ok=True)

#     with open(csv_path, "r", encoding="utf-8") as f:
#         reader = csv.DictReader(f)
#         moved = 0

#         for row in reader:
#             ligase = row["Ligase"]
#             pdb_file = row["PDB_File"]
#             unique_count = int(row["Unique_Residues"])

#             if unique_count > 1:
#                 # Locate the file
#                 pdb_path = os.path.join(base_dir, ligase, "PDB", pdb_file)
#                 if not os.path.exists(pdb_path):
#                     print(f"⚠️  Not found: {pdb_path}")
#                     continue

#                 # New name + destination
#                 new_name = f"{ligase}_{pdb_file}"
#                 dest_path = os.path.join(retired_dir, new_name)

#                 # Copy instead of move first (safety)
#                 shutil.move(pdb_path, dest_path)

#                 moved += 1
#                 print(f"🚫 {pdb_file} → moved to RetiredPDBs as {new_name}")

#     print(f"\n✅ Finished — {moved} PDBs moved to RetiredPDBs.")

# if __name__ == "__main__":
#     base_dir = r"C:\Users\joeys\Documents\WorkingViralDB\Ligases\MODULE\e3-ligase-atlas-explorer\Ligases"
#     csv_path = os.path.join(
#         r"C:\Users\joeys\Documents\WorkingViralDB\Ligases\MODULE\e3-ligase-atlas-explorer",
#         "ligand_unique_counts.csv"
#     )

#     move_multiligand_from_csv(csv_path, base_dir)


import os
import shutil

def move_unclean_duplicates(base_dir, backup_dir_name="ExtraPDBS"):
    """
    Move unclean PDB files (e.g., 9F1M_A1H.pdb) into a backup folder if a
    cleaned version (9F1M_A1H_1.pdb) exists in the same directory.

    Moved files are renamed to include their ligase prefix, e.g.:
        Ligases/VHL/PDB/9F1M_A1H.pdb → ExtraPDBS/VHL_9F1M_A1H.pdb
    """

    # Create backup folder if it doesn't exist
    backup_dir = os.path.join(base_dir, backup_dir_name)
    os.makedirs(backup_dir, exist_ok=True)

    moved = 0
    skipped = 0

    for root, _, files in os.walk(base_dir):
        pdb_files = [f for f in files if f.lower().endswith(".pdb")]

        # Find all cleaned "_1.pdb" bases
        clean_bases = {f[:-6] for f in pdb_files if f.endswith("_1.pdb")}

        # Infer ligase name from folder path
        parts = root.split(os.sep)
        ligase = None
        for p in reversed(parts):
            if p.upper() not in {"PDB", "LIGASES", "MODULE"}:
                ligase = p
                break

        if not ligase:
            continue

        for f in pdb_files:
            # Skip cleaned files
            if f.endswith("_1.pdb"):
                continue

            # Check if a cleaned version exists
            base_name = f[:-4]
            if base_name in clean_bases:
                src = os.path.join(root, f)
                new_name = f"{ligase}_{f}"
                dest = os.path.join(backup_dir, new_name)

                try:
                    shutil.move(src, dest)
                    moved += 1
                    print(f"📦 Moved {src} → {dest}")
                except Exception as e:
                    print(f"⚠️ Failed to move {src}: {e}")
            else:
                skipped += 1

    print(f"\n✅ Cleanup complete — {moved} unclean PDBs moved to '{backup_dir_name}', {skipped} skipped.")

if __name__ == "__main__":
    base_dir = r"/mnt/c/Users/joeys/Documents/WorkingViralDB/Ligases/MODULE/e3-ligase-atlas-explorer/Ligases"
    move_unclean_duplicates(base_dir)
