import sqlite3
import csv
import argparse
from pathlib import Path

DB_PATH = "Ligases/Ligase_Recruiter.db"

RESTORE_MAP = {
    "updated_Ligase_Ligand_SASA_atoms.csv": {
        "table": "Ligase_Ligand_SASA_atoms",
        "key": ["Ligase", "pdb_id", "Ligand", "Variant", "atom_id"],
    },
    "updated_Ligase_Ligand_SASA_summary.csv": {
        "table": "Ligase_Ligand_SASA_summary",
        "key": ["Ligase", "pdb_id", "Ligand", "Variant"],
    },
    "updated_Ligase_Ligands_Smiles_3DMapped.csv": {
        "table": "Ligase_Ligands_Smiles_3DMapped",
        "key": ["Ligase", "pdb_id", "Ligand", "Variant", "atom_id"],
    },
    "updated_Ligase_SMILE_Codes_Atoms.csv": {
        "table": "Ligase_SMILE_Codes_Atoms",
        "key": ["RECRUITER_CODE", "smiles_atom_index"],
    },
    "Ligase_MISSING_Chemical_Descriptors.csv": {
        "table": "Ligase_Chemical_Descriptors",
        "key": ["RECRUITER_CODE", "SMILES"],
    },
}

def row_exists(cursor, table, key_cols, row):
    where = " AND ".join(f"{k} = ?" for k in key_cols)
    values = [row[k] for k in key_cols]
    sql = f"SELECT 1 FROM {table} WHERE {where} LIMIT 1"
    cursor.execute(sql, values)
    return cursor.fetchone() is not None

def restore_missing_rows(dry_run=False):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n🧪 DRY RUN MODE ENABLED\n" if dry_run else "\n🚀 LIVE INSERT MODE\n")

    for csv_file, cfg in RESTORE_MAP.items():
        path = Path(csv_file)
        if not path.exists():
            print(f"⚠ Skipping missing file: {csv_file}")
            continue

        table = cfg["table"]
        key_cols = cfg["key"]

        print(f"\n🔄 Processing → {table}")

        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames

            quoted_cols = [f'"{c}"' for c in cols]

            insert_sql = f"""
                INSERT INTO {table} ({",".join(quoted_cols)})
                VALUES ({",".join("?" * len(cols))})
            """


            inserted = 0
            skipped = 0

            for row in reader:
                if row_exists(cursor, table, key_cols, row):
                    skipped += 1
                    continue

                inserted += 1

                if not dry_run:
                    try:
                        cursor.execute(insert_sql, [row[c] for c in cols])
                    except Exception as e:
                        print(f"❌ Insert error in {table}: {e}")
                        print(row)

            if not dry_run:
                conn.commit()

            print(f"   ➕ Would insert: {inserted}" if dry_run else f"   ✔ Inserted: {inserted}")
            print(f"   ↪ Skipped existing: {skipped}")

    conn.close()

    if dry_run:
        print("\n🧠 Dry run complete — no changes made.\n")
    else:
        print("\n✅ Intelligent restore complete.\n")

# --------------------------------------------------
# CLI ENTRY
# --------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore missing DB rows safely.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview inserts without modifying the database"
    )
    args = parser.parse_args()

    restore_missing_rows(dry_run=args.dry_run)
