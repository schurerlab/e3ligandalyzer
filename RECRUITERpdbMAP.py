import sqlite3
import csv
import json
import os

BASE_DIR = os.environ.get("E3_LIGASES_DIR", os.path.join(os.getcwd(), "Ligases"))
DB_PATH = os.path.join(BASE_DIR, "Ligase_Recruiter.db")

OUTPUT_CSV = "recruiter_pdb_map.csv"
OUTPUT_JSON = "recruiter_pdb_map.json"
OUTPUT_MISSING_RECRUITER = "missing_pdb_for_recruiter.txt"
OUTPUT_ORPHAN_PDBS = "unmatched_pdb_files.txt"


def find_matching_pdb(ligase, pdb_id, ligand, variant):
    pdb_folder = os.path.join(BASE_DIR, ligase, "PDB")
    if not os.path.isdir(pdb_folder):
        return None

    candidates = []

    if variant not in (None, "", 0):
        candidates.append(f"{pdb_id}_{ligand}_{variant}.pdb")

    candidates.append(f"{pdb_id}_{ligand}.pdb")

    for filename in candidates:
        full_path = os.path.join(pdb_folder, filename)
        if os.path.isfile(full_path):
            return filename

    return None


def list_all_pdb_files():
    """Scan filesystem for all PDB files."""
    all_pdbs = {}
    for ligase in os.listdir(BASE_DIR):
        lig_dir = os.path.join(BASE_DIR, ligase, "PDB")
        if not os.path.isdir(lig_dir):
            continue
        for file in os.listdir(lig_dir):
            if file.lower().endswith(".pdb"):
                full_path = os.path.join(lig_dir, file)
                all_pdbs.setdefault(ligase, []).append(file)
    return all_pdbs


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = """
    SELECT DISTINCT RECRUITER_CODE, Ligase, pdb_id, Ligand, Variant
    FROM Ligase_Ligands_Smiles_3DMapped
    ORDER BY RECRUITER_CODE;
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    csv_rows = []
    json_map = {}

    missing_pdb_for_recruiter = []
    recruiter_mapped_files = set()

    # ---- Check A: Recruiter → PDB mapping ----
    for recruiter_code, ligase, pdb_id, ligand, variant in rows:

        pdb_name = find_matching_pdb(ligase, pdb_id, ligand, variant)

        if pdb_name is None:
            missing_pdb_for_recruiter.append(
                f"{recruiter_code}  ({ligase}  {pdb_id}  {ligand}  variant={variant})"
            )
        else:
            recruiter_mapped_files.add((ligase, pdb_name))

        csv_rows.append({
            "RECRUITER_CODE": recruiter_code,
            "Ligase": ligase,
            "PDB_ID": pdb_id,
            "Ligand": ligand,
            "Variant": variant,
            "PDB_File": pdb_name if pdb_name else "NOT_FOUND"
        })

        json_map[recruiter_code] = {
            "ligase": ligase,
            "pdb_id": pdb_id,
            "ligand": ligand,
            "variant": variant,
            "pdb_file": pdb_name,
            "absolute_path": (
                os.path.join(BASE_DIR, ligase, "PDB", pdb_name)
                if pdb_name else None
            )
        }

    # ---- Write CSV ----
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["RECRUITER_CODE", "Ligase", "PDB_ID", "Ligand", "Variant", "PDB_File"]
        )
        writer.writeheader()
        writer.writerows(csv_rows)

    # ---- Write JSON ----
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(json_map, f, indent=4)

    # ---- Check B: PDB → Recruiter mapping ----
    all_pdb_files = list_all_pdb_files()

    orphan_pdbs = []

    for ligase, file_list in all_pdb_files.items():
        for file in file_list:
            if (ligase, file) not in recruiter_mapped_files:
                orphan_pdbs.append(f"{ligase}/{file}")

    # ---- Write Missing Recruiter PDB file list ----
    with open(OUTPUT_MISSING_RECRUITER, "w") as f:
        if missing_pdb_for_recruiter:
            f.write("Recruiter codes with missing PDB files:\n")
            for line in missing_pdb_for_recruiter:
                f.write(line + "\n")
        else:
            f.write("All recruiter codes have corresponding PDB files.\n")

    # ---- Write Orphan PDB files ----
    with open(OUTPUT_ORPHAN_PDBS, "w") as f:
        if orphan_pdbs:
            f.write("PDB files that are NOT referenced by any recruiter code:\n")
            for p in orphan_pdbs:
                f.write(p + "\n")
        else:
            f.write("All PDB files are used by recruiter codes.\n")

    print("CSV written →", OUTPUT_CSV)
    print("JSON written →", OUTPUT_JSON)
    print("Missing recruiter PDB list →", OUTPUT_MISSING_RECRUITER)
    print("Orphan PDB file list →", OUTPUT_ORPHAN_PDBS)
    print("\nDone.")


if __name__ == "__main__":
    main()
