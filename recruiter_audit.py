# # import sqlite3
# # import os
# # import csv


# # DB_PATH = "Ligases/Ligase_Recruiter.db"   # <-- CHANGE if needed
# # OUTPUT_CSV = "Incomplete_Recruiters.csv"


# # def query_all(db, query, params=()):
# #     cur = db.execute(query, params)
# #     cols = [c[0] for c in cur.description]
# #     return [dict(zip(cols, row)) for row in cur.fetchall()]


# # def main():
# #     print("🔍 Auditing recruiter dataset...")

# #     db = sqlite3.connect(DB_PATH)

# #     # Get ALL recruiters from mapping table
# #     recruiters = query_all(db, """
# #         SELECT RECRUITER_CODE, Ligase, pdb_id, Ligand, Variant
# #         FROM Ligase_Ligands_Smiles_3DMapped
# #     """)

# #     incomplete = []

# #     for r in recruiters:
# #         code    = r["RECRUITER_CODE"]
# #         ligase  = r["Ligase"]
# #         pdb_id  = r["pdb_id"]
# #         ligand  = r["Ligand"]
# #         variant = r["Variant"]

# #         # --- CHECK 1 : Composite key exists in mapping table (always true here)
# #         composite_ok = "YES"

# #         # --- CHECK 2 : SASA summary exists
# #         sasa_summary = query_all(db, """
# #             SELECT 1
# #             FROM Ligase_Ligand_SASA_summary
# #             WHERE Ligase=? AND pdb_id=? AND Ligand=?
# #               AND (Variant=? OR Variant IS NULL)
# #             LIMIT 1;
# #         """, [ligase, pdb_id, ligand, variant])
# #         sasa_summary_ok = "YES" if sasa_summary else "NO"

# #         # --- CHECK 3 : Atom-level SASA exists
# #         sasa_atoms = query_all(db, """
# #             SELECT 1
# #             FROM Ligase_Ligand_SASA_atoms
# #             WHERE Ligase=? AND pdb_id=? AND Ligand=?
# #               AND (Variant=? OR Variant IS NULL)
# #             LIMIT 1;
# #         """, [ligase, pdb_id, ligand, variant])
# #         sasa_atoms_ok = "YES" if sasa_atoms else "NO"

# #         # --- CHECK 4 : PDB file exists
# #         pdb_main = os.path.join("Ligases", ligase, "PDB", f"{pdb_id}_{ligand}.pdb")
# #         pdb_alt  = os.path.join("Ligases", ligase, "PDB", f"{pdb_id}_{ligand}_1.pdb")
# #         pdb_ok = "YES" if (os.path.exists(pdb_main) or os.path.exists(pdb_alt)) else "NO"

# #         # Do we keep this row?
# #         failures = [sasa_summary_ok, sasa_atoms_ok, pdb_ok]
# #         failed_any = "NO" if all(x == "YES" for x in failures) else "YES"

# #         if failed_any == "YES":
# #             incomplete.append({
# #                 "RECRUITER_CODE": code,
# #                 "Missing_CompositeKey": "NO" if composite_ok == "YES" else "YES",
# #                 "Missing_SASA_Summary": "YES" if sasa_summary_ok == "NO" else "NO",
# #                 "Missing_SASA_Atoms": "YES" if sasa_atoms_ok == "NO" else "NO",
# #                 "Missing_PDB": "YES" if pdb_ok == "NO" else "NO",
# #                 "Any_Failure": failed_any
# #             })

# #     # --- Write CSV ---
# #     with open(OUTPUT_CSV, "w", newline="") as f:
# #         writer = csv.DictWriter(f, fieldnames=[
# #             "RECRUITER_CODE",
# #             "Missing_CompositeKey",
# #             "Missing_SASA_Summary",
# #             "Missing_SASA_Atoms",
# #             "Missing_PDB",
# #             "Any_Failure"
# #         ])
# #         writer.writeheader()
# #         writer.writerows(incomplete)

# #     print(f"✅ Done. Found {len(incomplete)} incomplete recruiters.")
# #     print(f"📄 Output saved → {OUTPUT_CSV}")


# # if __name__ == "__main__":
# #     main()



# import pandas as pd

# # Input/output filenames
# INPUT = "Incomplete_Recruiters.csv"
# OUTPUT = "Incomplete_Recruiters_deduped.csv"

# print("🔄 Loading CSV...")
# df = pd.read_csv(INPUT)

# print(f"📦 Original rows: {len(df)}")

# # Ensure recruiter column is named correctly
# # Rename automatically if needed
# for col in df.columns:
#     if "RECRUITER" in col.upper():
#         recruiter_col = col
#         break
# else:
#     raise ValueError("❌ Recruiter code column not found.")

# print(f"🔑 Using recruiter column: {recruiter_col}")

# # Drop duplicates based on recruiter code
# df_dedup = df.drop_duplicates(subset=[recruiter_col], keep="first")

# print(f"✨ Deduplicated rows: {len(df_dedup)}")

# # Save cleaned version
# df_dedup.to_csv(OUTPUT, index=False)

# print(f"✅ Saved cleaned file → {OUTPUT}")

import pandas as pd

INPUT = "Incomplete_Recruiters_deduped.csv"
OUTPUT = "Excluded_Recruiters.txt"

print("🔄 Loading CSV...")
df = pd.read_csv(INPUT)

# Detect recruiter column automatically
for col in df.columns:
    if "RECRUITER" in col.upper():
        recruiter_col = col
        break
else:
    raise ValueError("❌ Recruiter code column not found.")

print(f"🔑 Extracting column: {recruiter_col}")

# Extract recruiter codes as list
codes = df[recruiter_col].dropna().astype(str).tolist()

print(f"📦 Found {len(codes)} recruiter codes")

# Create comma-separated string
line = ",".join(codes)

# Write to file
with open(OUTPUT, "w") as f:
    f.write(line)

print(f"✅ Wrote comma-separated recruiter list → {OUTPUT}")
