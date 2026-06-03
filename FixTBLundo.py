import sqlite3
import pandas as pd
import os
import shutil
import glob

DB_PATH = "Ligases/Ligase_Recruiter.db"
BASE = "Ligases"


def undo_file_changes(ligase, pdb_id, old_lig, new_lig):
    lig_dir = os.path.join(BASE, ligase)

    # ========== PDB ==========
    pattern = os.path.join(lig_dir, "PDB", f"{pdb_id}_{new_lig}*.pdb")
    for f in glob.glob(pattern):
        new_name = os.path.basename(f)
        suffix = new_name.split(new_lig, 1)[1]
        old_dest = os.path.join(lig_dir, "PDB", f"{pdb_id}_{old_lig}{suffix}")

        with open(f, "r") as fh:
            text = fh.read().replace(f" {new_lig} ", f" {old_lig} ")

        with open(old_dest, "w") as fh:
            fh.write(text)

        print("  Restored PDB:", new_name, "→", os.path.basename(old_dest))

    # ========== SDF_4Download ==========
    pattern = os.path.join(lig_dir, "SDF_4Download", f"{pdb_id}_{new_lig}*.sdf")
    for f in glob.glob(pattern):
        new_name = os.path.basename(f)
        suffix = new_name.split(new_lig, 1)[1]
        old_dest = os.path.join(lig_dir, "SDF_4Download", f"{pdb_id}_{old_lig}{suffix}")
        shutil.copy2(f, old_dest)
        print("  Restored SDF_4Download:", new_name, "→", os.path.basename(old_dest))

    # ========== Ligand-level SDF ==========
    pattern = os.path.join(lig_dir, "SDF", f"{ligase}_{new_lig}*.sdf")
    for f in glob.glob(pattern):
        new_name = os.path.basename(f)
        suffix = new_name.split(new_lig, 1)[1]
        old_dest = os.path.join(lig_dir, "SDF", f"{ligase}_{old_lig}{suffix}")
        shutil.copy2(f, old_dest)
        print("  Restored SDF:", new_name, "→", os.path.basename(old_dest))


def undo_db_updates(conn, ligase, pdb_id, old_lig, new_lig, mw, rec_code):
    cur = conn.cursor()

    # reverse SASA_atoms
    cur.execute("""
        UPDATE Ligase_Ligand_SASA_atoms
        SET Ligand = ?
        WHERE Ligase=? AND pdb_id=? AND Ligand=? AND MW=?
    """, (old_lig, ligase, pdb_id, new_lig, mw))

    # reverse SASA_summary
    cur.execute("""
        UPDATE Ligase_Ligand_SASA_summary
        SET Ligand = ?
        WHERE Ligase=? AND pdb_id=? AND Ligand=? AND MW=?
    """, (old_lig, ligase, pdb_id, new_lig, mw))

    # reverse 3D mapped
    cur.execute("""
        UPDATE Ligase_Ligands_Smiles_3DMapped
        SET Ligand = ?
        WHERE Ligase=? AND pdb_id=? AND Ligand=? AND RECRUITER_CODE=?
    """, (old_lig, ligase, pdb_id, new_lig, rec_code))

    # delete metadata entry
    cur.execute("""
        DELETE FROM Ligase_Ligand_Metadata
        WHERE Ligand = ?
    """, (new_lig,))

    print("  DB restored for:", old_lig)


def main():
    df = pd.read_csv("ligand_rewrite_map.csv")
    df.columns = [c.lower() for c in df.columns]

    print("\n===================================")
    print(" 🔄 RESTORE MODE — UNDOING CHANGES")
    print("===================================\n")

    conn = sqlite3.connect(DB_PATH)

    for i, row in df.iterrows():
        ligase = row["ligase"]
        pdb_id = row["pdb_id"]
        old_lig = row["ligand"]
        new_lig = row["new_ligand"]
        mw = row["mw"]
        rec_code = row["recruiter_code"]

        print(f"\n[{i+1}] Restoring: {new_lig} → {old_lig} ({ligase}/{pdb_id})")

        undo_file_changes(ligase, pdb_id, old_lig, new_lig)
        undo_db_updates(conn, ligase, pdb_id, old_lig, new_lig, mw, rec_code)

    conn.commit()
    conn.close()

    print("\n===================================")
    print(" ✅ RESTORE COMPLETE")
    print("===================================\n")


if __name__ == "__main__":
    main()
