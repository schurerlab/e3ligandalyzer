import os
import csv

BASE_DIR = "Ligases"
OUTPUT_CSV = "ligase_pdb_index.csv"

rows = []

for ligase in sorted(os.listdir(BASE_DIR)):
    ligase_path = os.path.join(BASE_DIR, ligase)

    # Only consider directories
    if not os.path.isdir(ligase_path):
        continue

    pdb_dir = os.path.join(ligase_path, "PDB")
    if not os.path.isdir(pdb_dir):
        continue

    for fname in sorted(os.listdir(pdb_dir)):
        if fname.lower().endswith(".pdb"):
            pdb_name = os.path.splitext(fname)[0]
            rows.append([ligase, pdb_name])

# Write CSV
with open(OUTPUT_CSV, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["ligase", "pdb_entry"])
    writer.writerows(rows)

print(f"✅ Wrote {len(rows)} entries to {OUTPUT_CSV}")
