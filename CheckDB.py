import sqlite3

# --------------------------------------------------
# CONFIG: schema knowledge (explicit + correct)
# --------------------------------------------------

DIRECT_RECRUITER_TABLES = {
    "Ligase_Chemical_Descriptors": "RECRUITER_CODE",
    "Ligase_Ligands_Smiles_3DMapped": "RECRUITER_CODE",
    "Recruiter_Master_Map": "RECRUITER_CODE",
    "Recruiter_SMILES_Map": "RECRUITER_CODE",
    "Ligase_SMILE_Codes": "RECRUITER_CODE",
    "Ligase_SMILE_Codes_Atoms": "RECRUITER_CODE",
    "Ligase_Recruiters_Scaffold": "RECRUITER_CODE",
    "missing_recruiters": "RECRUITER_CODE",
}

INDIRECT_LIGAND_TABLES = {
    "Ligase_Ligand_Metadata": "Ligand",
    "Ligase_Ligand_SASA_atoms": "Ligand",
    "Ligase_Ligand_SASA_summary": "Ligand",
    "Ligase_Ligands_Smiles": "Ligand",
    "Ligase_Duplicate_Ligands": "Ligand",
}

DERIVED_TABLES = {
    "Ligase_Scaffold_Data",
    "Ligase_Scaffold_Frequency",
    "Ligase_Scaffold_Summary",
    "Scaffold_Unified_Map",
}

# --------------------------------------------------
# MAIN AUDIT FUNCTION
# --------------------------------------------------

def audit_recruiter_semantic(db_path, recruiter_code):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"\n🔎 SEMANTIC AUDIT — Recruiter {recruiter_code}")
    print("=" * 60)

    # --------------------------------------------------
    # STEP 1: direct recruiter presence
    # --------------------------------------------------
    print("\n🟢 DIRECT RECRUITER PRESENCE")

    direct_hits = []
    for table, col in DIRECT_RECRUITER_TABLES.items():
        try:
            cursor.execute(
                f"SELECT 1 FROM {table} WHERE {col} = ? LIMIT 1;",
                (recruiter_code,)
            )
            if cursor.fetchone():
                direct_hits.append(f"{table}.{col}")
        except sqlite3.OperationalError:
            pass

    if direct_hits:
        for hit in direct_hits:
            print(f"  ✔ {hit}")
    else:
        print("  ❌ Recruiter not found in any direct tables")

    # --------------------------------------------------
    # STEP 2: resolve recruiter → ligands
    # --------------------------------------------------
    print("\n🟡 RESOLVED LIGANDS")

    cursor.execute(
        """
        SELECT DISTINCT Ligand
        FROM Recruiter_Master_Map
        WHERE RECRUITER_CODE = ?
        """,
        (recruiter_code,)
    )
    ligands = [r[0] for r in cursor.fetchall()]

    if not ligands:
        print("  ❌ No ligands mapped to this recruiter")
        conn.close()
        return

    for lig in ligands:
        print(f"  ✔ {lig}")

    # --------------------------------------------------
    # STEP 3: indirect ligand presence
    # --------------------------------------------------
    print("\n🟡 INDIRECT (LIGAND-MEDIATED) PRESENCE")

    indirect_found = []
    indirect_missing = []

    for table, col in INDIRECT_LIGAND_TABLES.items():
        placeholders = ",".join("?" * len(ligands))
        query = f"""
            SELECT 1 FROM {table}
            WHERE {col} IN ({placeholders})
            LIMIT 1
        """
        try:
            cursor.execute(query, ligands)
            if cursor.fetchone():
                indirect_found.append(table)
            else:
                indirect_missing.append(table)
        except sqlite3.OperationalError:
            indirect_missing.append(table)

    for table in indirect_found:
        print(f"  ✔ {table}")

    for table in indirect_missing:
        print(f"  ❌ {table} (no ligand data)")

    # --------------------------------------------------
    # STEP 4: derived tables (informational only)
    # --------------------------------------------------
    print("\n🔵 DERIVED / AGGREGATE TABLES (INFO ONLY)")

    for table in DERIVED_TABLES:
        print(f"  ℹ {table} (derived; absence may be expected)")

    conn.close()
    print("\n🧠 Semantic audit complete.\n")

# --------------------------------------------------
# CLI ENTRY
# --------------------------------------------------

if __name__ == "__main__":
    db_file = "Ligases/Ligase_Recruiter.db"
    audit_recruiter_semantic(db_file, "L00003")
