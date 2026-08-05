# import os
# import csv
# from collections import defaultdict

# def count_unique_ligands(base_dir, output_csv="ligand_unique_counts.csv"):
#     results = []

#     for root, _, files in os.walk(base_dir):
#         for file in files:
#             if not file.lower().endswith(".pdb"):
#                 continue

#             pdb_path = os.path.join(root, file)
#             parts = root.split(os.sep)

#             # Try to infer ligase name robustly
#             ligase = "Unknown"
#             for p in reversed(parts):
#                 if p.upper() not in {"PDB", "LIGASES", "MODULE"}:
#                     ligase = p
#                     break

#             # 🧩 Map ligand → set of residue numbers
#             ligand_to_resnums = defaultdict(set)

#             try:
#                 with open(pdb_path, "r", encoding="utf-8", errors="ignore") as f:
#                     for line in f:
#                         if line.startswith("HETATM"):
#                             resname = line[17:20].strip()
#                             resnum = line[22:26].strip()
#                             if resname.upper() not in {"HOH", "NA", "CL", "K", "CA", "MG"}:
#                                 ligand_to_resnums[resname].add(resnum)
#             except Exception as e:
#                 print(f"⚠️ Error reading {pdb_path}: {e}")
#                 continue

#             # 🧮 Count unique residue IDs for each ligand
#             for ligand, resnums in ligand_to_resnums.items():
#                 results.append({
#                     "Ligase": ligase,
#                     "PDB_File": file,
#                     "Ligand": ligand,
#                     "Unique_Residues": len(resnums)
#                 })

#     print(f"✅ Found {len(results)} ligand entries total.")
#     if results:
#         with open(output_csv, "w", newline='', encoding="utf-8") as csvfile:
#             writer = csv.DictWriter(csvfile, fieldnames=["Ligase", "PDB_File", "Ligand", "Unique_Residues"])
#             writer.writeheader()
#             writer.writerows(results)
#         print(f"💾 Results written to {output_csv}")
#     else:
#         print("⚠️ No ligands detected.")


# if __name__ == "__main__":
#     base_dir = r"/path/to/e3-ligase-atlas-explorer/Ligases"
#     count_unique_ligands(base_dir)



# import sqlite3
# import json

# DB = "Ligases/Ligase_Recruiter.db"

# def fetch_one(cursor, query, params=()):
#     cursor.execute(query, params)
#     return cursor.fetchone()

# def fetch_all(cursor, query, params=()):
#     cursor.execute(query, params)
#     return cursor.fetchall()

# def check_recruiter(code):
#     conn = sqlite3.connect(DB)
#     conn.row_factory = sqlite3.Row
#     c = conn.cursor()

#     print("\n==============================")
#     print(f"🔎 Checking recruiter: {code}")
#     print("==============================")

#     # 1. Does recruiter appear anywhere?
#     rows = fetch_all(c, "SELECT * FROM Ligase_Ligand_SASA_summary WHERE RECRUITER_CLASS = ?", [code])
#     print(f"📌 In SASA summary: {len(rows)} rows")

#     # 2. Does scaffold table have it?
#     row = fetch_one(c,
#         "SELECT Scaffold_ID, Scaffold_SMILES FROM Ligase_Recruiters_Scaffold WHERE RECRUITER_CODE = ? LIMIT 5",
#         [code]
#     )
#     if row:
#         print(f"🧩 Scaffold found: {row['Scaffold_ID']}")
#     else:
#         print("❌ No scaffold for this recruiter (likely the source of your 404).")

#     # 3. Is this recruiter mapped via SMILES → recruiter?
#     rows = fetch_all(c,
#         "SELECT SMILES FROM Ligase_SMILE_Codes WHERE RECRUITER_CODE = ?",
#         [code]
#     )
#     print(f"🧬 SMILES mappings: {len(rows)}")

#     # 4. Check duplicates table
#     dup = fetch_one(c,
#         "SELECT Ligand, MATCHED_RECRUITERS FROM Ligase_Duplicate_Ligands WHERE MATCHED_RECRUITERS LIKE ?",
#         [f"%{code}%"]
#     )
#     if dup:
#         print(f"⚠️ Recruiter is a DUPLICATE of others: {dup['MATCHED_RECRUITERS']}")
#         print(f"🧲 Canonical ligand name: {dup['Ligand']}")
#     else:
#         print("👌 Not a known duplicate recruiter.")

#     # 5. Does a SMILE atom map exist?
#     rows = fetch_all(c,
#         "SELECT smile_atom FROM Ligase_SMILE_Codes_Atoms WHERE RECRUITER_CODE = ? LIMIT 3",
#         [code]
#     )
#     print(f"🧪 SMILES atom-level mappings: {len(rows)}")

#     conn.close()


# if __name__ == "__main__":
#     # Add recruiters you want to test
#     test_codes = ["L00440", "L00167", "L00003"]

#     for code in test_codes:
#         check_recruiter(code)


# import sqlite3
# import csv

# DB = "Ligases/Ligase_Recruiter.db"
# OUT = "duplicate_master_fullmap.csv"


# def parse_recruiters(text):
#     """Parse comma-separated recruiter codes."""
#     return [x.strip() for x in text.split(",") if x.strip()]


# def recruiter_has_scaffold(conn, recruiter):
#     """Return True if recruiter exists in Ligase_Recruiters_Scaffold."""
#     q = """
#     SELECT 1 FROM Ligase_Recruiters_Scaffold
#     WHERE RECRUITER_CODE = ?
#     LIMIT 1
#     """
#     return conn.execute(q, (recruiter,)).fetchone() is not None




# """
# MASTER_DUPLICATE_BUILDER.py
# ----------------------------------
# Creates ALL mappings in ONE execution:
# 1. Builds duplicate_master_fullmap.csv  
# 2. Builds recruiter_master_map.csv  
# 3. Populates Recruiter_Master_Map table in Ligase_Recruiter.db
# """

# import sqlite3
# import csv
# import os

# DB = r"Ligases/Ligase_Recruiter.db"

# CSV_FULLMAP = "duplicate_master_fullmap.csv"
# CSV_MAP = "recruiter_master_map.csv"


# # -----------------------------------------
# # Helpers
# # -----------------------------------------
# def parse_recruiters(text):
#     """Parse comma-separated recruiter list."""
#     return [x.strip() for x in text.split(",") if x.strip()]


# def recruiter_has_scaffold(conn, recruiter):
#     """Check if recruiter exists in scaffold table."""
#     q = """
#     SELECT 1 FROM Ligase_Recruiters_Scaffold
#     WHERE RECRUITER_CODE = ?
#     LIMIT 1
#     """
#     return conn.execute(q, (recruiter,)).fetchone() is not None


# # -----------------------------------------
# # STEP 1: Build duplicate_master_fullmap.csv
# # -----------------------------------------
# def build_fullmaster_csv(conn):

#     dup_rows = conn.execute("""
#         SELECT Ligand, MATCHED_RECRUITERS
#         FROM Ligase_Duplicate_Ligands
#     """).fetchall()

#     results = []

#     print("\n==============================")
#     print("📄 STEP 1 — BUILDING MASTER DUPLICATE MAP")
#     print("==============================\n")

#     for ligand, rec_text in dup_rows:

#         recruiters = parse_recruiters(rec_text)
#         master = None

#         # Try to find first recruiter with scaffold
#         for r in recruiters:
#             if recruiter_has_scaffold(conn, r):
#                 master = r
#                 break

#         # Record row
#         results.append([ligand, ",".join(recruiters), master or ""])

#         if master:
#             print(f"{ligand}: MASTER = {master}")
#         else:
#             print(f"{ligand}: ⚠️ NO MASTER FOUND")

#     # Write output CSV
#     with open(CSV_FULLMAP, "w", newline="") as f:
#         writer = csv.writer(f)
#         writer.writerow(["Ligand", "Recruiters", "MasterRecruiter"])
#         writer.writerows(results)

#     print(f"\n✅ Wrote → {CSV_FULLMAP}\n")
#     return results


# # -----------------------------------------
# # STEP 2: Build recruiter_master_map.csv
# # -----------------------------------------
# def build_recruiter_to_master_csv(fullmap_rows):

#     rows = []

#     print("===================================")
#     print("📄 STEP 2 — EXPANDING INTO RECRUITER → MASTER MAP")
#     print("===================================\n")

#     for ligand, rec_list, master in fullmap_rows:

#         recruiters = parse_recruiters(rec_list)
#         master = master.strip()

#         if not master:
#             master = "BLANK"
#             print(f"⚠️ {ligand}: No master → assigning BLANK")

#         for r in recruiters:
#             rows.append([r, master])

#     with open(CSV_MAP, "w", newline="") as f:
#         writer = csv.writer(f)
#         writer.writerow(["RECRUITER_CODE", "MasterRecruiter"])
#         writer.writerows(rows)

#     print(f"\n✅ Wrote → {CSV_MAP}\n")
#     return rows


# # -----------------------------------------
# # STEP 3: Insert into DB as Recruiter_Master_Map
# # -----------------------------------------
# def insert_into_database(conn, rows):

#     print("===================================")
#     print("📄 STEP 3 — WRITING TABLE Recruiter_Master_Map")
#     print("===================================\n")

#     conn.execute("DROP TABLE IF EXISTS Recruiter_Master_Map")

#     conn.execute("""
#         CREATE TABLE Recruiter_Master_Map (
#             RECRUITER_CODE TEXT,
#             MasterRecruiter TEXT
#         )
#     """)

#     conn.executemany("""
#         INSERT INTO Recruiter_Master_Map (RECRUITER_CODE, MasterRecruiter)
#         VALUES (?, ?)
#     """, rows)

#     conn.commit()

#     print("🎉 SUCCESS — Added Recruiter_Master_Map to DB!\n")


# # -----------------------------------------
# # MAIN
# # -----------------------------------------
# def main():
#     conn = sqlite3.connect(DB)

#     # Step 1
#     fullmap = build_fullmaster_csv(conn)

#     # Step 2
#     recruiter_map_rows = build_recruiter_to_master_csv(fullmap)

#     # Step 3
#     insert_into_database(conn, recruiter_map_rows)

#     conn.close()


# if __name__ == "__main__":
#     main()




# import sqlite3
# import csv

# DB = r"Ligases/Ligase_Recruiter.db"
# OUT = "missing_descriptors.csv"

# def main():
#     conn = sqlite3.connect(DB)

#     # ---- 1) Get ALL recruiters used in 3DMapped ----
#     mapped = conn.execute("""
#         SELECT DISTINCT RECRUITER_CODE
#         FROM Ligase_Ligands_Smiles_3DMapped
#     """).fetchall()

#     mapped = [r[0] for r in mapped]

#     print(f"🔍 Total recruiters with 3D-mapped atoms: {len(mapped)}")

#     # ---- 2) Get recruiters with descriptor rows ----
#     desc = conn.execute("""
#         SELECT DISTINCT RECRUITER_CODE
#         FROM Ligase_Chemical_Descriptors
#     """).fetchall()

#     desc = {r[0] for r in desc}

#     print(f"🧪 Total recruiters with descriptors: {len(desc)}")

#     # ---- 3) Compute missing ----
#     missing = [r for r in mapped if r not in desc]

#     print(f"\n⚠️ Missing descriptor rows: {len(missing)}")
#     for m in missing[:10]:
#         print("  -", m)

#     # ---- 4) Export CSV ----
#     with open(OUT, "w", newline="") as f:
#         writer = csv.writer(f)
#         writer.writerow(["RECRUITER_CODE"])
#         for r in missing:
#             writer.writerow([r])

#     print(f"\n✅ Wrote → {OUT}")

#     conn.close()


# if __name__ == "__main__":
#     main()






# import sqlite3
# import csv

# DB = r"Ligases/Ligase_Recruiter.db"

# INPUT = "missing_descriptors.csv"
# OUTPUT = "missing_descriptors_with_smiles.csv"

# def main():
#     conn = sqlite3.connect(DB)
#     conn.row_factory = sqlite3.Row

#     out_rows = []

#     with open(INPUT, "r", newline="") as f:
#         reader = csv.DictReader(f)

#         for row in reader:
#             rc = row["RECRUITER_CODE"].strip()

#             smi_row = conn.execute("""
#                 SELECT SMILES
#                 FROM Recruiter_SMILES_Map
#                 WHERE RECRUITER_CODE = ?
#                 LIMIT 1;
#             """, [rc]).fetchone()

#             smiles = smi_row["SMILES"] if smi_row else ""

#             if not smiles:
#                 print(f"⚠️ No SMILES found for {rc}")

#             out_rows.append([rc, smiles])

#     # Write new CSV
#     with open(OUTPUT, "w", newline="") as f:
#         writer = csv.writer(f)
#         writer.writerow(["RECRUITER_CODE", "SMILES"])
#         writer.writerows(out_rows)

#     print(f"\n✅ Wrote → {OUTPUT}\n")
#     conn.close()


# if __name__ == "__main__":
#     main()


# import sqlite3
# import pandas as pd

# # --------------------------------------------
# # CONFIG
# # --------------------------------------------
# CSV_FILE = "missing_descriptors.csv"
# DB_FILE = "Ligases/Ligase_Recruiter.db"   # adjust path if needed
# OUTPUT_FILE = "Missing_Recruiter_PDB_Map.csv"
# TABLE = "Ligase_Ligands_Smiles_3DMapped"

# # --------------------------------------------
# # LOAD MISSING RECRUITERS
# # --------------------------------------------
# missing_df = pd.read_csv(CSV_FILE)
# missing_codes = missing_df["RECRUITER_CODE"].tolist()

# print(f"Loaded {len(missing_codes)} recruiter codes to check.")

# # --------------------------------------------
# # CONNECT TO DATABASE
# # --------------------------------------------
# conn = sqlite3.connect(DB_FILE)
# cursor = conn.cursor()

# results = []

# # --------------------------------------------
# # QUERY FOR EACH RECRUITER_CODE
# # --------------------------------------------
# for code in missing_codes:
#     cursor.execute(
#         f"""
#         SELECT DISTINCT pdb_id
#         FROM {TABLE}
#         WHERE RECRUITER_CODE = ?
#         """,
#         (code,)
#     )
#     rows = cursor.fetchall()

#     if rows:
#         pdb_ids = [r[0] for r in rows]
#     else:
#         pdb_ids = []

#     results.append({
#         "RECRUITER_CODE": code,
#         "PDB_IDs": ";".join(pdb_ids) if pdb_ids else "NOT FOUND"
#     })

# # --------------------------------------------
# # SAVE OUTPUT
# # --------------------------------------------
# out_df = pd.DataFrame(results)
# out_df.to_csv(OUTPUT_FILE, index=False)

# print(f"\n🎉 DONE — wrote {OUTPUT_FILE}")



# import re
# import requests
# import pandas as pd

# INPUT_FILE = "Missing_Recruiter_PDB_Map.csv"
# OUTPUT_FILE = "Missing_Recruiter_PDB_FirstLigand.csv"

# URL = "https://www.rcsb.org/structure/{}"

# # Regex to capture the JS variable:
# PATTERN = re.compile(r'var structureFirstLigand = "([^"]+)"')

# def get_first_ligand(pdb_id):
#     """Get the structureFirstLigand variable from the RCSB HTML."""
#     url = URL.format(pdb_id)
#     try:
#         html = requests.get(url, timeout=10).text
#     except Exception as e:
#         print(f"❌ Error fetching {pdb_id}: {e}")
#         return "ERROR"

#     match = PATTERN.search(html)
#     return match.group(1) if match else "NONE"


# # ----------------------------------------------------------
# # MAIN
# # ----------------------------------------------------------

# df = pd.read_csv(INPUT_FILE)
# first_ligand_col = []

# print("\n🚀 Extracting structureFirstLigand from RCSB...\n")

# for _, row in df.iterrows():
#     pdb_ids = row["PDB_IDs"]

#     if pdb_ids == "NOT FOUND":
#         first_ligand_col.append("NOT FOUND")
#         continue

#     # If multiple PDB IDs, just take first (your call)
#     pdb = pdb_ids.split(";")[0]
#     lig = get_first_ligand(pdb)
#     print(f"{pdb} → {lig}")

#     first_ligand_col.append(lig)

# df["StructureFirstLigand"] = first_ligand_col
# df.to_csv(OUTPUT_FILE, index=False)

# print(f"\n🎉 DONE — wrote {OUTPUT_FILE}\n")


# import pandas as pd


# # ================================================================
# # 1. LOAD FIRST-LIGAND RESULTS (already created earlier)
# # ================================================================
# INPUT_CSV = "Missing_Recruiter_PDB_FirstLigand.csv"

# print(f"📥 Loading recruiter–PDB–ligand map from {INPUT_CSV} ...")
# df = pd.read_csv(INPUT_CSV)
# print(f"✔ Loaded {len(df)} rows.")


# # ================================================================
# # 2. LOAD COMPONENT SMILES FILE (robust custom parser)
# # ================================================================
# SMILES_FILE = "Components-smiles-oe.smi"

# print(f"📥 Loading SMILES components from {SMILES_FILE} ...")

# smiles_entries = []

# with open(SMILES_FILE, "r", encoding="utf-8") as f:
#     for raw in f:
#         line = raw.strip()

#         if not line:
#             continue

#         parts = line.split()

#         # Must have at least SMILES + Component_ID
#         if len(parts) < 2:
#             continue

#         smiles = parts[0]
#         component_id = parts[1]
#         name = " ".join(parts[2:]) if len(parts) > 2 else ""

#         smiles_entries.append({
#             "SMILES": smiles,
#             "COMPONENT_ID": component_id,
#             "NAME": name
#         })

# smiles_df = pd.DataFrame(smiles_entries)
# comp_to_smiles = dict(zip(smiles_df["COMPONENT_ID"], smiles_df["SMILES"]))

# print(f"✔ Loaded {len(smiles_df)} SMILES entries.")


# # ================================================================
# # 3. MAP StructureFirstLigand → SMILES
# # ================================================================
# print("🔗 Mapping StructureFirstLigand → SMILES ...")

# smiles_column = []

# for idx, row in df.iterrows():
#     comp_id = str(row["StructureFirstLigand"]).strip()

#     if comp_id in comp_to_smiles:
#         smiles_column.append(comp_to_smiles[comp_id])
#     else:
#         smiles_column.append("NONE")

# df["SMILES"] = smiles_column
# print("✔ Added SMILES column.")


# # OPTIONAL: Remove rows with no SMILES
# REMOVE_NONE = False  # Set to True if you want to drop missing entries

# if REMOVE_NONE:
#     before = len(df)
#     df = df[df["SMILES"] != "NONE"].reset_index(drop=True)
#     print(f"✔ Removed {before - len(df)} rows with missing SMILES.")


# # ================================================================
# # 4. WRITE FINAL CSV
# # ================================================================
# OUTPUT_CSV = "Missing_Recruiter_PDB_Ligand_SMILES.csv"
# df.to_csv(OUTPUT_CSV, index=False)

# print(f"🎉 DONE — wrote {OUTPUT_CSV}")





# import pandas as pd
# import math
# from rdkit import Chem
# from rdkit.Chem import Descriptors, Crippen, rdMolDescriptors, QED
# from rdkit.Chem import FilterCatalog
# from rdkit.Chem.FilterCatalog import FilterCatalogParams

# INPUT  = "Missing_Recruiter_PDB_Ligand_SMILES.csv"
# OUTPUT = "FIXEDLigase_MISSING_Chemical_Descriptors.csv"

# # ============================================================
# # SAFE HELPERS
# # ============================================================
# from rdkit import RDLogger
# RDLogger.DisableLog("rdApp.*")

# def safe_mol(smiles):
#     smiles = str(smiles).strip()
#     try:
#         mol = Chem.MolFromSmiles(smiles, sanitize=True)
#         if mol:
#             return mol
#     except:
#         pass

#     try:
#         mol = Chem.MolFromSmiles(smiles, sanitize=False)
#         return mol
#     except:
#         return None


# def safe_bertz(mol):
#     try:
#         return rdMolDescriptors.CalcBertzCT(mol)
#     except:
#         try:
#             return Descriptors.BertzCT(mol)
#         except:
#             return math.nan


# # ============================================================
# # PAINS & BRENK
# # ============================================================
# def check_pains(mol):
#     params = FilterCatalogParams()
#     params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS_A)
#     params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS_B)
#     params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS_C)
#     catalog = FilterCatalog.FilterCatalog(params)
#     hits = catalog.GetMatches(mol)
#     return "; ".join([h.GetDescription() for h in hits]) if hits else "None"


# def check_brenk(mol):
#     params = FilterCatalogParams()
#     params.AddCatalog(FilterCatalogParams.FilterCatalogs.BRENK)
#     catalog = FilterCatalog.FilterCatalog(params)
#     hits = catalog.GetMatches(mol)
#     return "; ".join([h.GetDescription() for h in hits]) if hits else "None"


# # ============================================================
# # DRUG-LIKENESS RULES
# # ============================================================
# def druglikeness_rules(d):
#     mw, logp, tpsa = d["MW"], d["LogP"], d["TPSA"]
#     hbd, hba, rot = d["HBD"], d["HBA"], d["Rotatable_Bonds"]
#     heavy = d["Heavy_Atom_Count"]

#     lipinski = sum([
#         mw > 500,
#         logp > 5,
#         hbd > 5,
#         hba > 10
#     ]) <= 1

#     veber = (tpsa <= 140) and (rot <= 10)
#     egan = (tpsa <= 131) and (logp <= 5.88)
#     ghose = (160 <= mw <= 480) and (-0.4 <= logp <= 5.6) and (20 <= heavy <= 70)
#     muegge = (200 <= mw <= 600) and (-2 <= logp <= 5) and (hba <= 10) and (hbd <= 5) and (tpsa <= 150)

#     return {
#         "Lipinski_Pass": lipinski,
#         "Veber_Pass": veber,
#         "Egan_Pass": egan,
#         "Ghose_Pass": ghose,
#         "Muegge_Pass": muegge
#     }

# def force_sanitize(mol):
#     """
#     Safely sanitize a molecule and assign missing valence and stereo.
#     Returns None if the molecule cannot be fixed.
#     """
#     if mol is None:
#         return None

#     try:
#         Chem.SanitizeMol(mol)
#     except:
#         # Attempt partial sanitization
#         try:
#             Chem.SanitizeMol(
#                 mol,
#                 sanitizeOps=Chem.SanitizeFlags.SANITIZE_FINDRADICALS |
#                             Chem.SanitizeFlags.SANITIZE_KEKULIZE |
#                             Chem.SanitizeFlags.SANITIZE_SETAROMATICITY |
#                             Chem.SanitizeFlags.SANITIZE_SETCONJUGATION |
#                             Chem.SanitizeFlags.SANITIZE_SETHYBRIDIZATION
#             )
#         except:
#             return None

#     try:
#         # Assign stereochemistry, prevents numStereoCenters errors
#         Chem.AssignAtomChiralTags(mol, force=True)
#         Chem.AssignStereochemistry(mol, force=True)
#     except:
#         pass  # stereo isn't required for validity

#     return mol


# # ============================================================
# # DESCRIPTOR BUILDER
# # ============================================================
# def compute_descriptors(mol):

#     def safe(fn, default=math.nan):
#         try:
#             return fn(mol)
#         except:
#             return default

#     d = {
#         "MW": safe(Descriptors.MolWt),
#         "LogP": safe(Crippen.MolLogP),
#         "TPSA": safe(rdMolDescriptors.CalcTPSA),
#         "HBA": safe(rdMolDescriptors.CalcNumHBA),
#         "HBD": safe(rdMolDescriptors.CalcNumHBD),
#         "Rotatable_Bonds": safe(rdMolDescriptors.CalcNumRotatableBonds),
#         "Ring_Count": safe(rdMolDescriptors.CalcNumRings),
#         "Aromatic_Rings": safe(rdMolDescriptors.CalcNumAromaticRings),
#         "Fraction_CSP3": safe(rdMolDescriptors.CalcFractionCSP3),
#         "Heavy_Atom_Count": safe(lambda m: m.GetNumHeavyAtoms()),
#         "Chiral_Atoms": safe(rdMolDescriptors.CalcNumAtomStereoCenters),
#         "Formal_Charge": safe(Chem.GetFormalCharge),
#         "QED": safe(QED.qed),
#         "BertzCT": safe_bertz(mol),
#         "HallKierAlpha": safe(Descriptors.HallKierAlpha),
#         "Kappa1": safe(Descriptors.Kappa1),
#         "Kappa2": safe(Descriptors.Kappa2),
#         "Kappa3": safe(Descriptors.Kappa3),
#         "NumSpiroAtoms": safe(rdMolDescriptors.CalcNumSpiroAtoms),
#         "NumBridgeheadAtoms": safe(rdMolDescriptors.CalcNumBridgeheadAtoms),
#         "NumAliphaticRings": safe(rdMolDescriptors.CalcNumAliphaticRings),
#         "NumSaturatedRings": safe(rdMolDescriptors.CalcNumSaturatedRings),
#         "NumHeteroAtoms": safe(rdMolDescriptors.CalcNumHeteroatoms),
#         "MolMR": safe(Descriptors.MolMR),
#         "SA_Score": math.nan  # your script disables SA score
#     }

#     # Add all drug-likeness rules safely
#     try:
#         d.update(druglikeness_rules(d))
#     except:
#         pass

#     return d


# # ============================================================
# # MAIN
# # ============================================================
# def main():
#     df = pd.read_csv(INPUT)
#     rows = []

#     print(f"🔍 Loaded {len(df)} missing SMILES")

#     for _, row in df.iterrows():
#         code, smi = row["RECRUITER_CODE"], row["SMILES"]

#         mol = safe_mol(smi)

#         # Try full sanitization
#         mol = force_sanitize(mol)

#         if mol is None:
#             print(f"⚠️ UNUSABLE SMILES → {code}: {smi}")
#             continue


#         d = compute_descriptors(mol)
#         d["RECRUITER_CODE"] = code
#         d["SMILES"] = smi
#         d["PAINS_Hits"] = check_pains(mol)
#         d["Brenk_Hits"] = check_brenk(mol)

#         rows.append(d)

#     pd.DataFrame(rows).to_csv(OUTPUT, index=False)

#     print(f"\n✅ Wrote descriptor table → {OUTPUT}")
#     print(f"🧪 Rows: {len(rows)}")


# if __name__ == "__main__":
#     main()








import sqlite3
import pandas as pd

DB = "Ligases/Ligase_Recruiter.db"
OUT = "duplicate_recruiter_codes_descriptors.csv"

def main():
    conn = sqlite3.connect(DB)

    # Query duplicates
    df = pd.read_sql_query("""
        SELECT 
            RECRUITER_CODE,
            COUNT(*) AS count
        FROM Ligase_Chemical_Descriptors
        GROUP BY RECRUITER_CODE
        HAVING COUNT(*) > 1
        ORDER BY count DESC;
    """, conn)

    conn.close()

    if df.empty:
        print("✅ No duplicate RECRUITER_CODE entries found in Ligase_Chemical_Descriptors.")
    else:
        print("⚠️ Duplicates found!")
        print(df)

        df.to_csv(OUT, index=False)
        print(f"📄 Duplicate list written to: {OUT}")


if __name__ == "__main__":
    main()
