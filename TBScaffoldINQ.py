# # import sqlite3

# # DB_PATH = "Ligases/Ligase_Recruiter.db"
# # OUTFILE = "recruiters_without_scaffolds.txt"

# # query = """
# # SELECT DISTINCT r.RECRUITER_CODE
# # FROM Recruiter_Master_Map r
# # LEFT JOIN Ligase_Recruiters_Scaffold s
# #     ON r.RECRUITER_CODE = s.RECRUITER_CODE
# # WHERE s.RECRUITER_CODE IS NULL
# # ORDER BY r.RECRUITER_CODE;
# # """

# # def main():
# #     conn = sqlite3.connect(DB_PATH)
# #     cur = conn.cursor()

# #     cur.execute(query)
# #     recruiters = [row[0] for row in cur.fetchall()]

# #     conn.close()

# #     with open(OUTFILE, "w") as f:
# #         for r in recruiters:
# #             f.write(f"{r}\n")

# #     print(f"✔ Found {len(recruiters)} recruiters without scaffolds")
# #     print(f"✔ Written to: {OUTFILE}")

# # if __name__ == "__main__":
# #     main()



# # import sqlite3

# # DB_PATH = "Ligases/Ligase_Recruiter.db"
# # INPUT_FILE = "recruiters_without_scaffolds.txt"
# # OUT_FILE = "recruiter_existence_report.txt"

# # TABLES_AND_COLUMNS = {
# #     "Recruiter_Master_Map": "RECRUITER_CODE",
# #     "Ligase_Recruiters_Scaffold": "RECRUITER_CODE",
# #     "Ligase_Chemical_Descriptors": "RECRUITER_CODE",
# #     "Ligase_Ligands_Smiles_3DMapped": "RECRUITER_CODE",
# #     "Ligase_SMILE_Codes": "RECRUITER_CODE",
# #     "Ligase_SMILE_Codes_Atoms": "RECRUITER_CODE",
# # }

# # def main():
# #     conn = sqlite3.connect(DB_PATH)
# #     cur = conn.cursor()

# #     with open(INPUT_FILE) as f:
# #         recruiters = [line.strip() for line in f if line.strip()]

# #     with open(OUT_FILE, "w") as out:
# #         for rec in recruiters:
# #             out.write(f"\n=== {rec} ===\n")

# #             found_any = False

# #             for table, col in TABLES_AND_COLUMNS.items():
# #                 q = f"""
# #                 SELECT COUNT(*) FROM {table}
# #                 WHERE {col} = ?
# #                 """
# #                 cur.execute(q, (rec,))
# #                 count = cur.fetchone()[0]

# #                 if count > 0:
# #                     found_any = True
# #                     out.write(f"  ✔ Found in {table}: {count} rows\n")
# #                 else:
# #                     out.write(f"  ✘ Not in {table}\n")

# #             if not found_any:
# #                 out.write("  ⚠ Recruiter not found in ANY checked table\n")

# #     conn.close()
# #     print(f"✔ Trace report written to {OUT_FILE}")

# # if __name__ == "__main__":
# #     main()

# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-

# import sqlite3

# DB_PATH = "Ligases/Ligase_Recruiter.db"
# RECRUITER_CODE = "L00126"

# def main():
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     cur = conn.cursor()

#     query = """
#     SELECT
#         m.Ligand,
#         d.SMILES
#     FROM Ligase_Chemical_Descriptors d
#     LEFT JOIN Recruiter_Master_Map r
#         ON d.RECRUITER_CODE = r.RECRUITER_CODE
#     LEFT JOIN Ligase_Ligand_Metadata m
#         ON r.Ligand = m.Ligand
#     WHERE d.RECRUITER_CODE = ?
#     """

#     cur.execute(query, (RECRUITER_CODE,))
#     rows = cur.fetchall()

#     if not rows:
#         print(f"No entries found for recruiter {RECRUITER_CODE}")
#         return

#     print(f"\nLigands + SMILES for recruiter {RECRUITER_CODE}:\n")
#     for row in rows:
#         print(f" Ligand: {row['Ligand'] or 'UNKNOWN':<8} | SMILES: {row['SMILES']}")

#     conn.close()

# if __name__ == "__main__":
#     main()


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# import sqlite3

# DB_PATH = "Ligases/Ligase_Recruiter.db"

# SMILES = "C1CC(CCC1COC(=O)NC2CCC(=O)NC2=O)N"

# def main():
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     cur = conn.cursor()

#     query = """
#     SELECT DISTINCT RECRUITER_CODE
#     FROM Recruiter_SMILES_Map
#     WHERE SMILES = ?
#     """

#     cur.execute(query, (SMILES,))
#     rows = cur.fetchall()

#     if not rows:
#         print("\n❌ SMILES not found in Recruiter_SMILES_Map\n")
#         return

#     recruiters = [r["RECRUITER_CODE"] for r in rows]

#     print("\n🧪 SMILES found in the following recruiters:\n")
#     for r in recruiters:
#         print(f"  • {r}")

#     if len(recruiters) > 1:
#         print(f"\n⚠️ WARNING: SMILES maps to {len(recruiters)} recruiters!")
#     else:
#         print("\n✅ SMILES is unique to a single recruiter.")

#     conn.close()

# if __name__ == "__main__":
#     main()



#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# import sqlite3

# DB_PATH = "Ligases/Ligase_Recruiter.db"
# OUT_FILE = "duplicated_smiles_report.txt"

# def main():
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     cur = conn.cursor()

#     query = """
#     SELECT
#         SMILES,
#         COUNT(DISTINCT RECRUITER_CODE) AS recruiter_count,
#         GROUP_CONCAT(DISTINCT RECRUITER_CODE) AS recruiters
#     FROM Recruiter_SMILES_Map
#     GROUP BY SMILES
#     HAVING recruiter_count > 1
#     ORDER BY recruiter_count DESC;
#     """

#     cur.execute(query)
#     rows = cur.fetchall()

#     if not rows:
#         print("\n✅ No duplicated SMILES found.\n")
#         return

#     with open(OUT_FILE, "w") as f:
#         f.write("SMILES\tCount\tRecruiters\n")
#         for r in rows:
#             f.write(f"{r['SMILES']}\t{r['recruiter_count']}\t{r['recruiters']}\n")

#     print(f"\n⚠️ Found {len(rows)} duplicated SMILES.")
#     print(f"📄 Report written to: {OUT_FILE}\n")

#     conn.close()

# if __name__ == "__main__":
#     main()


# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-

# import sqlite3
# import csv

# DB_PATH = "Ligases/Ligase_Recruiter.db"

# OUT_TXT = "bad_2d_3d_mappings.txt"
# OUT_CSV = "bad_2d_3d_mappings.csv"


# def main():
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     cur = conn.cursor()

#     # 1️⃣ All ligands that appear in 3D (SASA summary)
#     cur.execute("""
#         SELECT DISTINCT
#             m.RECRUITER_CODE,
#             s.Ligand,
#             s.pdb_id,
#             s.Variant
#         FROM Ligase_Ligand_SASA_summary s
#         JOIN Ligase_Ligands_Smiles_3DMapped m
#         ON s.Ligand = m.Ligand
#         AND s.Variant = m.Variant
#     """)
#     ligands_3d = cur.fetchall()

#     ligands_3d = cur.fetchall()

#     bad = []

#     for row in ligands_3d:
#         recruiter = row["RECRUITER_CODE"]
#         ligand    = row["Ligand"]
#         pdb_id    = row["pdb_id"]
#         variant   = row["Variant"]

#         # 2️⃣ Check atom mapping count
#         cur.execute("""
#             SELECT COUNT(*) AS n
#             FROM Ligase_Ligands_Smiles_3DMapped
#             WHERE RECRUITER_CODE = ?
#               AND Ligand = ?
#               AND Variant = ?
#         """, (recruiter, ligand, variant))

#         n_mapped = cur.fetchone()["n"]

#         if n_mapped == 0:
#             bad.append({
#                 "RECRUITER_CODE": recruiter,
#                 "Ligand": ligand,
#                 "pdb_id": pdb_id,
#                 "Variant": variant,
#                 "Mapped_Atoms": n_mapped
#             })

#     conn.close()

#     # 3️⃣ Write TXT
#     with open(OUT_TXT, "w") as f:
#         f.write("❌ BAD 2D–3D MAPPINGS (0 mapped atoms)\n")
#         f.write("=" * 50 + "\n\n")

#         for b in bad:
#             f.write(
#                 f"{b['RECRUITER_CODE']} | "
#                 f"Ligand={b['Ligand']} | "
#                 f"PDB={b['pdb_id']} | "
#                 f"Variant={b['Variant']}\n"
#             )

#     # 4️⃣ Write CSV
#     with open(OUT_CSV, "w", newline="") as f:
#         writer = csv.DictWriter(
#             f,
#             fieldnames=["RECRUITER_CODE", "Ligand", "pdb_id", "Variant", "Mapped_Atoms"]
#         )
#         writer.writeheader()
#         writer.writerows(bad)

#     print(f"\n✅ Audit complete")
#     print(f"❌ Bad mappings found: {len(bad)}")
#     print(f"📄 TXT: {OUT_TXT}")
#     print(f"📊 CSV: {OUT_CSV}\n")


# if __name__ == "__main__":
#     main()


import sqlite3
import csv

DB_PATH = "Ligases/Ligase_Recruiter.db"
TABLE_NAME = "Recruiter_Master_Map"
OUT_CSV = "Masterrecruiter.csv"

def export_table_to_csv(db_path, table_name, out_csv):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Fetch column names
    cur.execute(f"PRAGMA table_info({table_name});")
    columns = [col[1] for col in cur.fetchall()]

    if not columns:
        raise RuntimeError(f"No columns found for table: {table_name}")

    # Fetch all rows
    cur.execute(f"SELECT * FROM {table_name};")
    rows = cur.fetchall()

    # Write CSV
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)  # header
        writer.writerows(rows)

    conn.close()

    print(f"✅ Exported {len(rows)} rows from '{table_name}' → {out_csv}")

if __name__ == "__main__":
    export_table_to_csv(DB_PATH, TABLE_NAME, OUT_CSV)
