# import os
# import glob
# import sqlite3
# import pandas as pd
# from pymol import cmd

# # --- CONFIG ---
# DB_PATH = "Ligases/Ligase_Recruiter.db"
# BASE_DIR = os.getcwd()
# SESSION_NAME = "Fully_Exposed_Ligands.pse"

# # --- QUERY DATABASE ---
# conn = sqlite3.connect(DB_PATH)
# query = """
# SELECT Ligase, pdb_id, Ligand, Residue_ID, Variant, MW,
#        Recruiter_Class, Total_atoms, Exposed_atoms, SASA_in_complex_A2,
#        [%Exposed] AS ExposedPct, [%Buried] AS BuriedPct
# FROM Ligase_Ligand_SASA_summary
# WHERE CAST([%Exposed] AS REAL) >= 0.99
# ORDER BY Ligase, pdb_id;
# """
# df = pd.read_sql_query(query, conn)
# conn.close()

# df.to_csv("fully_exposed_ligands.csv", index=False)
# print(f"✅ Found {len(df)} fully exposed ligands. Exported to fully_exposed_ligands.csv\n")

# # --- SETUP PYMOL ---
# cmd.reinitialize()
# loaded_count = 0

# color_map = {
#     "Drug-like Recruiter": "green",
#     "Fragment Recruiter": "gray",
#     "Peptide-like Recruiter": "magenta"
# }

# # --- LOAD STRUCTURES ---
# for _, row in df.iterrows():
#     ligase = row["Ligase"]
#     pdb_id = row["pdb_id"]
#     ligand = row["Ligand"]
#     recruiter_class = row["Recruiter_Class"]

#     # Pattern for PDB file (with or without "_1" variant)
#     search_patterns = [
#         os.path.join(BASE_DIR, "Ligases", ligase, "PDB", f"{pdb_id}_{ligand}.pdb"),
#         os.path.join(BASE_DIR, "Ligases", ligase, "PDB", f"{pdb_id}_{ligand}_1.pdb"),
#         os.path.join(BASE_DIR, "Ligases", ligase, "PDB", f"{pdb_id}.pdb"),
#     ]

#     pdb_path = next((p for p in search_patterns if os.path.exists(p)), None)

#     if pdb_path:
#         obj_name = f"{ligase}_{pdb_id}_{ligand}"
#         cmd.load(pdb_path, obj_name)
#         cmd.hide("everything", obj_name)
#         cmd.show("sticks", obj_name)
#         color = color_map.get(recruiter_class, "cyan")
#         cmd.color(color, obj_name)
#         cmd.group(ligase, obj_name)
#         print(f"Loaded {obj_name} ({recruiter_class}) from {pdb_path}")
#         loaded_count += 1
#     else:
#         print(f"[⚠️] Missing PDB: {ligase}/{pdb_id}_{ligand}.pdb")

# cmd.bg_color("white")
# cmd.orient()
# cmd.save(SESSION_NAME)
# print(f"\n💾 Saved PyMOL session with {loaded_count} structures → {SESSION_NAME}")



import sqlite3
import pandas as pd

DB_PATH = "Ligases/Ligase_Recruiter.db"
conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON;")

# --- 1. Find fully exposed ligand–pdb pairs ---
fully_exposed = pd.read_sql_query("""
SELECT Ligase, pdb_id, Ligand
FROM Ligase_Ligand_SASA_summary
WHERE CAST([%Exposed] AS REAL) >= 0.99
""", conn)

if fully_exposed.empty:
    print("✅ No fully exposed ligands found.")
    conn.close()
    exit()

# --- 2. Map to recruiter codes via Ligase_Ligands_Smiles_3DMapped ---
query_codes = """
SELECT DISTINCT s.Ligase, s.pdb_id, s.Ligand, m.RECRUITER_CODE
FROM Ligase_Ligand_SASA_summary s
JOIN Ligase_Ligands_Smiles_3DMapped m
    ON s.Ligase = m.Ligase AND s.pdb_id = m.pdb_id AND s.Ligand = m.Ligand
WHERE CAST(s.[%Exposed] AS REAL) >= 0.99
"""
recruiter_df = pd.read_sql_query(query_codes, conn)

if recruiter_df.empty:
    print("⚠️ No recruiter codes linked to fully exposed ligands.")
    conn.close()
    exit()

recruiter_df.to_csv("deleted_fully_exposed_recruiters.csv", index=False)
recruiters_to_remove = tuple(recruiter_df["RECRUITER_CODE"].unique().tolist())
print(f"🧹 Found {len(recruiters_to_remove)} recruiter codes linked to fully exposed ligands.")

# --- 3. Delete safely across all related tables ---
try:
    conn.execute("BEGIN;")

    # recruiter-level tables
    recruiter_tables = [
        "Ligase_Chemical_Descriptors",
        "Ligase_Recruiters_Scaffold",
        "Ligase_SMILE_Codes",
        "Ligase_SMILE_Codes_Atoms",
    ]
    for table in recruiter_tables:
        q = f"DELETE FROM {table} WHERE RECRUITER_CODE IN ({','.join(['?']*len(recruiters_to_remove))});"
        conn.execute(q, recruiters_to_remove)
        print(f"Deleted from {table}")

    # ligand-level tables
    ligand_tables = [
        "Ligase_Ligand_SASA_atoms",
        "Ligase_Ligand_SASA_summary",
        "Ligase_Ligand_Metadata",
        "Ligase_Ligands_Smiles_3DMapped",
    ]
    for table in ligand_tables:
        q = """
        DELETE FROM {table}
        WHERE Ligand IN (
            SELECT Ligand FROM Ligase_Ligand_SASA_summary
            WHERE CAST([%Exposed] AS REAL) >= 0.99
        );
        """.format(table=table)
        conn.execute(q)
        print(f"Deleted from {table}")

    conn.commit()
    print("✅ Cleanup complete and committed.")

except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}\nRolled back all changes.")
finally:
    conn.close()
