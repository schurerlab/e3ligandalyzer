#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
E3 Ligase Atlas — API + Static Routes
-------------------------------------------------------------------------------
Provides:
  • SQLite → JSON endpoints for recruiter and scaffold data
  • RDKit SVG rendering for SMILES and recruiter codes
  • PDB and SDF file serving from Ligases/<Ligase>/ directories
  • ELiAH gene expression integration for ligase analysis
===============================================================================
"""

import os
import re
import sqlite3
from pathlib import Path
import requests
from flask import Blueprint, jsonify, request, send_from_directory, current_app
import pandas as pd
from Ligases import randy_client
from Ligases import shipment_store


# ---------------------------------------------------------------------------
# 🔹 Blueprint Definition
# ---------------------------------------------------------------------------
ligases_bp = Blueprint("ligases_bp", __name__)

# ---------------------------------------------------------------------------
# 🔹 Database Paths
# ---------------------------------------------------------------------------
DB_PATH = os.environ.get(
    "E3_LOCAL_DB_PATH",
    os.path.join(os.path.dirname(__file__), "Ligase_Recruiter.db"),
)
ELIAH_DB_PATH = os.environ.get(
    "E3_LOCAL_ELIAH_DB_PATH",
    os.path.join(os.path.dirname(__file__), "eliah.db"),
)
import uuid

# ---------------------------------------------------------------------------
# 🔹 Database Query Helpers
# ---------------------------------------------------------------------------
def query_db(query, args=(), one=False):
    """
    Execute a query against the primary Ligase_Recruiter.db database.
    Returns a list of Row objects or a single record if one=True.
    """
    if randy_client.remote_enabled():
        return randy_client.query("main", query, args, one=one)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(query, args)
    rows = cur.fetchall()
    conn.close()
    return (rows[0] if rows else None) if one else rows


def query_eliah_db(query, args=(), one=False):
    """
    Execute a query against the ELiAH gene expression database (eliah.db).
    Returns JSON-ready dictionaries by default.
    """
    if randy_client.remote_enabled():
        return randy_client.query("eliah", query, args, one=one)

    conn = sqlite3.connect(ELIAH_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(query, args)
    rows = cur.fetchall()
    conn.close()
    return (rows[0] if rows else None) if one else [dict(r) for r in rows]


def _eliah_table_columns(table_name):
    """Read ELiAH table columns through a SELECT-compatible path for remote mode."""
    table_name = str(table_name or "").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
        raise ValueError(f"Invalid ELiAH table name: {table_name}")
    rows = query_eliah_db(f"SELECT name FROM pragma_table_info('{table_name}') ORDER BY cid;")
    columns = []
    for row in rows:
        if isinstance(row, dict):
            name = str(row.get("name", "")).strip()
        elif isinstance(row, (list, tuple)) and row:
            name = str(row[0]).strip()
        else:
            name = ""
        if name:
            columns.append(name)
    return columns


def normalize_sdf_filename(filename: str) -> str:
    """Normalize a PDB-like or SDF-like asset name into an SDF filename."""
    raw = str(filename or "").strip()
    if not raw:
        raise ValueError("Missing filename.")

    parts = Path(raw).parts
    if raw.startswith("/") or ".." in parts:
        raise ValueError("Invalid filename.")

    suffix = Path(raw).suffix.lower()
    if suffix == ".sdf":
        return raw
    if suffix == ".pdb":
        return f"{raw[:-4]}.sdf"
    if suffix:
        raise ValueError(f"Unsupported file extension: {suffix}")
    return f"{raw}.sdf"


def candidate_sdf_filenames(filename: str) -> list[str]:
    """Return preferred SDF filename candidates for a PDB/SDF asset request."""
    normalized = normalize_sdf_filename(filename)
    stem = Path(normalized).stem
    core_no_variant = re.sub(r"_\d+$", "", stem)

    candidates = [normalized]
    if core_no_variant != stem:
        candidates.append(f"{core_no_variant}.sdf")
    candidates.append(f"{core_no_variant}_1.sdf")
    return list(dict.fromkeys(candidates))


# ===========================================================================
# 🧠 BASIC ENDPOINTS
# ===========================================================================
@ligases_bp.route("/ligases", methods=["GET"])
def get_ligases():
    """Return unique ligase list for dropdowns."""
    rows = query_db("SELECT DISTINCT Ligase FROM Ligase_Scaffold_Data ORDER BY Ligase;")
    return jsonify([r["Ligase"] for r in rows])


@ligases_bp.route("/featured-recruiters", methods=["GET"])
def get_featured_recruiters():
    """
    Return recruiter compounds for the homepage or explorer view.

    Optional query parameters:
      ?ligase=VHL
      ?scaffold_class=Polycyclic_Hetero
      ?recruiter_class=Aromatic
      ?min_qed=0.6
      ?max_qed=1.0
      ?limit=500
      ?offset=0
    """
    ligase = request.args.get("ligase")
    scaffold_class = request.args.get("scaffold_class")
    recruiter_class = request.args.get("recruiter_class")
    min_qed = float(request.args.get("min_qed", 0.0))
    max_qed = float(request.args.get("max_qed", 1.0))
    limit = int(request.args.get("limit", 200))
    offset = int(request.args.get("offset", 0))

    query = """
        SELECT 
            d.RECRUITER_CODE,
            m.Ligase,
            d.MW,
            d.LogP,
            d.QED,
            d.SMILES,
            d.RECRUITER_CODE,
            sd.Scaffold_ID,
            sd.Scaffold_Class,
            sa.Recruiter_Class,
            ROUND(sa.[%Exposed], 2) AS Percent_Exposed,
            ROUND(sa.[%Buried], 2) AS Percent_Buried
        FROM Ligase_Chemical_Descriptors AS d
        LEFT JOIN Ligase_Ligands_Smiles_3DMapped AS m
            ON d.RECRUITER_CODE = m.RECRUITER_CODE
        LEFT JOIN Ligase_Scaffold_Data AS sd
            ON m.Ligase = sd.Ligase
        LEFT JOIN Ligase_Ligand_SASA_summary AS sa
            ON m.Ligase = sa.Ligase AND sa.Ligand = m.Ligand
        WHERE d.QED BETWEEN ? AND ?
            AND m.Ligase IS NOT NULL
            AND TRIM(m.Ligase) != ''
            AND m.Ligase NOT LIKE 'Unknown Ligase'


    """
    params = [min_qed, max_qed]

    if ligase:
        query += " AND m.Ligase = ?"
        params.append(ligase)
    if scaffold_class:
        query += " AND sd.Scaffold_Class = ?"
        params.append(scaffold_class)
    if recruiter_class:
        query += " AND sa.Recruiter_Class = ?"
        params.append(recruiter_class)

    query += """
        GROUP BY d.RECRUITER_CODE, m.Ligase
        ORDER BY d.QED DESC
        LIMIT ? OFFSET ?;
    """
    params.extend([limit, offset])

    rows = query_db(query, params)
    return jsonify([dict(r) for r in rows])




# ===========================================================================
# 🧱 SCAFFOLD + CLASS SUMMARIES
# ===========================================================================
# =======================================================================
# 🧱 SCAFFOLD DASHBOARD ENDPOINTS (FULL FRONTEND COMPATIBLE)
# =======================================================================
@ligases_bp.route("/scaffold-data", methods=["GET"])
def get_scaffold_data():
    """
    Canonical scaffold data endpoint for the dashboard.
    Returns camelCase keys that match the frontend.
    """

    ligase = request.args.get("ligase")
    scaf_class = request.args.get("class")

    query = """
        SELECT
            Ligase,
            Scaffold_ID,
            Recruiter_Count,
            Scaffold_SMILES,
            Murcko_SMILES,
            Scaffold_Class,
            Scaffold_Center_of_Mass_X,
            Scaffold_Center_of_Mass_Y,
            Scaffold_Center_of_Mass_Z,
            Ligase_Scaffold_Connectivity,
            Total_Recruiters,
            Recruiter_Density_Score,
            Shannon_Diversity_Index,
            Normalized_Diversity
        FROM Ligase_Scaffold_Data
        WHERE 1=1
    """

    params = []
    if ligase:
        query += " AND Ligase = ?"
        params.append(ligase)
    if scaf_class:
        query += " AND Scaffold_Class = ?"
        params.append(scaf_class)

    query += " ORDER BY Shannon_Diversity_Index DESC;"

    rows = query_db(query, params)

    def convert_row(r):
        raw_class = r["Scaffold_Class"]
        sc_class = raw_class.strip() if raw_class else ""
        if sc_class == "":
            sc_class = "Unknown"

        return {
            # identifiers
            "ligase": r["Ligase"],
            "scaffoldId": r["Scaffold_ID"],
            "scaffoldClass": sc_class,

            # counts / metrics
            "recruiterCount": r["Recruiter_Count"],
            "totalRecruiters": r["Total_Recruiters"],
            "connectivity": r["Ligase_Scaffold_Connectivity"],
            "recruiterDensity": r["Recruiter_Density_Score"],
            "shannonIndex": r["Shannon_Diversity_Index"],
            "normalizedDiversity": r["Normalized_Diversity"],

            # chemistry
            "scaffoldSmiles": r["Scaffold_SMILES"],
            "murckoSmiles": r["Murcko_SMILES"],

            # coordinates (for future true 3D placement if you want)
            "x": r["Scaffold_Center_of_Mass_X"],
            "y": r["Scaffold_Center_of_Mass_Y"],
            "z": r["Scaffold_Center_of_Mass_Z"],
        }

    clean = [convert_row(r) for r in rows]
    return jsonify(clean)




# =======================================================================
# 🧱 SCAFFOLD DASHBOARD ENDPOINTS (ADDITIONAL)
# =======================================================================

@ligases_bp.route("/scaffold-summary", methods=["GET"])
def get_scaffold_summary():
    """
    Return summarized scaffold diversity metrics per ligase.
      Example: /api/scaffold-summary
    """
    query = """
        SELECT 
            Ligase,
            Unique_Scaffolds,
            Total_Recruiters,
            Diversity_Score,
            Shannon_Index
        FROM Ligase_Scaffold_Summary
        ORDER BY Shannon_Index DESC;
    """
    rows = query_db(query)
    return jsonify([dict(r) for r in rows])


@ligases_bp.route("/scaffold-frequency", methods=["GET"])
def get_scaffold_frequency():
    """
    Return scaffold frequency per ligase.
      Example: /api/scaffold-frequency
               /api/scaffold-frequency?ligase=CRBN
    """
    ligase = request.args.get("ligase")
    if ligase:
        query = """
            SELECT Ligase, Scaffold_ID, Recruiter_Count
            FROM Ligase_Scaffold_Frequency
            WHERE Ligase = ?
            ORDER BY Recruiter_Count DESC;
        """
        rows = query_db(query, [ligase])
    else:
        query = """
            SELECT Ligase, Scaffold_ID, Recruiter_Count
            FROM Ligase_Scaffold_Frequency
            ORDER BY Recruiter_Count DESC;
        """
        rows = query_db(query)
    return jsonify([dict(r) for r in rows])


@ligases_bp.route("/scaffold-recruiters", methods=["GET"])
def get_recruiter_scaffolds():
    """
    Return recruiter-to-scaffold mapping data.
      Example: /api/scaffold-recruiters
               /api/scaffold-recruiters?ligase=CHIP
    """
    ligase = request.args.get("ligase")
    if ligase:
        query = """
            SELECT 
                Ligase,
                Scaffold_ID,
                RECRUITER_CODE,
                Scaffold_SMILES,
                Scaffold_Hash
            FROM Ligase_Recruiters_Scaffold
            WHERE Ligase = ?
            ORDER BY Scaffold_ID;
        """
        rows = query_db(query, [ligase])
    else:
        query = """
            SELECT 
                Ligase,
                Scaffold_ID,
                RECRUITER_CODE,
                Scaffold_SMILES,
                Scaffold_Hash
            FROM Ligase_Recruiters_Scaffold
            ORDER BY Ligase, Scaffold_ID;
        """
        rows = query_db(query)
    return jsonify([dict(r) for r in rows])



















# ===========================================================================
# 🧬 DESCRIPTORS + METADATA
# ===========================================================================
@ligases_bp.route("/descriptors/<recruiter_code>", methods=["GET"])
def get_descriptors(recruiter_code):
    """Return chemical descriptors for a given recruiter."""
    query = "SELECT * FROM Ligase_Chemical_Descriptors WHERE RECRUITER_CODE = ?;"
    rows = query_db(query, [recruiter_code])
    return jsonify([dict(r) for r in rows])


@ligases_bp.route("/metadata/<recruiter_code>", methods=["GET"])
def get_metadata(recruiter_code):
    """Return metadata for a given ligand."""
    query = """
        SELECT * FROM Ligase_Ligand_Metadata
        WHERE Name LIKE ? OR Ligand LIKE ? OR Canonical_SMILES LIKE ?;
    """
    rows = query_db(query, [recruiter_code, recruiter_code, recruiter_code])
    return jsonify([dict(r) for r in rows])


# ===========================================================================
# 📊 LIGASE SUMMARIES + STATS
# ===========================================================================
@ligases_bp.route("/ligase-summary", methods=["GET"])
def get_ligase_summary():
    """Return per-ligase statistics aggregated from Ligase_Scaffold_Data."""
    query = """
        SELECT 
            Ligase,
            COUNT(DISTINCT Scaffold_ID) AS Unique_Scaffolds,
            SUM(Recruiter_Count) AS Total_Recruiters,
            AVG(Recruiter_Density_Score) AS Avg_Density,
            AVG(Shannon_Diversity_Index) AS Avg_Shannon,
            AVG(Normalized_Diversity) AS Avg_Normalized
        FROM Ligase_Scaffold_Data
        GROUP BY Ligase
        ORDER BY Total_Recruiters DESC;
    """
    rows = query_db(query)
    return jsonify([dict(r) for r in rows])


@ligases_bp.route("/recruiter-class-summary", methods=["GET"])
def recruiter_class_summary():
    """Return count of recruiter classes per ligase."""
    query = """
        SELECT Ligase, Recruiter_Class, COUNT(*) AS Count
        FROM Ligase_Ligand_SASA_summary
        GROUP BY Ligase, Recruiter_Class
        ORDER BY Ligase, Count DESC;
    """
    rows = query_db(query)
    return jsonify([dict(r) for r in rows])


@ligases_bp.route("/scaffold-class-summary", methods=["GET"])
def scaffold_class_summary():
    """Return count of scaffold classes per ligase."""
    query = """
        SELECT Ligase, Scaffold_Class, COUNT(*) AS Count
        FROM Ligase_Scaffold_Data
        GROUP BY Ligase, Scaffold_Class
        ORDER BY Ligase, Count DESC;
    """
    rows = query_db(query)
    return jsonify([dict(r) for r in rows])


@ligases_bp.route("/ligase-ligand-stats", methods=["GET"])
def get_ligase_ligand_stats():
    """Aggregate ligand-level metrics (MW, %Exposed, %Buried) per ligase."""
    query = """
        SELECT Ligase,
               AVG(MW) AS Avg_MW,
               AVG([%Exposed]) AS Avg_Exposed,
               AVG([%Buried]) AS Avg_Buried,
               COUNT(*) AS Ligand_Count
        FROM Ligase_Ligand_SASA_summary
        GROUP BY Ligase
        ORDER BY Avg_MW DESC;
    """
    rows = query_db(query)
    return jsonify([dict(r) for r in rows])


# ===========================================================================
# 🧪 SMILES → SVG (RDKit)
# ===========================================================================
@ligases_bp.route("/render-smiles/<path:smiles>")
def render_smiles(smiles):
    """Render a SMILES string as SVG using RDKit."""
    from rdkit import Chem
    from rdkit.Chem import Draw
    from flask import Response

    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return Response("Invalid SMILES", status=400, mimetype="text/plain")

        svg = Draw.MolsToGridImage(
            [mol], molsPerRow=1, subImgSize=(250, 250), useSVG=True
        )
        return Response(svg, mimetype="image/svg+xml")

    except Exception as e:
        print(f"⚠️ RDKit rendering failed for SMILES: {smiles}\nError: {e}")
        return Response(f"Error rendering SMILES: {e}", status=500, mimetype="text/plain")



# ===========================================================================
# 🔬 PDB FILE MANAGEMENT
# ===========================================================================
@ligases_bp.route("/ligase-pdbs/<ligase>", methods=["GET"])
def get_ligase_pdbs(ligase):
    """Return list of PDB files for the given ligase."""
    if randy_client.remote_enabled():
        return jsonify(randy_client.get_json(f"ligase-pdbs/{randy_client.quote_part(ligase)}"))

    # Walk up until we find the top-level Ligases/ folder
    base_dir = os.path.abspath(os.path.dirname(__file__))
    while not os.path.exists(os.path.join(base_dir, "Ligases")) and base_dir != "/":
        base_dir = os.path.dirname(base_dir)

    ligase_dir = os.path.join(base_dir, "Ligases", ligase, "PDB")
    if not os.path.exists(ligase_dir):
        print(f"[404] Ligase PDB folder not found: {ligase_dir}")
        return jsonify([])

    pdb_files = [f for f in os.listdir(ligase_dir) if f.endswith(".pdb")]
    print(f"[DEBUG] Found {len(pdb_files)} PDBs for {ligase} in {ligase_dir}")
    return jsonify(sorted(pdb_files))



# ============================================================
# 🧩 STATIC PDB FILE SERVING WITH VARIANT RESOLUTION + DEBUG
# ============================================================
from flask import send_from_directory
import os
import re

@ligases_bp.route("/Ligases/<ligase>/PDB/<path:filename>")
def serve_ligase_pdb(ligase, filename):
    """
    Serve PDB files from:
       Ligases/<Ligase>/PDB/

    Logic:
      1) Try exact file (your original logic)
      2) Try <base>_1.pdb
      3) Try ANY <base>_<n>.pdb variant
      4) Debug output for all steps
    """
    if randy_client.remote_enabled():
        return randy_client.proxy_file(
            f"file/pdb/{randy_client.quote_part(ligase)}/{randy_client.quote_path(filename)}",
            mimetype="chemical/x-pdb",
        )

    print("\n==============================")
    print(f"🔍 REQUEST RECEIVED for ligase: {ligase}")
    print(f"📄 Requested filename: {filename}")
    print(f"📂 __file__: {__file__}")
    print(f"📂 os.getcwd(): {os.getcwd()}")

    # ----------------------------------------------------------
    # 🌐 BASE PATHS
    # ----------------------------------------------------------
    routes_dir = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.join(routes_dir, ".."))
    pdb_dir_expected = os.path.join(project_root, "Ligases", ligase, "PDB")
    pdb_dir_alt = os.path.join(routes_dir, ligase, "PDB")

    print(f"🧭 routes_dir:       {routes_dir}")
    print(f"🧭 project_root:     {project_root}")
    print(f"🧭 pdb_dir_expected: {pdb_dir_expected}")
    print(f"🧭 pdb_dir_alt:      {pdb_dir_alt}")

    # ----------------------------------------------------------
    # 🔬 Normalize filename (strip extension)
    # ----------------------------------------------------------
    core = os.path.splitext(filename)[0]          # e.g. 4W9L_3JJ
    core_no_variant = re.sub(r"_\d+$", "", core)  # e.g. 4W9L_3JJ

    print(f"🔧 Parsed core:            {core}")
    print(f"🔧 Core (no variant):      {core_no_variant}")

    # ----------------------------------------------------------
    # 📂 BUILD FULL PATHS (exact)
    # ----------------------------------------------------------
    exact_expected = os.path.join(pdb_dir_expected, f"{core}.pdb")
    exact_alt = os.path.join(pdb_dir_alt, f"{core}.pdb")

    print(f"📄 exact_expected: {exact_expected}")
    print(f"📄 exact_alt:      {exact_alt}")

    # ----------------------------------------------------------
    # 1️⃣ TRY EXACT MATCH
    # ----------------------------------------------------------
    if os.path.exists(exact_expected):
        print(f"✅ Exact match found (expected): {exact_expected}")
        print("==============================\n")
        return send_from_directory(pdb_dir_expected, f"{core}.pdb")

    if os.path.exists(exact_alt):
        print(f"✅ Exact match found (alt): {exact_alt}")
        print("==============================\n")
        return send_from_directory(pdb_dir_alt, f"{core}.pdb")

    # ----------------------------------------------------------
    # 2️⃣ TRY _1 VARIANT
    # ----------------------------------------------------------
    var1_expected = os.path.join(pdb_dir_expected, f"{core_no_variant}_1.pdb")
    var1_alt = os.path.join(pdb_dir_alt, f"{core_no_variant}_1.pdb")

    print(f"🔎 Checking variant _1:")
    print(f"    → {var1_expected}")
    print(f"    → {var1_alt}")

    if os.path.exists(var1_expected):
        print(f"🔁 Variant _1 found (expected): {var1_expected}")
        print("==============================\n")
        return send_from_directory(pdb_dir_expected, f"{core_no_variant}_1.pdb")

    if os.path.exists(var1_alt):
        print(f"🔁 Variant _1 found (alt): {var1_alt}")
        print("==============================\n")
        return send_from_directory(pdb_dir_alt, f"{core_no_variant}_1.pdb")

    # ----------------------------------------------------------
    # 3️⃣ TRY ANY VARIANT: <base>_<n>.pdb
    # ----------------------------------------------------------
    print("🔍 Scanning directories for ANY variant...")

    variant_pattern = re.compile(rf"^{core_no_variant}_(\d+)\.pdb$", re.IGNORECASE)

    for scan_dir in [pdb_dir_expected, pdb_dir_alt]:
        if not os.path.isdir(scan_dir):
            continue

        for f in os.listdir(scan_dir):
            if variant_pattern.match(f):
                print(f"🔍 Found alternative variant: {f}   in {scan_dir}")
                print("==============================\n")
                return send_from_directory(scan_dir, f)

    # ----------------------------------------------------------
    # ❌ NONE FOUND
    # ----------------------------------------------------------
    print(f"❌ No PDB variant found for: {core_no_variant}")
    print("==============================\n")

    return (
        f"❌ PDB not found for '{filename}'\n"
        f"Tried:\n"
        f"  • {exact_expected}\n"
        f"  • {exact_alt}\n"
        f"  • {var1_expected}\n"
        f"  • {var1_alt}\n"
        f"  • Any {core_no_variant}_<n>.pdb\n",
        404,
    )





###LIGAND PAGE ROUTES####

@ligases_bp.route("/ligand-sasa/<recruiter_code>", methods=["GET"])
def get_ligand_sasa(recruiter_code):
    """
    Return SASA per-atom data and coordinates for a given recruiter.
    Includes atom-level exposure, coordinates, and atom type.
    """

    query = """
        SELECT 
            a.Ligase,
            a.pdb_id,
            a.Ligand,
            a.Residue_ID,
            a.atom_id,
            a.exact_atom,
            a.atom_type,
            a.x, a.y, a.z,
            a.Exposure_A2,
            m.smiles_atom_index,
            m.smile_atom
        FROM Ligase_Ligand_SASA_atoms AS a
        LEFT JOIN Ligase_Ligands_Smiles_3DMapped AS m
            ON a.Ligase = m.Ligase
           AND a.Ligand = m.Ligand
           AND a.atom_id = m.atom_id
        WHERE m.RECRUITER_CODE = ?
        ORDER BY a.atom_id ASC;
    """

    rows = query_db(query, [recruiter_code])
    return jsonify([dict(r) for r in rows])


# ============================================================
# 🧩 COMPOSITE LIGAND VISUALIZATION ROUTE
# ============================================================

# ---------------------------------------------
# 🔧 Helpers
# ---------------------------------------------
def _get_smiles_for_code(recruiter_code: str):
    """
    Resolve a recruiter code → SMILES.
    Priority:
      1) Ligase_SMILE_Codes
      2) Ligase_Chemical_Descriptors (fallback)
    """
    row = query_db(
        "SELECT SMILES FROM Ligase_SMILE_Codes WHERE RECRUITER_CODE = ? LIMIT 1;",
        [recruiter_code],
        one=True
    )
    if row:
        return row["SMILES"]

    row = query_db(
        "SELECT SMILES FROM Ligase_Chemical_Descriptors WHERE RECRUITER_CODE = ? LIMIT 1;",
        [recruiter_code],
        one=True
    )
    return row["SMILES"] if row else None


def _get_ligands_for_code(recruiter_code: str):
    """
    Recruiter code → set of Ligand IDs that appear in our SASA/3D mapping.
    Uses the robust SMILES bridge: SMILES → Metadata.Ligand → SASA tables.
    """
    # 1) SMILES for recruiter
    smiles = _get_smiles_for_code(recruiter_code)
    if not smiles:
        return [], None

    # 2) All ligands that carry that SMILES in metadata
    lig_rows = query_db(
        "SELECT DISTINCT Ligand FROM Ligase_Ligand_Metadata WHERE SMILES = ?;",
        [smiles]
    )
    ligands = [r["Ligand"] for r in lig_rows] if lig_rows else []

    return ligands, smiles


# ---------------------------------------------
# ✅ New: return SMILES for a recruiter code
# ---------------------------------------------
@ligases_bp.route("/recruiter-smiles/<recruiter_code>", methods=["GET"])
def recruiter_smiles(recruiter_code):
    smiles = _get_smiles_for_code(recruiter_code)
    if not smiles:
        return jsonify({"RECRUITER_CODE": recruiter_code, "SMILES": None}), 404
    return jsonify({"RECRUITER_CODE": recruiter_code, "SMILES": smiles})


# ---------------------------------------------
# ✅ New: RDKit render by recruiter code
# (keeps your existing /render-smiles/<path:smiles> untouched)
# ---------------------------------------------
@ligases_bp.route("/render-smiles-by-code/<recruiter_code>")
def render_smiles_by_code(recruiter_code):
    from rdkit import Chem
    from rdkit.Chem.Draw import rdMolDraw2D
    from flask import Response

    smiles = _get_smiles_for_code(recruiter_code)
    if not smiles:
        return Response("Unknown recruiter code", status=404, mimetype="text/plain")

    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return Response("Invalid SMILES", status=400, mimetype="text/plain")

        # ✅ Prepare molecule for clean drawing
        rdMolDraw2D.PrepareMolForDrawing(mol)

        # ✅ Create SVG drawer (transparent bg)
        drawer = rdMolDraw2D.MolDraw2DSVG(300, 300)
        opts = drawer.drawOptions()
        opts.addAtomIndices = True          # 👈 adds <text class="atom-#">
        opts.includeAtomTags = True         # 👈 keeps explicit per-atom IDs
        opts.explicitMethyl = True          # shows CH3 groups
        opts.addStereoAnnotation = False    # optional: cleaner look
        opts.setBackgroundColour((0, 0, 0, 0))  # transparent background

        # ✅ Optional: make carbons & hydrogens white, keep others standard
        white = (1.0, 1.0, 1.0)
        opts.atomPalette[6] = white  # carbon
        opts.atomPalette[1] = white  # hydrogen

        # ✅ Draw & export
        drawer.DrawMolecule(mol)
        drawer.FinishDrawing()
        svg = drawer.GetDrawingText()

        # ✅ Clean up RDKit’s fill/stroke for your dark theme
        svg = svg.replace('fill:#FFFFFF;fill-rule:evenodd;', 'fill:none;')
        svg = svg.replace('stroke:#000000', 'stroke:#FFFFFF')

        return Response(svg, mimetype="image/svg+xml")

    except Exception as e:
        return Response(f"Error rendering: {e}", status=500, mimetype="text/plain")



# ============================================================
# 🧩 FALLBACK: SMILES → Recruiter with SASA / PDB
# ============================================================
def _find_fallback_recruiter(recruiter_code: str):
    """
    If this recruiter lacks SASA or PDB data,
    find another recruiter with identical SMILES that has SASA.
    """
    # 1️⃣ Get this recruiter's SMILES
    smiles_row = query_db("""
        SELECT SMILES FROM Ligase_SMILE_Codes WHERE RECRUITER_CODE = ?;
    """, [recruiter_code], one=True)
    smiles = smiles_row["SMILES"] if smiles_row else None
    if not smiles:
        return None

    # 2️⃣ Find another recruiter with same SMILES and SASA data
    fallback_row = query_db("""
        SELECT DISTINCT s.RECRUITER_CODE
        FROM Ligase_SMILE_Codes AS s
        JOIN Ligase_Ligand_SASA_summary AS sa
          ON s.RECRUITER_CODE = sa.Ligand
        WHERE s.SMILES = ? LIMIT 1;
    """, [smiles], one=True)

    return fallback_row["RECRUITER_CODE"] if fallback_row else None


def _pdb_filename_candidates(pdb_id, ligand, variant=None):
    """Return variant-aware candidate PDB filenames for a mapping row."""
    base = f"{str(pdb_id or '').strip().upper()}_{str(ligand or '').strip().upper()}"
    candidates = []

    variant_text = "" if variant in (None, "", 0, "0") else str(variant).strip()
    if variant_text:
        candidates.append(f"{base}_{variant_text}.pdb")

    candidates.append(f"{base}.pdb")

    if variant_text in {"", "1"}:
        candidates.append(f"{base}_1.pdb")

    for n in range(2, 10):
        if str(n) != variant_text:
            candidates.append(f"{base}_{n}.pdb")

    seen = set()
    ordered = []
    for candidate in candidates:
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(candidate)
    return ordered


def _resolve_pdb_filename(ligase, pdb_id, ligand, variant=None):
    """Resolve the effective PDB filename from local files or the remote RANDY listing."""
    ligase = str(ligase or "").strip()
    pdb_id = str(pdb_id or "").strip().upper()
    ligand = str(ligand or "").strip().upper()
    candidates = _pdb_filename_candidates(pdb_id, ligand, variant)

    if randy_client.remote_enabled():
        try:
            filenames = randy_client.get_json(f"ligase-pdbs/{randy_client.quote_part(ligase)}")
        except Exception as exc:
            current_app.logger.warning(
                "Remote PDB listing failed for recruiter lookup: ligase=%s exc=%s",
                ligase,
                type(exc).__name__,
            )
            return None

        if not isinstance(filenames, list):
            return None

        by_lower = {
            str(name).strip().lower(): str(name).strip()
            for name in filenames
            if isinstance(name, str) and str(name).strip()
        }
        for candidate in candidates:
            match = by_lower.get(candidate.lower())
            if match:
                return match

        base = f"{pdb_id}_{ligand}"
        pattern = re.compile(rf"^{re.escape(base)}(?:_\d+)?\.pdb$", re.IGNORECASE)
        for name in sorted(by_lower.values(), key=str.lower):
            if pattern.fullmatch(name):
                return name
        return None

    pdb_dir = os.path.join("Ligases", ligase, "PDB")
    for candidate in candidates:
        if os.path.exists(os.path.join(pdb_dir, candidate)):
            return candidate

    if os.path.isdir(pdb_dir):
        base = f"{pdb_id}_{ligand}"
        pattern = re.compile(rf"^{re.escape(base)}(?:_\d+)?\.pdb$", re.IGNORECASE)
        for name in sorted(os.listdir(pdb_dir), key=str.lower):
            if pattern.fullmatch(name):
                return name

    return None


# ============================================================
# ✅ Unified visual payload (composite-key aware, auto-fallback)
# ============================================================
from flask import render_template

@ligases_bp.route("/ligand-visual/<recruiter_code>", methods=["GET"])
def get_ligand_visual(recruiter_code):
    """
    Return unified ligand visualization payload:
      • Chemical descriptor data
      • Metadata (name, SMILES, ligand ID)
      • SASA summary (%Exposed, %Buried)
      • Atom-level SASA + 3D coordinates
      • If missing SASA or PDB data → render missing_data.html
    """

    recruiter_code = str(recruiter_code or "").strip().upper()
    backend_mode = "remote" if randy_client.remote_enabled() else "local"

    try:
        desc = query_db(
            "SELECT * FROM Ligase_Chemical_Descriptors WHERE RECRUITER_CODE = ?;",
            [recruiter_code], one=True
        )
        descriptor = dict(desc) if desc else {}

        key_row = query_db("""
            SELECT Ligase, PDB_ID AS pdb_id, Ligand, Variant
            FROM Ligase_Ligands_Smiles_3DMapped
            WHERE RECRUITER_CODE = ?
            LIMIT 1;
        """, [recruiter_code], one=True)

        if not key_row:
            current_app.logger.warning(
                "Ligand visual missing composite key: code=%s backend=%s",
                recruiter_code,
                backend_mode,
            )
            return jsonify({
                "ok": False,
                "error": "No composite key found.",
                "recruiter_code": recruiter_code,
                "backend_mode": backend_mode,
            }), 404

        ligase = key_row["Ligase"]
        pdb_id = key_row["pdb_id"]
        ligand = key_row["Ligand"]
        variant = key_row["Variant"] or 1

        sm_row = query_db("""
            SELECT SMILES
            FROM Recruiter_SMILES_Map
            WHERE RECRUITER_CODE = ?
            LIMIT 1;
        """, [recruiter_code], one=True)
        canonical_smiles = sm_row["SMILES"] if sm_row else descriptor.get("SMILES")

        metadata = {
            "SMILES": canonical_smiles,
            "Ligand": ligand,
            "PDB_ID": pdb_id,
            "Ligase": ligase,
            "Variant": variant,
        }

        print(f"🔑 [CompositeKey] {recruiter_code} → Ligase={ligase}, PDB={pdb_id}, Ligand={ligand}, Variant={variant}")

        residue_row = query_db("""
            SELECT Residue_ID
            FROM Ligase_Ligand_SASA_summary
            WHERE Ligase=? AND pdb_id=? AND Ligand=? AND (Variant=? OR Variant IS NULL)
            LIMIT 1;
        """, [ligase, pdb_id, ligand, variant], one=True)
        residue_id = residue_row["Residue_ID"] if residue_row else None

        sasa_summary_row = query_db("""
            SELECT *
            FROM Ligase_Ligand_SASA_summary
            WHERE Ligase=? AND pdb_id=? AND Ligand=?
            AND (Residue_ID=? OR ? IS NULL)
            AND (Variant=? OR Variant IS NULL)
            LIMIT 1;
        """, [ligase, pdb_id, ligand, residue_id, residue_id, variant], one=True)
        sasa_summary = dict(sasa_summary_row) if sasa_summary_row else {}

        sasa_atoms_rows = query_db("""
            SELECT *
            FROM Ligase_Ligand_SASA_atoms
            WHERE Ligase=? AND pdb_id=? AND Ligand=?
            AND (Residue_ID=? OR ? IS NULL)
            AND (Variant=? OR Variant IS NULL)
            ORDER BY atom_id ASC;
        """, [ligase, pdb_id, ligand, residue_id, residue_id, variant])
        sasa_atoms = [dict(r) for r in sasa_atoms_rows]



        # ------------------------------------------------------------------
        # 🧱 STEP 4: Validate PDB availability in the active backend
        # ------------------------------------------------------------------
        pdb_file = _resolve_pdb_filename(ligase, pdb_id, ligand, variant)
        pdb_missing = not bool(pdb_file)
        pdb_path = f"/Ligases/{ligase}/PDB/{pdb_file}" if pdb_file else None

        # ------------------------------------------------------------------
        # 🚨 STEP 5: Missing data fallback
        # ------------------------------------------------------------------
        missing_critical = (
            not sasa_summary or
            not sasa_atoms or
            pdb_missing
        )

        if missing_critical:
            current_app.logger.warning(
                "Ligand visual missing critical data: code=%s backend=%s has_summary=%s has_atoms=%s has_pdb=%s",
                recruiter_code,
                backend_mode,
                bool(sasa_summary),
                bool(sasa_atoms),
                bool(pdb_file),
            )
            return jsonify({
                "ok": False,
                "error": "Missing SASA or PDB data.",
                "recruiter_code": recruiter_code,
                "backend_mode": backend_mode,
                "has_sasa_summary": bool(sasa_summary),
                "has_sasa_atoms": bool(sasa_atoms),
                "has_pdb": bool(pdb_file),
            }), 411
        
        
        # ------------------------------------------------------------------
        # 🎨 STEP 8: Generate 2D SASA SVG on the fly (no saved file needed)
        # ------------------------------------------------------------------
        sasa_svg = None
        try:
            if sasa_atoms:
                # Extract coordinates and normalize to 0-100%
                xs = [a["x"] for a in sasa_atoms]
                ys = [a["y"] for a in sasa_atoms]
                expos = [a.get("Exposure_A2", 0) for a in sasa_atoms]
                minx, maxx = min(xs), max(xs)
                miny, maxy = min(ys), max(ys)
                minexp, maxexp = min(expos), max(expos)
                width, height = 400, 400

                svg_parts = [
                    f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
                    '<rect width="100%" height="100%" fill="#0f172a"/>'
                ]
                for a in sasa_atoms:
                    # normalize coordinates
                    cx = ((a["x"] - minx) / (maxx - minx)) * width
                    cy = ((a["y"] - miny) / (maxy - miny)) * height
                    color = sasa_color_for_exposure(a.get("Exposure_A2"))

                    if color is None:
                        continue

                    r, g, b = [int(c * 255) for c in color]
                    svg_parts.append(
                        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" fill="rgb({r},{g},{b})" />'
                    )

                svg_parts.append("</svg>")
                sasa_svg = "".join(svg_parts)
                print(f"🧬 Generated dynamic SASA SVG for recruiter {recruiter_code}")
            else:
                print(f"⚠️ No atom-level SASA data available → skipping 2D SVG generation.")
        except Exception as e:
            print(f"⚠️ Failed to generate 2D SASA SVG for {recruiter_code}: {e}")
            sasa_svg = None




    

        # ------------------------------------------------------------------
        # 🎁 STEP 6: Return full JSON payload if complete
        # ------------------------------------------------------------------
        print(f"✅ Successfully built visual payload for {recruiter_code}")
        return jsonify({
            "ok": True,
            "recruiter_code": recruiter_code,
            "descriptor": descriptor,
            "metadata": metadata,
            "sasa_summary": sasa_summary,
            "sasa_atoms": sasa_atoms,
            "pdb_path": pdb_path,
            "pdb_file": pdb_file,
            "pdb_missing": pdb_missing,
            "sasa_svg": sasa_svg,  # ⬅ ADD THIS

        })

    except Exception as e:
        current_app.logger.exception(
            "Ligand visual fatal error: code=%s backend=%s exc=%s",
            recruiter_code,
            backend_mode,
            type(e).__name__,
        )
        return jsonify({
            "ok": False,
            "error": "ligand-visual-failed",
            "recruiter_code": recruiter_code,
            "backend_mode": backend_mode,
            "exception_type": type(e).__name__,
        }), 500



# ============================================================
# 🧩 STATIC SDF FILE SERVING  (SMART VARIANT RESOLUTION)
# ============================================================
@ligases_bp.route("/render-sdf/<ligase>/<path:filename>", methods=["GET"])
def serve_sdf_file(ligase, filename):
    """
    Serve .sdf files from Ligases/<Ligase>/SDF_4Download/

    Smart resolution:
    - Try exact match      (4W9L_3JJ.sdf)
    - If missing, try _1   (4W9L_3JJ_1.sdf)
    - If still missing, try any variant dynamically
    """
    try:
        normalized_filename = normalize_sdf_filename(filename)
    except ValueError as exc:
        current_app.logger.warning(
            "SDF filename normalization rejected: ligase=%s original=%s exc=%s",
            ligase,
            filename,
            type(exc).__name__,
        )
        return jsonify({"ok": False, "error": str(exc)}), 400

    if randy_client.remote_enabled():
        attempted_filenames = []
        for candidate_filename in candidate_sdf_filenames(filename):
            attempted_filenames.append(candidate_filename)
            remote_path = (
                f"file/sdf/{randy_client.quote_part(ligase)}/"
                f"{randy_client.quote_path(candidate_filename)}"
            )
            try:
                return randy_client.proxy_file(
                    remote_path,
                    mimetype="chemical/x-mdl-sdfile",
                )
            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else 502
                if status_code == 404:
                    continue
                current_app.logger.warning(
                    "Remote SDF proxy failed: ligase=%s original=%s attempted=%s status=%s exc=%s",
                    ligase,
                    filename,
                    candidate_filename,
                    status_code,
                    type(exc).__name__,
                )
                return jsonify({
                    "ok": False,
                    "error": "Remote SDF request failed.",
                    "ligase": ligase,
                    "filename": candidate_filename,
                }), status_code
            except Exception as exc:
                current_app.logger.warning(
                    "Remote SDF proxy unexpected failure: ligase=%s original=%s attempted=%s exc=%s",
                    ligase,
                    filename,
                    candidate_filename,
                    type(exc).__name__,
                )
                return jsonify({
                    "ok": False,
                    "error": "Remote SDF proxy failed.",
                    "ligase": ligase,
                    "filename": candidate_filename,
                }), 502

        current_app.logger.warning(
            "Remote SDF proxy failed: ligase=%s original=%s normalized=%s attempted=%s status=404 exc=HTTPError",
            ligase,
            filename,
            normalized_filename,
            attempted_filenames,
        )
        return jsonify({
            "ok": False,
            "error": "Remote SDF request failed.",
            "ligase": ligase,
            "filename": normalized_filename,
            "attempted": attempted_filenames,
        }), 404

    from flask import send_from_directory
    import os
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sdf_dir = os.path.join(base_dir, "Ligases", ligase, "SDF_4Download")

    # Core name (strip normalized .sdf suffix)
    core = os.path.splitext(normalized_filename)[0]
    core_no_variant = re.sub(r"_\d+$", "", core)  # strip trailing _1 if present

    # Expected filenames:
    primary_sdf = f"{core_no_variant}.sdf"         # 4W9L_3JJ.sdf
    variant_sdf = f"{core_no_variant}_1.sdf"       # 4W9L_3JJ_1.sdf

    primary_path = os.path.join(sdf_dir, primary_sdf)
    variant_path = os.path.join(sdf_dir, variant_sdf)

    print("\n==============================")
    print(f"🧪 [SDF Route] ligase={ligase}, filename={filename}, normalized={normalized_filename}")
    print(f"📂 sdf_dir: {sdf_dir}")
    print(f"🔎 core_no_variant = {core_no_variant}")
    print("==============================")

    # 1) Try exact match
    if os.path.exists(primary_path):
        print(f"✅ Exact SDF found: {primary_path}")
        return send_from_directory(sdf_dir, primary_sdf, as_attachment=True)

    # 2) Try the _1 fallback
    if os.path.exists(variant_path):
        print(f"🔁 Variant SDF found: {variant_path}")
        return send_from_directory(sdf_dir, variant_sdf, as_attachment=True)

    # 3) FINAL: Scan directory for ANY matching variant (e.g. _2, _3)
    pattern = re.compile(rf"^{core_no_variant}_(\d+)\.sdf$", re.IGNORECASE)
    for f in os.listdir(sdf_dir):
        if pattern.match(f):
            print(f"🔍 Found alternative variant: {f}")
            return send_from_directory(sdf_dir, f, as_attachment=True)

    print(f"❌ No matching SDF for {core_no_variant}")
    return (f"SDF file not found for {ligase}/{core_no_variant}", 404)


@ligases_bp.route("/recruiter-by-pdb", methods=["GET"])
def get_recruiter_by_pdb():
    pdb_id = request.args.get("pdb_id")
    ligand = request.args.get("ligand")
    variant = request.args.get("variant", "").replace(".pdb", "").replace("_", "")

    row = query_db("""
        SELECT RECRUITER_CODE
        FROM Ligase_Ligands_Smiles_3DMapped
        WHERE PDB_ID = ? AND Ligand = ? COLLATE NOCASE
        LIMIT 1
    """, (pdb_id, ligand), one=True)

    if row:
        return jsonify(dict(row))
    return jsonify({"error": "No recruiter found"}), 404



@ligases_bp.route("/global-stats", methods=["GET"])
def global_stats():
    """
    Returns high-level dataset metrics for About page visualization.
    """
    try:
        # ========== Structural Counts ==========
        ligase_count = query_db("SELECT COUNT(DISTINCT Ligase) AS n FROM Ligase_Scaffold_Data;", one=True)["n"]
        ligand_count = query_db("SELECT COUNT(DISTINCT Ligand) AS n FROM Ligase_Ligand_SASA_summary;", one=True)["n"]
        structure_count = query_db("SELECT COUNT(DISTINCT pdb_id) AS n FROM Ligase_Ligand_SASA_summary;", one=True)["n"]
        scaffold_count = query_db("SELECT COUNT(DISTINCT Scaffold_ID) AS n FROM Ligase_Scaffold_Data;", one=True)["n"]

        # ========== Scientific Metrics ==========
        avg_shannon = query_db("SELECT AVG(Shannon_Diversity_Index) AS val FROM Ligase_Scaffold_Data;", one=True)["val"] or 0
        mean_connectivity = query_db("SELECT AVG(Ligase_Scaffold_Connectivity) AS val FROM Ligase_Scaffold_Data;", one=True)["val"] or 0
        median_bertz = query_db("SELECT BertzCT FROM Ligase_Chemical_Descriptors WHERE BertzCT IS NOT NULL ORDER BY BertzCT;",)
        median_bertz_val = median_bertz[len(median_bertz)//2]["BertzCT"] if median_bertz else 0
        avg_qed = query_db("SELECT AVG(QED) AS val FROM Ligase_Chemical_Descriptors;", one=True)["val"] or 0
        percent_lipinski = query_db("SELECT (SUM(Lipinski_Pass)*100.0/COUNT(*)) AS val FROM Ligase_Chemical_Descriptors;", one=True)["val"] or 0
        avg_norm_div = query_db("SELECT AVG(Normalized_Diversity) AS val FROM Ligase_Scaffold_Data;", one=True)["val"] or 0

        # ========== Top Ligase ==========
        top_row = query_db("""
            SELECT Ligase, SUM(Recruiter_Count) AS total
            FROM Ligase_Scaffold_Data
            GROUP BY Ligase
            ORDER BY total DESC LIMIT 1;
        """, one=True)
        top_ligase = top_row["Ligase"] if top_row else "N/A"

        return jsonify({
            "structures": structure_count,
            "ligases": ligase_count,
            "ligands": ligand_count,
            "total_scaffolds": scaffold_count,
            "avg_shannon": round(avg_shannon, 2),
            "mean_connectivity": round(mean_connectivity, 2),
            "median_bertz": round(median_bertz_val, 1),
            "avg_qed": round(avg_qed, 2),
            "percent_lipinski": round(percent_lipinski, 1),
            "avg_norm_div": round(avg_norm_div, 2),
            "top_ligase": top_ligase
        })
    except Exception as e:
        print(f"⚠️ Error generating global stats: {e}")
        return jsonify({})



def sasa_color_for_exposure(exp):
    """
    Warhead-consistent SASA coloring.

    GREEN:  15–24 Å²
    YELLOW: 24–34 Å²
    RED:    >=34 Å²

    Below 15 Å² or invalid values are not colored.
    """
    try:
        exp = float(exp)
    except (TypeError, ValueError):
        return None

    if exp < 15:
        return None

    if exp >= 34:
        return (1.0, 0.25, 0.25)   # red

    if exp >= 24:
        return (0.95, 0.85, 0.10)  # yellow

    return (0.15, 0.85, 0.20)      # green


@ligases_bp.route("/render-2d-sasa/<recruiter_code>", methods=["GET"])
def render_2d_sasa(recruiter_code):
    print("\n==========================")
    print(f"📥 [2D-SASA] Incoming request for: {recruiter_code}")
    print("==========================")

    try:
        # 1) Get canonical PDB-matched SMILES
        row = query_db("""
            SELECT SMILES
            FROM Recruiter_SMILES_Map
            WHERE RECRUITER_CODE = ?
            LIMIT 1;
        """, [recruiter_code], one=True)

        if not row:
            print("⚠️ No SMILES row found in Recruiter_SMILES_Map")
            return "<svg><!-- no descriptor row, fallback --></svg>", 200, {
                "Content-Type": "image/svg+xml"
            }

        smiles = row["SMILES"]
        print(f"🧪 Using SMILES: {smiles}")

        from rdkit import Chem
        from rdkit.Chem import rdDepictor
        from rdkit.Chem.Draw import rdMolDraw2D

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return "<svg><!-- bad smiles --></svg>", 400, {
                "Content-Type": "image/svg+xml"
            }

        Chem.SanitizeMol(mol)
        rdDepictor.Compute2DCoords(mol)

        # 2) Fetch composite key
        key_row = query_db("""
            SELECT Ligase, pdb_id, Ligand, Variant
            FROM Ligase_Ligands_Smiles_3DMapped
            WHERE RECRUITER_CODE = ?
            LIMIT 1;
        """, [recruiter_code], one=True)

        if not key_row:
            print(f"⚠️ No composite key found for {recruiter_code}")
            return "<svg><!-- no composite key --></svg>", 404, {
                "Content-Type": "image/svg+xml"
            }

        ligase = key_row["Ligase"]
        pdb_id = key_row["pdb_id"]
        ligand = key_row["Ligand"]
        variant = key_row["Variant"]

        print(f"🔑 Composite key → {ligase}, {pdb_id}, {ligand}, {variant}")

        # 3) Pull atom-level SASA mapped to RDKit SMILES atom index
        sasa_rows = query_db("""
            SELECT DISTINCT
                m.smiles_atom_index,
                a.Exposure_A2
            FROM Ligase_Ligands_Smiles_3DMapped AS m
            JOIN Ligase_Ligand_SASA_atoms AS a
              ON m.Ligase = a.Ligase
             AND m.pdb_id = a.pdb_id
             AND m.Ligand = a.Ligand
             AND m.Variant = a.Variant
             AND ABS(m.x - a.x) < 0.1
             AND ABS(m.y - a.y) < 0.1
             AND ABS(m.z - a.z) < 0.1
            WHERE m.RECRUITER_CODE = ?
              AND m.smiles_atom_index IS NOT NULL
              AND a.Exposure_A2 IS NOT NULL
        """, [recruiter_code])

        print(f"📊 SASA rows matched by coord: {len(sasa_rows)}")

        # 4) Build RDKit highlight maps using WARHEAD thresholds
        highlight_atoms = []
        highlight_colors = {}
        highlight_radii = {}

        for r in sasa_rows:
            idx = r["smiles_atom_index"]
            exp = r["Exposure_A2"]

            try:
                idx = int(idx)
            except (TypeError, ValueError):
                continue

            color = sasa_color_for_exposure(exp)

            # Below 15 Å² or invalid values are intentionally ignored.
            if color is None:
                continue

            highlight_atoms.append(idx)
            highlight_colors[idx] = color
            highlight_radii[idx] = 0.45

        # Remove duplicate atom indices while preserving color/radius dictionaries
        highlight_atoms = sorted(set(highlight_atoms))

        print(f"🎨 SASA-highlighted atoms: {len(highlight_atoms)}")
        print("   GREEN  = 15–24 Å²")
        print("   YELLOW = 24–34 Å²")
        print("   RED    = >=34 Å²")
        print("   <15 Å² = ignored / normal")

        # 5) Draw SVG
        drawer = rdMolDraw2D.MolDraw2DSVG(400, 400)
        opts = drawer.drawOptions()
        opts.setBackgroundColour((0, 0, 0, 0))

        # Optional but useful for debugging/mapping
        # opts.addAtomIndices = True

        drawer.DrawMolecule(
            mol,
            highlightAtoms=highlight_atoms,
            highlightAtomColors=highlight_colors,
            highlightAtomRadii=highlight_radii
        )

        drawer.FinishDrawing()
        svg = drawer.GetDrawingText()

        # Dark-theme cleanup
        svg = svg.replace("stroke:#000000", "stroke:#FFFFFF")
        svg = svg.replace("fill:#000000", "fill:#FFFFFF")

        return svg, 200, {"Content-Type": "image/svg+xml"}

    except Exception as e:
        print(f"❌ 2D-SASA ERROR: {e}")
        import traceback
        traceback.print_exc()
        return f"<svg><!-- error: {e} --></svg>", 500, {
            "Content-Type": "image/svg+xml"
        }





@ligases_bp.route("/sasa-atoms/<recruiter_code>", methods=["GET"])
def sasa_atoms(recruiter_code):
    try:
        # Step 1: Get ligand mapping (Ligase, pdb, Ligand, Variant)
        key = query_db("""
            SELECT Ligase, pdb_id, Ligand, Variant
            FROM Ligase_Ligands_Smiles_3DMapped
            WHERE RECRUITER_CODE = ?
            LIMIT 1;
        """, [recruiter_code], one=True)

        if not key:
            return jsonify({"error": "No mapping found"}), 404

        ligase  = key["Ligase"]
        pdb     = key["pdb_id"]
        ligand  = key["Ligand"]
        variant = key["Variant"]

        # Step 2: Get atom-level SASA
        atoms = query_db("""
            SELECT atom_id, atom_type, Exposure_A2, x, y, z
            FROM Ligase_Ligand_SASA_atoms
            WHERE Ligase=? AND pdb_id=? AND Ligand=? AND Variant=?;
        """, [ligase, pdb, ligand, variant])

        return jsonify({"atoms": atoms})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@ligases_bp.route("/sasa-full/<recruiter_code>", methods=["GET"])
def sasa_full(recruiter_code):
    print("\n\n==============================")
    print("📥 [SASA-FULL] Request:", recruiter_code)
    print("==============================\n")

    try:
        # ----------------------------------------------
        # STEP 1 — Get full composite key from 3DMapped
        # ----------------------------------------------
        key = query_db("""
            SELECT Ligase, pdb_id, Ligand, Variant
            FROM Ligase_Ligands_Smiles_3DMapped
            WHERE RECRUITER_CODE = ?
            LIMIT 1;
        """, [recruiter_code], one=True)

        if not key:
            return jsonify({"error": "No mapping found"}), 404

        ligase  = key["Ligase"]
        pdb_id  = key["pdb_id"]
        ligand  = key["Ligand"]
        variant = key["Variant"]

        # ----------------------------------------------
        # STEP 2 — SASA SUMMARY (single row)
        # ----------------------------------------------
        summary = query_db("""
            SELECT *
            FROM Ligase_Ligand_SASA_summary
            WHERE Ligase = ?
              AND pdb_id = ?
              AND Ligand = ?
              AND Variant = ?
            LIMIT 1;
        """, [ligase, pdb_id, ligand, variant], one=True)

        if not summary:
            summary = {}

        # ----------------------------------------------
        # STEP 3 — Full SASA atom table
        # ----------------------------------------------
        atoms = query_db("""
            SELECT atom_index, atom_id, atom_type,
                   x, y, z,
                   Exposure_A2, Residue_ID
            FROM Ligase_Ligand_SASA_atoms
            WHERE Ligase = ?
              AND pdb_id = ?
              AND Ligand = ?
              AND Variant = ?
            ORDER BY atom_index ASC;
        """, [ligase, pdb_id, ligand, variant])

        print(f"🧬 SASA atoms fetched: {len(atoms)}")

        # ----------------------------------------------
        # STEP 4 — Return unified payload
        # ----------------------------------------------
        return jsonify({
            "recruiter_code": recruiter_code,
            "Ligase": ligase,
            "pdb_id": pdb_id,
            "Ligand": ligand,
            "Variant": variant,
            "summary": {k: summary[k] for k in summary.keys()} if summary else {},
            "atoms": atoms
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500





# =====================================================================
# 🧬 ELiAH DATABASE — Ligase Expression Explorer
# =====================================================================

# === ELiAH API Routes ===
# ======================================
# 🧬 ELiAH API ROUTES
# ======================================
@ligases_bp.route("/eliah/ligases")
def eliah_ligase_list():
    """
    Return all ligase names from ligase_list table.
    Automatically handles wide-format tables (columns = ligases).
    """
    try:
        print("=== ELiAH Ligase Debug ===")

        cols = _eliah_table_columns("ligase_list")
        if not cols:
            return jsonify({"error": "Table 'ligase_list' not found or empty."}), 404

        ligases = []
        for name in cols:
            if name.lower() not in ("gene", "id", "index", ""):
                ligases.append(name)

        print(f"Detected {len(ligases)} ligases:", ligases[:10])

        # Get total row count (not critical for dropdown)
        try:
            count_row = query_eliah_db("SELECT COUNT(*) AS total FROM ligase_list;")
            total = (
                count_row[0]["total"]
                if count_row and isinstance(count_row[0], dict)
                else (count_row[0][0] if count_row else 0)
            )
        except Exception:
            total = 0

        return jsonify({
            "total_rows": total,
            "ligases": ligases
        })

    except Exception as e:
        import traceback
        print("❌ /eliah/ligases ERROR:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



@ligases_bp.route("/eliah/genes")
def eliah_genes():
    """Return genes associated with a given ligase (no averaging)."""
    ligase = request.args.get("ligase", "").strip()
    if not ligase:
        return jsonify({"error": "Missing ?ligase parameter"}), 400

    try:
        # --- Detect ligase_list schema
        colnames = [name.lower() for name in _eliah_table_columns("ligase_list")]
        genes = []

        # Narrow layout: ligase_list(ligase, gene)
        if {"ligase", "gene"}.issubset(set(colnames)):
            rows = query_eliah_db(
                "SELECT DISTINCT gene FROM ligase_list WHERE ligase = ? AND gene IS NOT NULL;",
                (ligase,)
            )
            genes = [r["gene"] if isinstance(r, dict) else r[0] for r in rows]

        # Wide/pivot layout: one column per ligase (e.g. ANKIB1)
        elif ligase.lower() in colnames:
            q = f"SELECT [{ligase}] AS gene FROM ligase_list WHERE [{ligase}] IS NOT NULL;"
            rows = query_eliah_db(q)
            genes = [r["gene"] if isinstance(r, dict) else r[0] for r in rows]

        else:
            return jsonify({"error": f"Ligase '{ligase}' not found in ligase_list."}), 404

        # Normalize output keys for frontend
        result = [{"Gene": g} for g in sorted(set(genes))]
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ligases_bp.route("/eliah/expression")
def eliah_expression():
    """Return normalized Z-scores for a specific gene."""
    gene = request.args.get("gene", "")
    if not gene:
        return jsonify({"error": "Missing ?gene parameter"}), 400

    try:
        q = """
        SELECT Sample, Z_score
        FROM gene_expression_normalized
        WHERE Gene = ?
        ORDER BY Sample ASC;
        """
        rows = query_eliah_db(q, (gene,))
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@ligases_bp.route("/eliah/tissues")
def eliah_tissues():
    """Return total sample counts per tissue group (with readable labels)."""
    try:
        q = """
        SELECT Tissgrp AS tissue, COUNT(*) AS count
        FROM sample_tissue
        GROUP BY Tissgrp
        ORDER BY count DESC;
        """
        rows = query_eliah_db(q)

        # Map of shorthand → human-readable labels
        label_map = {
            "Muscle_S": "Skeletal Muscle",
            "Whole_B": "Whole Blood",
            "Thyroid": "Thyroid",
            "Lung": "Lung",
            "Heart_Atr": "Heart (Atrium)",
            "Heart_Lef": "Heart (Left Ventricle)",
            "Colon_Tra": "Colon (Transverse)",
            "Colon_Sigmoid": "Colon (Sigmoid)",
            "Pancreas": "Pancreas",
            "Stomach": "Stomach",
            # Add more mappings as needed
        }

        # Add readable field
        for r in rows:
            if isinstance(r, dict):
                r["label"] = label_map.get(r["tissue"], r["tissue"])
            else:
                r = list(r) + [label_map.get(r[0], r[0])]

        return jsonify(rows)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ligases_bp.route("/eliah/tissue_profile")
def get_tissue_profile():
    gene = request.args.get("gene", "").strip()
    tissue = request.args.get("tissue", "").strip()

    # Debugging log to trace the incoming gene and tissue
    print(f"🧬 [DEBUG] Incoming request → gene: {gene}, tissue: {tissue}")

    if not gene:
        return jsonify([])

    if tissue:
        # 🔬 Return all per-sample Z-scores for a single tissue + gene
        query = """
            SELECT Sample, Gene, Z_score, Tissgrp
            FROM gene_expression_normalized
            WHERE Gene = ?
              AND Tissgrp = ?
            ORDER BY Sample
            """
        params = (gene, tissue)
    else:
        # 🌎 Return all tissues (All button)
        query = """
            SELECT Sample, Gene, Z_score, Tissgrp
            FROM gene_expression_normalized
            WHERE Gene = ?
            ORDER BY Tissgrp, Sample
            """
        params = (gene,)

    rows = query_eliah_db(query, params)

    # Debugging log to trace the response data
    print(f"🧬 [DEBUG] Response rows → {len(rows)} rows for gene: {gene}, tissue: {tissue}")

    return jsonify(rows)




@ligases_bp.route("/eliah/search")
def eliah_search():
    q = request.args.get("q", "").strip()
    tissues = [t for t in request.args.get("tissues", "").split(",") if t]

    # 🧩 Handle too-short input
    if len(q) < 2:
        return jsonify([])

    is_exact = len(q) <= 8 and q.isupper()

    # 🧠 Core query: join three summary tables
    query = """
        SELECT 
            a.Ligase,
            a.Tissgrp,
            ROUND(a.avg_z, 3) AS avg_z,
            ROUND(e.enrichment_z, 3) AS enrichment_z,
            ROUND(s.Specificity, 3) AS Specificity
        FROM ligase_tissue_avg AS a
        LEFT JOIN ligase_tissue_enrichment AS e 
            ON a.Ligase = e.Ligase AND a.Tissgrp = e.Tissgrp
        LEFT JOIN ligase_specificity_index AS s 
            ON a.Ligase = s.Ligase
        WHERE a.Ligase {} ? COLLATE NOCASE
    """.format("=" if is_exact else "LIKE")

    params = [q if is_exact else f"{q}%"]

    # 🧫 Optional tissue filtering
    if tissues:
        placeholders = ",".join(["?"] * len(tissues))
        query += f" AND a.Tissgrp IN ({placeholders})"
        params += tissues

    query += " ORDER BY a.avg_z DESC LIMIT 100;"

    try:
        rows = query_eliah_db(query, params)
    except sqlite3.DatabaseError as e:
        print("❌ Database error:", e)
        return jsonify({"error": "Database query failed"}), 500

    # 🧩 Return enriched JSON output
    results = [
        {
            "Ligase": r["Ligase"],
            "Tissue": r["Tissgrp"],
            "Mean_Zscore": r["avg_z"],
            "Enrichment_Z": r["enrichment_z"],
            "Specificity": r["Specificity"],
        }
        for r in rows
    ]
    return jsonify(results)



@ligases_bp.route("/eliah/autocomplete")
def eliah_autocomplete():
    q = request.args.get("q", "").strip().upper()
    if not q or len(q) < 2:
        return jsonify([])

    rows = query_eliah_db(
        "SELECT ANKIB1 AS Gene FROM ligase_list WHERE ANKIB1 LIKE ? LIMIT 10;",
        (f"{q}%",)
    )
    return jsonify([r["Gene"] for r in rows])



@ligases_bp.route("/eliah/expression_filter")
def expression_filter():
    """
    🔬 Expression Filter API
    Filters ligases by tissue type and Z-score range.
    Aggregates across samples (GROUP BY Ligase, Tissgrp)
    to return one averaged entry per gene–tissue pair.
    """

    tissue = request.args.get("tissue", "").strip()
    try:
        min_z = float(request.args.get("minZ", -1))
        max_z = float(request.args.get("maxZ", 1))
    except ValueError:
        return jsonify({"error": "Invalid Z-score parameters"}), 400

    # ⚡ Optional cached response for default all-tissue view
    if not tissue and min_z == -1 and max_z == 1:
        cache_file = "Ligases/CSVcache/default_all_tissues.json"
        if os.path.exists(cache_file):
            with open(cache_file) as f:
                try:
                    data = json.load(f)
                    return jsonify(data)
                except json.JSONDecodeError:
                    print("⚠️ Cache file is invalid JSON — skipping cache.")

    try:
        # --- SQL Query with proper aggregation ---
        if tissue:
            query = """
                SELECT 
                    avg.Ligase,
                    avg.Tissgrp,
                    ROUND(AVG(avg.avg_z), 3) AS avg_z,
                    ROUND(AVG(enrich.enrichment_z), 3) AS enrichment_z,
                    ROUND(AVG(spec.Specificity), 3) AS Specificity
                FROM ligase_tissue_avg AS avg
                LEFT JOIN ligase_tissue_enrichment AS enrich 
                    ON avg.Ligase = enrich.Ligase 
                    AND avg.Tissgrp = enrich.Tissgrp
                LEFT JOIN ligase_specificity_index AS spec 
                    ON avg.Ligase = spec.Ligase
                WHERE avg.Tissgrp = ?
                  AND avg.avg_z BETWEEN ? AND ?
                GROUP BY avg.Ligase, avg.Tissgrp
                HAVING AVG(avg.avg_z) BETWEEN ? AND ?
                ORDER BY AVG(avg.avg_z) DESC
                LIMIT 30000
            """
            params = (tissue, min_z, max_z, min_z, max_z)
        else:
            query = """
                SELECT 
                    avg.Ligase,
                    avg.Tissgrp,
                    ROUND(AVG(avg.avg_z), 3) AS avg_z,
                    ROUND(AVG(enrich.enrichment_z), 3) AS enrichment_z,
                    ROUND(AVG(spec.Specificity), 3) AS Specificity
                FROM ligase_tissue_avg AS avg
                LEFT JOIN ligase_tissue_enrichment AS enrich 
                    ON avg.Ligase = enrich.Ligase 
                    AND avg.Tissgrp = enrich.Tissgrp
                LEFT JOIN ligase_specificity_index AS spec 
                    ON avg.Ligase = spec.Ligase
                WHERE avg.avg_z BETWEEN ? AND ?
                GROUP BY avg.Ligase, avg.Tissgrp
                HAVING AVG(avg.avg_z) BETWEEN ? AND ?
                ORDER BY avg.Tissgrp, AVG(avg.avg_z) DESC
                LIMIT 30000
            """
            params = (min_z, max_z, min_z, max_z)

        rows = query_eliah_db(query, params)

        results = [dict(row) for row in rows]
        print(f"🧮 ExpressionFilter returned {len(results)} rows for tissue={tissue or 'ALL'} "
              f"(Z={min_z}–{max_z})")

        return jsonify(results)

    except Exception as e:
        print(f"⚠️ Expression filter error: {e}")
        return jsonify({"error": str(e)}), 500



# =======================================================================
# 🧬 Scaffold Network Full Page View
# =======================================================================
@ligases_bp.route("/scaffold-network-full")
def scaffold_network_full():
    """Render a full-page network visualization."""
    return render_template("scaffold_network_full.html")



@ligases_bp.route("/sasa-summary/<recruiter_code>", methods=["GET"])
def sasa_summary(recruiter_code):
    print("\n\n====================================")
    print(f"📥 [SASA-SUMMARY] Request for recruiter: {recruiter_code}")
    print("====================================\n")

    try:
        # 1) Composite key lookup
        key = query_db("""
            SELECT Ligase, pdb_id, Ligand, Variant
            FROM Ligase_Ligands_Smiles_3DMapped
            WHERE RECRUITER_CODE = ?
            LIMIT 1;
        """, [recruiter_code], one=True)

        if not key:
            return jsonify({"error": "No mapping found"}), 404

        ligase  = key["Ligase"]
        pdb     = key["pdb_id"]
        ligand  = key["Ligand"]
        variant = key["Variant"]

        # 2) Try summary table
        summary = query_db("""
            SELECT *
            FROM Ligase_Ligand_SASA_summary
            WHERE Ligase=? AND pdb_id=? AND Ligand=? AND Variant=?
            LIMIT 1;
        """, [ligase, pdb, ligand, variant], one=True)

        # 3) Fallback using atoms table (optional but safe)
        if not summary:
            fallback = query_db("""
                SELECT DISTINCT Residue_ID
                FROM Ligase_Ligand_SASA_atoms
                WHERE Ligase=? AND pdb_id=? AND Ligand=? AND Variant=?
                LIMIT 1;
            """, [ligase, pdb, ligand, variant], one=True)

            if fallback:
                summary = query_db("""
                    SELECT *
                    FROM Ligase_Ligand_SASA_summary
                    WHERE Ligase=? AND pdb_id=? AND Ligand=? AND Variant=? AND Residue_ID=?
                    LIMIT 1;
                """, [ligase, pdb, ligand, variant, fallback["Residue_ID"]], one=True)

        # 4) If STILL missing → return empty
        if not summary:
            return jsonify({
                "Total_atoms": None,
                "Exposed_atoms": None,
                "SASA_in_complex_A2": None,
                "Percent_Exposed": None,
                "Percent_Buried": None
            })

        # 5) Convert sqlite Row → dict and return
        return jsonify({k: summary[k] for k in summary.keys()})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500




# @ligases_bp.route("/scaffold/<recruiter_code>")
# def api_scaffold_for_recruiter(recruiter_code):
#     row = query_db("""
#         SELECT Scaffold_ID, Scaffold_SMILES
#         FROM Ligase_Recruiters_Scaffold
#         WHERE RECRUITER_CODE = ?
#         LIMIT 1;
#     """, [recruiter_code], one=True)

#     if not row:
#         return jsonify({"error": "Not found"}), 404

#     return jsonify(dict(row))







@ligases_bp.route("/scaffold/<recruiter_code>")
def api_scaffold_for_recruiter(recruiter_code):

    # 1️⃣ Check if this recruiter is in duplicate master map
    master_row = query_db("""
        SELECT MasterRecruiter
        FROM Recruiter_Master_Map
        WHERE RECRUITER_CODE = ?
        LIMIT 1;
    """, [recruiter_code], one=True)

    if master_row:
        master = (master_row["MasterRecruiter"] or "").strip().upper()

        # Case C — duplicate group with NO scaffold (master = BLANK)
        if master == "BLANK":
            return jsonify({"error": "NO_MASTER"}), 404

        # Case B — duplicate group WITH valid master
        if master != "":
            recruiter_code = master  # rewrite recruiter code
    
        # Case A — master_row exists but empty? (should not happen)
        # Fall through and continue normally

    # 2️⃣ Continue normal scaffold lookup
    row = query_db("""
        SELECT Scaffold_ID, Scaffold_SMILES
        FROM Ligase_Recruiters_Scaffold
        WHERE RECRUITER_CODE = ?
        LIMIT 1;
    """, [recruiter_code], one=True)

    if not row:
        return jsonify({"error": "Not found"}), 404

    return jsonify(dict(row))









@ligases_bp.route("/scaffolds/<scaffold_id>")
def scaffold_page(scaffold_id):
    # Fetch full scaffold info
    row = query_db("""
        SELECT DISTINCT Scaffold_ID, Scaffold_SMILES
        FROM Ligase_Recruiters_Scaffold
        WHERE Scaffold_ID = ?
    """, [scaffold_id], one=True)

    if not row:
        return "Scaffold not found", 404

    # Fetch all recruiters that share this scaffold (optional)
    recruiters = query_db("""
        SELECT RECRUITER_CODE, Ligase
        FROM Ligase_Recruiters_Scaffold
        WHERE Scaffold_ID = ?
        ORDER BY Ligase
    """, [scaffold_id])

    return render_template(
        "scaffold_page.html",
        scaffold=row,
        recruiters=[dict(r) for r in recruiters]
    )





def render_smiles_by_code(recruiter_code):
    from rdkit import Chem
    from rdkit.Chem.Draw import rdMolDraw2D
    from flask import Response

    smiles = _get_smiles_for_code(recruiter_code)
    if not smiles:
        return Response("Unknown recruiter code", status=404, mimetype="text/plain")

    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return Response("Invalid SMILES", status=400, mimetype="text/plain")

        # Prepare molecule
        rdMolDraw2D.PrepareMolForDrawing(mol)

        # Draw transparent 300×300 SVG
        drawer = rdMolDraw2D.MolDraw2DSVG(300, 300)
        opts = drawer.drawOptions()

        # === ATOM COLORS (custom E3 theme) ============================
        opts.atomPalette[6] = (1.0, 1.0, 1.0)        # Carbon → white
        opts.atomPalette[1] = (1.0, 1.0, 1.0)        # Hydrogen → white
        opts.atomPalette[7] = (0.13, 0.83, 0.93)     # Nitrogen → cyan (#22D3EE)
        opts.atomPalette[8] = (0.97, 0.44, 0.44)     # Oxygen → coral (#F87171)

        # === BOND COLORS (white) ======================================
        bond_white = (1.0, 1.0, 1.0)
        for bond in mol.GetBonds():
            idx = bond.GetIdx()
            opts.bondPalette[idx] = bond_white

        # === Clean background =========================================
        opts.setBackgroundColour((0, 0, 0, 0))       # Transparent

        # Optional drawing styling
        opts.addAtomIndices = False
        opts.includeAtomTags = False
        opts.explicitMethyl = True

        drawer.DrawMolecule(mol)
        drawer.FinishDrawing()
        svg = drawer.GetDrawingText()

        # RDKit still adds some white-fills → remove them
        svg = svg.replace("fill:#FFFFFF", "fill:none")
        svg = svg.replace("stroke:#000000", "stroke:#FFFFFF")

        # Also remove the <rect> background if any slipped through
        import re
        svg = re.sub(r"<rect.*?</rect>", "", svg, flags=re.DOTALL)

        return Response(svg, mimetype="image/svg+xml")

    except Exception as e:
        return Response(f"Error rendering: {e}", status=500, mimetype="text/plain")





def log_ligase_shipment(ip_address: str, **event_fields):
    """Compatibility wrapper for legacy shipment logging."""
    event = {
        "client_ip": str(ip_address or "").strip(),
        "source": event_fields.get("source", "convert_atom_to_v"),
        "status": event_fields.get("status", "success"),
        "backend_mode": "remote" if randy_client.remote_enabled() else "local",
        "session_id": str(event_fields.get("session_id", "") or "").strip(),
        "recruiter_code": str(event_fields.get("recruiter_code", "") or "").strip(),
        "skip_modify": bool(event_fields.get("skip_modify", False)),
        "metadata_json": event_fields.get("metadata_json") or {},
    }
    return shipment_store.record_shipment_event(event)


@ligases_bp.get("/shipped-count")
def shipped_count():
    return jsonify(shipment_store.get_shipment_count())




@ligases_bp.post("/convert_atom_to_v")
def convert_atom_to_v():
    from rdkit import Chem
    import uuid, csv, datetime
    import os
    import traceback

    print("\n==============================")
    print("🔥 [convert_atom_to_v] Incoming request...")
    print("==============================")

    try:
        # ---------------------------
        # LOAD INPUT FIELDS
        # ---------------------------
        data = request.get_json(silent=True) or {}
        sdf_text = data["sdf"]
        atom_index = int(data["atom_index"])
        recruiter = data.get("recruiter") or data.get("RECRUITER") or "UNKNOWN"
        skip_modify = bool(data.get("skip_modify", False))

        ip = request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0].strip()
        print(
            "📥 convert_atom_to_v payload "
            f"(has_sdf={bool(sdf_text)}, recruiter={recruiter}, atom_index={atom_index}, skip_modify={skip_modify})"
        )
        print(f"🌐 User IP parsed → {ip}")

        print(f"🔹 Recruiter: {recruiter}")
        print(f"🔹 atom_index: {atom_index}")
        print(f"🔹 skip_modify: {skip_modify}")

        # ---------------------------
        # PARSE MOLECULE
        # ---------------------------
        print("🧪 Parsing incoming SDF...")
        mol = Chem.MolFromMolBlock(sdf_text, sanitize=False)
        if mol is None:
            print("❌ RDKit could NOT parse SDF!!!")
            return jsonify({"error": "Unable to parse SDF"}), 400

        print("✅ SDF parsed successfully")

        # ORIGINAL SMILES
        try:
            original_smiles = Chem.MolToSmiles(mol)
        except:
            original_smiles = "ERROR_SMILES"

        print(f"🔹 Original SMILES: {original_smiles}")

        # ---------------------------
        # MODIFY OR SKIP
        # ---------------------------
        if skip_modify:
            print("⚠️ SKIPPING Vanadium modification → Sending unmodified ligand")
            modified = 0

        else:
            try:
                mol.GetAtomWithIdx(atom_index).SetAtomicNum(23)
                print(f"🧬 Converted atom index {atom_index} → Vanadium (23)")
                modified = 1
            except Exception as e:
                print(f"❌ Atom conversion failure: {e}")
                traceback.print_exc()
                return jsonify({"error": f"Atom conversion failed: {e}"}), 500

        # ---------------------------
        # WRITE OUTPUT SDF
        # ---------------------------
        new_sdf = Chem.MolToMolBlock(mol)
        session_id = str(uuid.uuid4())
        out_dir = "tmp_sessions"

        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{session_id}.sdf")

        with open(out_path, "w") as f:
            f.write(new_sdf)

        print(f"📄 SDF output written → {out_path}")
        print(f"📁 Full directory absolute path → {os.path.abspath(out_dir)}")

        # ---------------------------
        # COMPUTE NEW SMILES
        # ---------------------------
        try:
            converted_smiles = Chem.MolToSmiles(mol)
        except:
            converted_smiles = original_smiles

        print(f"🔹 Converted SMILES: {converted_smiles}")

        # ---------------------------
        # CSV LOGGING
        # ---------------------------
        csv_dir = "Ligases"
        csv_path = os.path.join(csv_dir, "converted-ligases-by-user.csv")

        try:
            print(f"📝 Preparing CSV log at → {csv_path}")
            os.makedirs(csv_dir, exist_ok=True)

            create_header = not os.path.exists(csv_path)

            with open(csv_path, "a", newline="") as csvfile:
                writer = csv.writer(csvfile)

                if create_header:
                    print("📌 Creating CSV header row…")
                    writer.writerow([
                        "Timestamp",
                        "User_IP",
                        "Recruiter",
                        "Converted_SMILES",
                        "Original_SMILES",
                        "Session_ID",
                        "Modified"
                    ])

                writer.writerow([
                    datetime.datetime.now().isoformat(),
                    ip,
                    recruiter,
                    converted_smiles,
                    original_smiles,
                    session_id,
                    modified
                ])

            print("🧾 CSV logging completed successfully")
            print(f"📁 CSV absolute path → {os.path.abspath(csv_path)}")
        except Exception as csv_error:
            print(f"⚠️ Converted-ligases CSV logging failed: {csv_error}")

        try:
            shipment_result = log_ligase_shipment(
                ip,
                session_id=session_id,
                recruiter_code=recruiter,
                skip_modify=skip_modify,
                metadata_json={
                    "modified": bool(modified),
                    "atom_index": atom_index,
                },
            )
            print(
                "📦 Shipment event recorded "
                f"(source={shipment_result.source}, duplicate={shipment_result.duplicate}, backup_ok={shipment_result.backup_ok})"
            )
        except Exception as shipment_error:
            print(f"⚠️ Shipment event logging failed: {shipment_error}")

        print("✅ [convert_atom_to_v] COMPLETED")
        print("==============================\n")

        return jsonify({
            "session_id": session_id,
            "converted_smiles": converted_smiles,
            "original_smiles": original_smiles,
            "modified": modified,
            "user_ip": ip
        })

    except Exception as e:
        print(f"❌ FATAL ERROR in convert_atom_to_v: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500








import json
import os

VISITS_FILE = os.path.join(os.path.dirname(__file__), "visits.json")

def increment_visits():
    """Helper that increments the visits.json counter."""
    if not os.path.exists(VISITS_FILE):
        with open(VISITS_FILE, "w") as f:
            json.dump({"total": 1}, f)
        return

    with open(VISITS_FILE, "r") as f:
        data = json.load(f)

    data["total"] = data.get("total", 0) + 1

    with open(VISITS_FILE, "w") as f:
        json.dump(data, f)


@ligases_bp.route("/visits", methods=["GET"])
def get_visits():
    """Return the number of visits."""
    if not os.path.exists(VISITS_FILE):
        return {"total": 0}

    with open(VISITS_FILE, "r") as f:
        data = json.load(f)

    return data




@ligases_bp.route("/tooltip/descriptors/<recruiter_code>", methods=["GET"])
def tooltip_descriptors(recruiter_code):
    """Return a single cleaned descriptor row for tooltip rendering."""
    query = """
        SELECT MW, LogP, TPSA, HBA, HBD, Ring_Count, QED, SA_Score,
               Lipinski_Pass, Veber_Pass, Egan_Pass
        FROM Ligase_Chemical_Descriptors
        WHERE RECRUITER_CODE = ?;
    """
    rows = query_db(query, [recruiter_code])
    return jsonify(dict(rows[0]) if rows else {})

@ligases_bp.route("/tooltip/metadata/<recruiter_code>", methods=["GET"])
def tooltip_metadata(recruiter_code):
    """Return simplified ligand metadata for tooltip."""
    query = """
        SELECT Name, Formula, Type, Canonical_SMILES
        FROM Ligase_Ligand_Metadata
        WHERE Ligand = ?
           OR Name = ?
           OR Canonical_SMILES = ?;
    """
    rows = query_db(query, [recruiter_code, recruiter_code, recruiter_code])
    return jsonify(dict(rows[0]) if rows else {})

@ligases_bp.route("/tooltip/all/<recruiter_code>", methods=["GET"])
def tooltip_all(recruiter_code):
    """Return descriptors + metadata + SMILES for tooltip rendering."""

    # --- DESCRIPTORS (has SMILES) ---
    d_query = """
        SELECT *
        FROM Ligase_Chemical_Descriptors
        WHERE RECRUITER_CODE = ?;
    """
    d_rows = query_db(d_query, [recruiter_code])
    descriptors = dict(d_rows[0]) if d_rows else {}

    # --- METADATA (optional extra data) ---
    m_query = """
        SELECT *
        FROM Ligase_Ligand_Metadata
        WHERE Canonical_SMILES = ? 
        OR SMILES = ?;
    """
    m_rows = query_db(m_query, [descriptors.get("SMILES"), descriptors.get("SMILES")])

    metadata = dict(m_rows[0]) if m_rows else {}

    # --- Select correct SMILES ---
    smiles = (
        descriptors.get("SMILES")
        or metadata.get("Canonical_SMILES")
        or ""
    )

    return jsonify({
        "descriptors": descriptors,
        "metadata": metadata,
        "smiles": smiles
    })



@ligases_bp.route("/missing-recruiter")
def missing_recruiter():
    """Page shown when a recruiter lacks SASA or PDB data."""
    code = request.args.get("code", "UNKNOWN")
    return render_template("missing_recruiter.html", code=code)











@ligases_bp.get("/random-recruiter")
def random_recruiter():
    """
    Return a random recruiter_code that has:
      - Valid composite key mapping
      - SASA summary
      - Atom-level SASA data
      - A valid PDB file in the active backend
    Ensures random clicks never hit missing_data.html
    """
    import random

    # Step 1 — Get all recruiters with valid composite key
    rows = query_db("""
        SELECT RECRUITER_CODE, Ligase, pdb_id, Ligand, Variant
        FROM Ligase_Ligands_Smiles_3DMapped
    """)

    valid = []

    for r in rows:
        code    = r["RECRUITER_CODE"]
        ligase  = r["Ligase"]
        pdb_id  = r["pdb_id"]
        ligand  = r["Ligand"]
        variant = r["Variant"]

        # Step 2 — SASA summary exists?
        sasa = query_db("""
            SELECT 1
            FROM Ligase_Ligand_SASA_summary
            WHERE Ligase=? AND pdb_id=? AND Ligand=?
              AND (Variant=? OR Variant IS NULL)
            LIMIT 1;
        """, [ligase, pdb_id, ligand, variant], one=True)

        if not sasa:
            continue

        # Step 3 — Atom-level SASA exists?
        atoms = query_db("""
            SELECT 1
            FROM Ligase_Ligand_SASA_atoms
            WHERE Ligase=? AND pdb_id=? AND Ligand=?
              AND (Variant=? OR Variant IS NULL)
            LIMIT 1;
        """, [ligase, pdb_id, ligand, variant], one=True)

        if not atoms:
            continue

        # Step 4 — PDB must exist in the active backend
        if not _resolve_pdb_filename(ligase, pdb_id, ligand, variant):
            continue

        # PASSED ALL CHECKS → SAFE RECRUITER
        valid.append(code)

    if not valid:
        return jsonify({"error": "No valid recruiters available"}), 404

    return jsonify({"code": random.choice(valid)})





@ligases_bp.route("/fixed-2d-smiles/<recruiter>", methods=["GET"])
def get_fixed_2d_smiles(recruiter):
    try:
        recruiter = recruiter.upper()

        row = query_db("""
            SELECT SMILES
            FROM Ligase_Chemical_Descriptors
            WHERE RECRUITER_CODE = ?
            LIMIT 1
        """, [recruiter], one=True)

        if not row:
            return jsonify({"error": "Not found"}), 404

        return jsonify({
            "RECRUITER_CODE": recruiter,
            "SMILES": row["SMILES"]
        })

    except Exception as e:
        print("❌ fixed-2d-smiles error:", e)
        return jsonify({"error": "server-error"}), 500



@ligases_bp.route("/scaffold-clusters", methods=["GET"])
def get_scaffold_clusters():
    """
    Return clustered scaffold data for the full-network Cytoscape view.

    Each entry in the returned list looks like:
    {
        "scaffoldHash": "6d930456",
        "scaffoldIds": ["CRBN_SCAF_1", "MDM2_SCAF_5"],
        "ligases": ["CRBN", "MDM2"],
        "recruiterCount": 42,
        "scaffoldSmiles": "CC1=NC(=O)...",
        "similarHashes": []   # optional similarity edges (currently empty)
    }
    """

    try:
        # Core aggregation — one row per Scaffold_Hash
        query = """
            SELECT
                Scaffold_Hash,
                GROUP_CONCAT(DISTINCT Scaffold_ID)      AS Scaffold_IDs,
                GROUP_CONCAT(DISTINCT Ligase)           AS Ligases,
                COUNT(DISTINCT RECRUITER_CODE)          AS Recruiter_Count,
                MAX(COALESCE(Scaffold_SMILES, ''))      AS Scaffold_SMILES
            FROM Ligase_Recruiters_Scaffold
            WHERE Scaffold_Hash IS NOT NULL
              AND TRIM(Scaffold_Hash) != ''
            GROUP BY Scaffold_Hash
        """

        rows = query_db(query)

        clusters = []
        for r in rows:
            scaffold_hash = r["Scaffold_Hash"]

            # Split CSV-style lists from GROUP_CONCAT
            scaffold_ids_raw = (r["Scaffold_IDs"] or "").split(",") if r["Scaffold_IDs"] else []
            ligases_raw      = (r["Ligases"] or "").split(",") if r["Ligases"] else []

            scaffold_ids = [s.strip() for s in scaffold_ids_raw if s and s.strip()]
            ligases      = sorted({l.strip() for l in ligases_raw if l and l.strip()})

            recruiter_count = r["Recruiter_Count"] or 0
            smiles = r["Scaffold_SMILES"].strip() if r["Scaffold_SMILES"] else None

            clusters.append({
                "scaffoldHash": scaffold_hash,
                "scaffoldIds": scaffold_ids,
                "ligases": ligases,
                "recruiterCount": recruiter_count,
                "scaffoldSmiles": smiles,
                # hook for future similarity table; for now, empty
                "similarHashes": []
            })

        return jsonify(clusters)

    except Exception as e:
        print(f"❌ Error building scaffold clusters: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to build scaffold clusters"}), 500



from flask import Response, current_app

@ligases_bp.route("/serve_session/<session_id>", methods=["GET"])
def serve_session(session_id):
    """
    Serve tmp_sessions/<session_id>.sdf as raw text.
    URL resolves to:
      https://stan.rove-vernier.ts.net/ligase/api/serve_session/<session_id>
    """
    import os

    base_dir = current_app.root_path
    tmp_dir = os.path.join(base_dir, "tmp_sessions")
    sdf_path = os.path.join(tmp_dir, f"{session_id}.sdf")

    print("\n==============================")
    print(f"📦 [serve_session] session_id = {session_id}")
    print(f"📄 sdf_path: {sdf_path}")
    print("==============================")

    if not os.path.exists(sdf_path):
        print("❌ File not found")
        return Response("Not found", status=404, mimetype="text/plain")

    with open(sdf_path, "r") as f:
        sdf_text = f.read()

    return Response(sdf_text, status=200, mimetype="chemical/x-mdl-sdfile")



@ligases_bp.route("/Ligases/<ligase>/PDB/<path:filename>")
def serve_pdb(ligase, filename):
    if randy_client.remote_enabled():
        return randy_client.proxy_file(
            f"file/pdb/{randy_client.quote_part(ligase)}/{randy_client.quote_path(filename)}",
            mimetype="chemical/x-pdb",
        )

    base = os.path.join(app.root_path, "Ligases")
    return send_from_directory(
        os.path.join(base, ligase),
        f"PDB/{filename}"
    )


@ligases_bp.route("/search/recruiters", methods=["GET"])
def search_recruiters():
    ligase = request.args.get("ligase")
    min_qed = float(request.args.get("min_qed", 0))
    min_mw = float(request.args.get("min_mw", 0))
    limit   = int(request.args.get("limit", 300))

    # Advanced filters
    logp = request.args.get("logp", type=float)
    tpsa = request.args.get("tpsa", type=float)
    hba  = request.args.get("hba", type=int)
    hbd  = request.args.get("hbd", type=int)
    rotb = request.args.get("rotb", type=int)
    fsp3 = request.args.get("fsp3", type=float)

    if not ligase:
        return jsonify([])

    query = """
        SELECT
            d.RECRUITER_CODE,
            d.SMILES,
            d.QED,
            d.MW
        FROM Ligase_Chemical_Descriptors d
        WHERE EXISTS (
            SELECT 1
            FROM Ligase_Ligands_Smiles_3DMapped m
            WHERE m.RECRUITER_CODE = d.RECRUITER_CODE
            AND m.Ligase = ?
        )
        AND d.QED >= ?
        AND d.MW >= ?
    """


    params = [ligase, min_qed, min_mw]

    # ---------- ADVANCED FILTERS ----------

    if logp is not None:
        query += " AND (d.LogP IS NULL OR d.LogP <= ?)"
        params.append(logp)

    if tpsa is not None:
        query += " AND (d.TPSA IS NULL OR d.TPSA <= ?)"
        params.append(tpsa)

    if hba is not None:
        query += " AND (d.HBA IS NULL OR d.HBA <= ?)"
        params.append(hba)

    if hbd is not None:
        query += " AND (d.HBD IS NULL OR d.HBD <= ?)"
        params.append(hbd)

    if rotb is not None:
        query += " AND (d.Rotatable_Bonds IS NULL OR d.Rotatable_Bonds <= ?)"
        params.append(rotb)

    if fsp3 is not None:
        query += " AND (d.Fraction_CSP3 IS NULL OR d.Fraction_CSP3 >= ?)"
        params.append(fsp3)


    query += """
        ORDER BY d.QED DESC
        LIMIT ?;
    """

    params.append(limit)

    # 🔥 THIS WAS THE BUG
    rows = query_db(query, params)

    return jsonify([dict(r) for r in rows])





# ===========================================================================
# 📦 PUBLIC DATA DOWNLOAD API — E3 Recruiter Ligandalyzer
# ---------------------------------------------------------------------------
# Paste this block near the bottom of Ligases/routes.py.
# Because Ligase_app.py registers ligases_bp with url_prefix="/api", every route
# below will appear publicly as /api/download/...
#
# Directory assumptions on STAN:
#   WebTools/E3Recruiter_Ligandalyzer/Ligases/routes.py
#   WebTools/E3Recruiter_Ligandalyzer/Ligases/<Ligase>/PDB/*.pdb
#   WebTools/E3Recruiter_Ligandalyzer/Ligases/<Ligase>/SDF_4Download/*.sdf
#   WebTools/E3Recruiter_Ligandalyzer/Ligases/<Ligase>/SDF/*.sdf       (fallback)
# ===========================================================================

from pathlib import Path
from io import BytesIO, StringIO
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime, timezone
import csv
import json
import re

from flask import Response, abort, jsonify, request, send_file


# ---------------------------------------------------------------------------
# Safe filesystem helpers
# ---------------------------------------------------------------------------
def _download_ligases_root() -> Path:
    """Return the physical Ligases/ directory that contains routes.py."""
    return Path(__file__).resolve().parent


def _is_relative_to(path: Path, root: Path) -> bool:
    """Python 3.8-compatible Path.is_relative_to()."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _list_download_ligase_dirs():
    """Return true ligase directories, excluding cache/db/report folders."""
    root = _download_ligases_root()
    skip_names = {
        "__pycache__", "CSVcache", "templates", "static", "tmp_sessions",
    }
    dirs = []
    for p in root.iterdir():
        if not p.is_dir():
            continue
        if p.name in skip_names or p.name.startswith("."):
            continue
        if (p / "PDB").is_dir() or (p / "SDF_4Download").is_dir() or (p / "SDF").is_dir():
            dirs.append(p)
    return sorted(dirs, key=lambda x: x.name.lower())


def _resolve_ligase_dir(ligase: str) -> Path:
    """
    Resolve a ligase folder by exact or case-insensitive name.
    Prevents path traversal while still supporting names like HOIP(RNF31) and Cbl-b.
    """
    if not ligase or "/" in ligase or "\\" in ligase or ".." in ligase:
        abort(400, description="Invalid ligase name.")

    root = _download_ligases_root()
    exact = (root / ligase).resolve()
    if exact.is_dir() and _is_relative_to(exact, root):
        return exact

    lower = ligase.lower()
    for d in _list_download_ligase_dirs():
        if d.name.lower() == lower:
            return d.resolve()

    abort(404, description=f"Ligase not found: {ligase}")


def _asset_dirs_for_ligase(ligase_dir: Path, asset_type: str):
    """Return candidate folders for pdb/sdf/all downloads."""
    asset_type = asset_type.lower()
    folders = []

    if asset_type in {"pdb", "pdbs", "all", "structures"}:
        folders.append(("PDB", ligase_dir / "PDB", {".pdb"}))

    if asset_type in {"sdf", "sdfs", "all", "structures"}:
        # Prefer the cleaned/user-facing SDF_4Download folder, but support SDF fallback.
        folders.append(("SDF_4Download", ligase_dir / "SDF_4Download", {".sdf"}))
        folders.append(("SDF", ligase_dir / "SDF", {".sdf"}))

    return [(label, folder, exts) for label, folder, exts in folders if folder.is_dir()]


def _files_from_asset_dirs(asset_dirs):
    """Collect files from candidate asset directories."""
    files = []
    seen = set()
    for label, folder, exts in asset_dirs:
        for f in sorted(folder.iterdir(), key=lambda x: x.name.lower()):
            if not f.is_file():
                continue
            if f.suffix.lower() not in exts:
                continue
            resolved = f.resolve()
            if not _is_relative_to(resolved, folder):
                continue
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            files.append((label, resolved))
    return files


def _safe_file_in_folder(folder: Path, filename: str, allowed_exts):
    """Resolve an individual requested file under a known folder."""
    if not filename or filename.startswith("/") or ".." in Path(filename).parts:
        abort(400, description="Invalid filename.")

    candidate = (folder / filename).resolve()
    if not _is_relative_to(candidate, folder):
        abort(400, description="Invalid filename.")
    if not candidate.is_file():
        abort(404, description=f"File not found: {filename}")
    if candidate.suffix.lower() not in allowed_exts:
        abort(400, description=f"Unsupported file type: {candidate.suffix}")
    return candidate


def _zip_response(files, download_name: str, metadata: dict | None = None):
    """Build an in-memory ZIP response from a list of (archive_path, physical_path)."""
    if not files:
        abort(404, description="No matching downloadable files were found.")

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as zf:
        if metadata:
            zf.writestr("manifest.json", json.dumps(metadata, indent=2, sort_keys=True))

        added = set()
        for arcname, path in files:
            arcname = str(arcname).replace("\\", "/")
            if arcname in added:
                # Avoid zip duplicate warnings if two source folders contain same basename.
                stem = Path(arcname).stem
                suffix = Path(arcname).suffix
                parent = str(Path(arcname).parent).replace("\\", "/")
                arcname = f"{parent}/{stem}_{len(added)}{suffix}"
            added.add(arcname)
            zf.write(path, arcname)

    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=download_name,
        max_age=0,
    )


def _api_url(path: str) -> str:
    """Create an absolute URL that respects reverse-proxy script roots when present."""
    script_root = request.script_root.rstrip("/")
    return f"{request.host_url.rstrip('/')}{script_root}/api{path}"


def _variant_stems(pdb_id, ligand, variant=None):
    """Candidate filename stems for PDB/SDF assets tied to a database mapping row."""
    base = f"{pdb_id}_{ligand}"
    candidates = []

    if variant not in (None, "", 0, "0"):
        candidates.append(f"{base}_{variant}")

    candidates.extend([base, f"{base}_1"])

    # Preserve order but remove duplicates.
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def _find_asset_for_mapping(ligase, pdb_id, ligand, variant, ext):
    """Find a PDB/SDF file from a mapping row using exact and variant-aware fallbacks."""
    ligase_dir = _resolve_ligase_dir(ligase)
    ext = ext.lower()

    folders = []
    if ext == ".pdb":
        folders = [ligase_dir / "PDB"]
    elif ext == ".sdf":
        folders = [ligase_dir / "SDF_4Download", ligase_dir / "SDF"]
    else:
        return None

    base = f"{pdb_id}_{ligand}"
    stems = _variant_stems(pdb_id, ligand, variant)

    for folder in folders:
        if not folder.is_dir():
            continue

        for stem in stems:
            candidate = (folder / f"{stem}{ext}").resolve()
            if candidate.is_file() and _is_relative_to(candidate, folder):
                return candidate

        # Final fallback: any <PDB>_<LIGAND>_<n>.ext variant.
        pattern = re.compile(rf"^{re.escape(base)}(?:_\d+)?{re.escape(ext)}$", re.IGNORECASE)
        for f in sorted(folder.iterdir(), key=lambda x: x.name.lower()):
            if f.is_file() and pattern.match(f.name):
                return f.resolve()

    return None


_RECRUITER_CODE_RE = re.compile(r"^LR\d{5}$", re.IGNORECASE)


def _clean_recruiter_code(code: str) -> str:
    """
    Validate and canonicalize public recruiter IDs.

    Canonical format is LR##### with five digits, for example LR00001.
    There are no public L##### recruiter codes in this dataset.
    """
    code = (code or "").strip().upper()
    if not code:
        abort(400, description="At least one recruiter code is required. Use LR##### format, e.g. LR00001.")
    if not _RECRUITER_CODE_RE.fullmatch(code):
        abort(400, description=f"Invalid recruiter code '{code}'. Use canonical LR##### format, e.g. LR00001.")
    return code


def _parse_recruiter_codes(codes):
    """
    Parse recruiter codes from a comma/space/semicolon-delimited string or iterable.
    Returns unique uppercase LR##### codes in input order.
    """
    if isinstance(codes, str):
        raw_parts = re.split(r"[,;\s]+", codes.strip())
    else:
        raw_parts = list(codes or [])

    cleaned = []
    for raw in raw_parts:
        if raw is None or str(raw).strip() == "":
            continue
        code = _clean_recruiter_code(str(raw))
        if code not in cleaned:
            cleaned.append(code)

    if not cleaned:
        abort(400, description="At least one recruiter code is required. Use LR##### format, e.g. LR00001.")
    return cleaned


def _mapping_rows_for_recruiter_codes(codes):
    """Resolve canonical LR##### recruiter codes to physical structure mappings."""
    cleaned = _parse_recruiter_codes(codes)

    placeholders = ",".join(["?"] * len(cleaned))
    rows = query_db(f"""
        SELECT DISTINCT
            RECRUITER_CODE,
            Ligase,
            PDB_ID AS pdb_id,
            Ligand,
            Variant
        FROM Ligase_Ligands_Smiles_3DMapped
        WHERE UPPER(RECRUITER_CODE) IN ({placeholders})
        ORDER BY RECRUITER_CODE, Ligase, pdb_id, Ligand, Variant;
    """, cleaned)

    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Public download manifest and discovery endpoints
# ---------------------------------------------------------------------------
@ligases_bp.route("/download/manifest", methods=["GET"])
def download_manifest():
    """
    Discover downloadable data.

    Optional filters:
      /api/download/manifest
      /api/download/manifest?ligase=CRBN
      /api/download/manifest?recruiter_code=LR00001
    """
    ligase_filter = request.args.get("ligase")
    recruiter_code = request.args.get("recruiter_code")

    if recruiter_code:
        recruiter_code = _clean_recruiter_code(recruiter_code)
        rows = _mapping_rows_for_recruiter_codes([recruiter_code])
        entries = []
        for row in rows:
            pdb_file = _find_asset_for_mapping(row["Ligase"], row["pdb_id"], row["Ligand"], row.get("Variant"), ".pdb")
            sdf_file = _find_asset_for_mapping(row["Ligase"], row["pdb_id"], row["Ligand"], row.get("Variant"), ".sdf")
            entries.append({
                **row,
                "pdb_file": pdb_file.name if pdb_file else None,
                "sdf_file": sdf_file.name if sdf_file else None,
                "pdb_download": _api_url(f"/download/pdb/{row['Ligase']}/{pdb_file.name}") if pdb_file else None,
                "sdf_download": _api_url(f"/download/sdf/{row['Ligase']}/{sdf_file.name}") if sdf_file else None,
            })

        return jsonify({
            "base_url": _api_url(""),
            "filter": {"recruiter_code": recruiter_code},
            "count": len(entries),
            "bundle_download": _api_url(f"/download/recruiter/{recruiter_code}.zip"),
            "entries": entries,
        })

    ligase_dirs = [_resolve_ligase_dir(ligase_filter)] if ligase_filter else _list_download_ligase_dirs()
    ligases = []

    for ligase_dir in ligase_dirs:
        pdb_files = _files_from_asset_dirs(_asset_dirs_for_ligase(ligase_dir, "pdbs"))
        sdf_files = _files_from_asset_dirs(_asset_dirs_for_ligase(ligase_dir, "sdfs"))
        ligases.append({
            "ligase": ligase_dir.name,
            "pdb_count": len(pdb_files),
            "sdf_count": len(sdf_files),
            "downloads": {
                "pdb_zip": _api_url(f"/download/ligase/{ligase_dir.name}/pdbs.zip"),
                "sdf_zip": _api_url(f"/download/ligase/{ligase_dir.name}/sdfs.zip"),
                "all_zip": _api_url(f"/download/ligase/{ligase_dir.name}/all.zip"),
            },
            "files": {
                "pdb": [p.name for _, p in pdb_files],
                "sdf": [p.name for _, p in sdf_files],
            }
        })

    return jsonify({
        "base_url": _api_url(""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ligase_count": len(ligases),
        "all_downloads": {
            "all_pdbs_zip": _api_url("/download/all/pdbs.zip"),
            "all_sdfs_zip": _api_url("/download/all/sdfs.zip"),
            "all_structures_zip": _api_url("/download/all/structures.zip"),
        },
        "tables": {
            "scaffold_data_csv": _api_url("/download/table/Ligase_Scaffold_Data.csv"),
            "recruiter_scaffold_csv": _api_url("/download/table/Ligase_Recruiters_Scaffold.csv"),
            "sasa_summary_csv": _api_url("/download/table/Ligase_Ligand_SASA_summary.csv"),
            "sasa_atoms_csv": _api_url("/download/table/Ligase_Ligand_SASA_atoms.csv"),
            "descriptor_csv": _api_url("/download/table/Ligase_Chemical_Descriptors.csv"),
        },
        "ligases": ligases,
    })


@ligases_bp.route("/download/ligases", methods=["GET"])
def download_ligase_index():
    """Compact JSON index of ligases and downloadable file counts."""
    rows = []
    for ligase_dir in _list_download_ligase_dirs():
        pdb_count = len(_files_from_asset_dirs(_asset_dirs_for_ligase(ligase_dir, "pdbs")))
        sdf_count = len(_files_from_asset_dirs(_asset_dirs_for_ligase(ligase_dir, "sdfs")))
        rows.append({
            "ligase": ligase_dir.name,
            "pdb_count": pdb_count,
            "sdf_count": sdf_count,
            "all_zip": _api_url(f"/download/ligase/{ligase_dir.name}/all.zip"),
        })
    return jsonify(rows)


@ligases_bp.route("/download/recruiter-codes", methods=["GET"])
def download_recruiter_code_index():
    """
    Discover canonical LR##### recruiter codes with optional ligase filtering.

    Examples:
      /api/download/recruiter-codes
      /api/download/recruiter-codes?ligase=CRBN
      /api/download/recruiter-codes?ligase=CRBN&limit=25
    """
    ligase = request.args.get("ligase")
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50
    limit = max(1, min(limit, 1000))

    query = """
        SELECT DISTINCT
            RECRUITER_CODE,
            Ligase,
            PDB_ID AS pdb_id,
            Ligand,
            Variant
        FROM Ligase_Ligands_Smiles_3DMapped
        WHERE RECRUITER_CODE IS NOT NULL
          AND TRIM(RECRUITER_CODE) != ''
          AND UPPER(RECRUITER_CODE) LIKE 'LR%'
    """
    params = []
    if ligase:
        query += " AND Ligase = ?"
        params.append(ligase)
    query += " ORDER BY RECRUITER_CODE, Ligase, pdb_id, Ligand LIMIT ?;"
    params.append(limit)

    rows = [dict(r) for r in query_db(query, params)]
    results = []
    for row in rows:
        pdb_file = _find_asset_for_mapping(row["Ligase"], row["pdb_id"], row["Ligand"], row.get("Variant"), ".pdb")
        sdf_file = _find_asset_for_mapping(row["Ligase"], row["pdb_id"], row["Ligand"], row.get("Variant"), ".sdf")
        results.append({
            "recruiter_code": row["RECRUITER_CODE"],
            "ligase": row["Ligase"],
            "pdb_id": row["pdb_id"],
            "ligand": row["Ligand"],
            "variant": row.get("Variant"),
            "has_pdb": bool(pdb_file),
            "has_sdf": bool(sdf_file),
            "pdb_file": pdb_file.name if pdb_file else None,
            "sdf_file": sdf_file.name if sdf_file else None,
        })

    example_codes = []
    for item in results:
        code = item["recruiter_code"]
        if code not in example_codes and (item["has_pdb"] or item["has_sdf"]):
            example_codes.append(code)
        if len(example_codes) >= 3:
            break

    return jsonify({
        "count": len(results),
        "filter": {"ligase": ligase, "limit": limit},
        "canonical_format": "LR#####",
        "example_codes": example_codes,
        "bundle_example": _api_url(f"/download/recruiters.zip?codes={','.join(example_codes)}") if example_codes else None,
        "results": results,
    })


# ---------------------------------------------------------------------------
# Individual physical file downloads
# ---------------------------------------------------------------------------
@ligases_bp.route("/download/pdb/<ligase>/<path:filename>", methods=["GET"])
def download_single_pdb(ligase, filename):
    """Download one PDB file from Ligases/<Ligase>/PDB/."""
    if randy_client.remote_enabled():
        return randy_client.proxy_file(
            f"file/pdb/{randy_client.quote_part(ligase)}/{randy_client.quote_path(filename)}",
            download_name=filename,
            mimetype="chemical/x-pdb",
        )

    ligase_dir = _resolve_ligase_dir(ligase)
    folder = ligase_dir / "PDB"
    if not folder.is_dir():
        abort(404, description=f"No PDB folder found for {ligase}.")
    f = _safe_file_in_folder(folder, filename, {".pdb"})
    return send_file(f, mimetype="chemical/x-pdb", as_attachment=True, download_name=f.name, max_age=0)


@ligases_bp.route("/download/sdf/<ligase>/<path:filename>", methods=["GET"])
def download_single_sdf(ligase, filename):
    """Download one SDF file from SDF_4Download first, then SDF fallback."""
    if randy_client.remote_enabled():
        return randy_client.proxy_file(
            f"file/sdf/{randy_client.quote_part(ligase)}/{randy_client.quote_path(filename)}",
            download_name=filename,
            mimetype="chemical/x-mdl-sdfile",
        )

    ligase_dir = _resolve_ligase_dir(ligase)
    for folder in [ligase_dir / "SDF_4Download", ligase_dir / "SDF"]:
        if not folder.is_dir():
            continue
        try:
            f = _safe_file_in_folder(folder, filename, {".sdf"})
            return send_file(f, mimetype="chemical/x-mdl-sdfile", as_attachment=True, download_name=f.name, max_age=0)
        except Exception:
            # Try next candidate folder before returning 404.
            continue
    abort(404, description=f"SDF not found for {ligase}/{filename}")


# ---------------------------------------------------------------------------
# Ligase-level ZIP downloads
# ---------------------------------------------------------------------------
@ligases_bp.route("/download/ligase/<ligase>/<asset_type>.zip", methods=["GET"])
def download_ligase_zip(ligase, asset_type):
    """
    Download all files for one ligase.

    asset_type:
      pdbs.zip   -> all Ligases/<Ligase>/PDB/*.pdb
      sdfs.zip   -> all Ligases/<Ligase>/SDF_4Download/*.sdf and SDF/*.sdf
      all.zip    -> PDB + SDF files
    """
    asset_type = asset_type.lower()
    if asset_type not in {"pdbs", "sdfs", "all", "structures"}:
        abort(400, description="asset_type must be one of: pdbs, sdfs, all, structures")
    if randy_client.remote_enabled():
        return randy_client.proxy_file(
            f"download/ligase/{randy_client.quote_part(ligase)}/{randy_client.quote_part(asset_type)}.zip",
            download_name=f"E3Ligandalyzer_{ligase}_{asset_type}.zip",
            mimetype="application/zip",
        )

    ligase_dir = _resolve_ligase_dir(ligase)
    source_files = _files_from_asset_dirs(_asset_dirs_for_ligase(ligase_dir, asset_type))

    files = []
    for label, path in source_files:
        files.append((f"{ligase_dir.name}/{label}/{path.name}", path))

    metadata = {
        "scope": "ligase",
        "ligase": ligase_dir.name,
        "asset_type": asset_type,
        "file_count": len(files),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _zip_response(files, f"E3Ligandalyzer_{ligase_dir.name}_{asset_type}.zip", metadata)


@ligases_bp.route("/download/all/<asset_type>.zip", methods=["GET"])
def download_all_ligases_zip(asset_type):
    """
    Download PDB/SDF files across every ligase.

    asset_type:
      pdbs.zip, sdfs.zip, structures.zip, all.zip
    """
    asset_type = asset_type.lower()
    if asset_type not in {"pdbs", "sdfs", "all", "structures"}:
        abort(400, description="asset_type must be one of: pdbs, sdfs, all, structures")
    if randy_client.remote_enabled():
        return randy_client.proxy_file(
            f"download/all/{randy_client.quote_part(asset_type)}.zip",
            download_name=f"E3Ligandalyzer_ALL_{asset_type}.zip",
            mimetype="application/zip",
        )

    files = []
    per_ligase = []
    for ligase_dir in _list_download_ligase_dirs():
        source_files = _files_from_asset_dirs(_asset_dirs_for_ligase(ligase_dir, asset_type))
        per_ligase.append({"ligase": ligase_dir.name, "file_count": len(source_files)})
        for label, path in source_files:
            files.append((f"{ligase_dir.name}/{label}/{path.name}", path))

    metadata = {
        "scope": "all_ligases",
        "asset_type": asset_type,
        "file_count": len(files),
        "ligases": per_ligase,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _zip_response(files, f"E3Ligandalyzer_ALL_{asset_type}.zip", metadata)


# ---------------------------------------------------------------------------
# Recruiter-code ZIP downloads
# ---------------------------------------------------------------------------
@ligases_bp.route("/download/recruiter/<recruiter_code>.zip", methods=["GET"])
def download_recruiter_bundle(recruiter_code):
    """
    Download all mapped PDB/SDF assets for a single recruiter code.
    Example: /api/download/recruiter/LR00001.zip
    """
    recruiter_code = _clean_recruiter_code(recruiter_code)
    rows = _mapping_rows_for_recruiter_codes([recruiter_code])
    if not rows:
        abort(404, description=f"No database mappings found for recruiter {recruiter_code}.")

    files = []
    resolved = []
    missing = []

    for row in rows:
        row_key = f"{row['RECRUITER_CODE']}/{row['Ligase']}/{row['pdb_id']}_{row['Ligand']}_v{row.get('Variant') or 'NA'}"
        pdb_file = _find_asset_for_mapping(row["Ligase"], row["pdb_id"], row["Ligand"], row.get("Variant"), ".pdb")
        sdf_file = _find_asset_for_mapping(row["Ligase"], row["pdb_id"], row["Ligand"], row.get("Variant"), ".sdf")

        if pdb_file:
            files.append((f"{row_key}/PDB/{pdb_file.name}", pdb_file))
        else:
            missing.append({**row, "missing": "pdb"})

        if sdf_file:
            files.append((f"{row_key}/SDF/{sdf_file.name}", sdf_file))
        else:
            missing.append({**row, "missing": "sdf"})

        resolved.append({
            **row,
            "pdb_file": pdb_file.name if pdb_file else None,
            "sdf_file": sdf_file.name if sdf_file else None,
        })

    metadata = {
        "scope": "recruiter",
        "recruiter_code": recruiter_code.upper(),
        "mapping_count": len(rows),
        "file_count": len(files),
        "resolved": resolved,
        "missing": missing,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _zip_response(files, f"E3Ligandalyzer_{recruiter_code.upper()}_bundle.zip", metadata)


@ligases_bp.route("/download/recruiters.zip", methods=["GET"])
def download_multiple_recruiter_bundle():
    """
    Download a combined ZIP for multiple recruiter codes.
    Example: /api/download/recruiters.zip?codes=LR00001,LR00002,LR00003
    """
    codes_raw = request.args.get("codes", "")
    codes = _parse_recruiter_codes(codes_raw)

    rows = _mapping_rows_for_recruiter_codes(codes)
    if not rows:
        abort(404, description="No database mappings found for the supplied recruiter codes.")

    files = []
    resolved = []
    missing = []

    for row in rows:
        row_key = f"{row['RECRUITER_CODE']}/{row['Ligase']}/{row['pdb_id']}_{row['Ligand']}_v{row.get('Variant') or 'NA'}"
        for ext, label in [(".pdb", "PDB"), (".sdf", "SDF")]:
            asset = _find_asset_for_mapping(row["Ligase"], row["pdb_id"], row["Ligand"], row.get("Variant"), ext)
            if asset:
                files.append((f"{row_key}/{label}/{asset.name}", asset))
                resolved.append({**row, "asset_type": label, "file": asset.name})
            else:
                missing.append({**row, "missing": label})

    metadata = {
        "scope": "recruiters",
        "requested_codes": [c.upper() for c in codes],
        "mapping_count": len(rows),
        "file_count": len(files),
        "resolved": resolved,
        "missing": missing,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    joined = "_".join([c.upper() for c in codes[:6]])
    suffix = "_plus" if len(codes) > 6 else ""
    return _zip_response(files, f"E3Ligandalyzer_recruiters_{joined}{suffix}.zip", metadata)


# ---------------------------------------------------------------------------
# CSV table exports from Ligase_Recruiter.db
# ---------------------------------------------------------------------------
_PUBLIC_DOWNLOAD_TABLES = {
    "Ligase_Scaffold_Data",
    "Ligase_Scaffold_Summary",
    "Ligase_Scaffold_Frequency",
    "Ligase_Recruiters_Scaffold",
    "Ligase_Chemical_Descriptors",
    "Ligase_Ligand_Metadata",
    "Ligase_Ligand_SASA_summary",
    "Ligase_Ligand_SASA_atoms",
    "Ligase_Ligands_Smiles_3DMapped",
    "Ligase_SMILE_Codes",
    "Recruiter_SMILES_Map",
}


@ligases_bp.route("/download/tables", methods=["GET"])
def download_table_index():
    """List whitelisted database tables that can be exported as CSV."""
    return jsonify([
        {"table": table, "csv": _api_url(f"/download/table/{table}.csv")}
        for table in sorted(_PUBLIC_DOWNLOAD_TABLES)
    ])


@ligases_bp.route("/download/table/<table_name>.csv", methods=["GET"])
def download_table_csv(table_name):
    """
    Export a public, whitelisted SQLite table as CSV.
    Example: /api/download/table/Ligase_Scaffold_Data.csv
    """
    if table_name not in _PUBLIC_DOWNLOAD_TABLES:
        abort(404, description=f"Table is not available for public export: {table_name}")
    if randy_client.remote_enabled():
        return randy_client.proxy_file(
            f"download/table/{randy_client.quote_part(table_name)}.csv",
            download_name=f"E3Ligandalyzer_{table_name}.csv",
            mimetype="text/csv",
        )

    rows = query_db(f"SELECT * FROM {table_name};")
    output = StringIO()

    if rows:
        headers = rows[0].keys()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    else:
        output.write("")

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=E3Ligandalyzer_{table_name}.csv",
            "Cache-Control": "no-store",
        },
    )
