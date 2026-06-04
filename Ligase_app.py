#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from datetime import datetime
from urllib.parse import urlencode
from flask import Flask, render_template, send_from_directory, request, redirect
from Ligases.routes import ligases_bp, query_db, build_download_manifest
from Ligases import randy_client
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Request

import random


def get_protac_builder_base_url() -> str:
    return (os.environ.get("PROTAC_BUILDER_BASE_URL", "https://protacbuilder.com") or "https://protacbuilder.com").rstrip("/")


def build_protac_builder_session_url(session_id: str) -> str:
    query = urlencode({"session": str(session_id or "").strip()})
    return f"{get_protac_builder_base_url()}/builder?{query}"


def _safe_scalar(query, fallback=None):
    try:
        rows = query_db(query)
        if rows:
            return rows[0][0]
    except Exception:
        pass
    return fallback


def build_release_context():
    db_path = os.environ.get(
        "E3_LOCAL_DB_PATH",
        os.path.join(os.path.dirname(__file__), "Ligases", "Ligase_Recruiter.db"),
    )

    snapshot_date = None
    try:
        snapshot_date = datetime.fromtimestamp(os.path.getmtime(db_path)).strftime("%B %d, %Y").replace(" 0", " ")
    except OSError:
        snapshot_date = None

    stats = {
        "ligases": _safe_scalar("SELECT COUNT(DISTINCT Ligase) FROM Ligase_Scaffold_Data"),
        "recruiter_records": _safe_scalar("SELECT COUNT(DISTINCT RECRUITER_CODE) FROM Ligand_Instance_Recruiter_Codes"),
        "unique_ligands": _safe_scalar("SELECT COUNT(DISTINCT Ligand) FROM Ligand_Instance_Recruiter_Codes"),
        "pdb_structures": _safe_scalar("SELECT COUNT(DISTINCT pdb_id) FROM Ligand_Instance_Recruiter_Codes"),
        "scaffolds": _safe_scalar("SELECT COUNT(DISTINCT Scaffold_ID) FROM Ligase_Scaffold_Data"),
        "scaffold_superclusters": _safe_scalar("SELECT COUNT(DISTINCT Supercluster_Key) FROM Ligase_Scaffold_Superclusters"),
        "complete_sasa": _safe_scalar(
            "SELECT COUNT(*) FROM Ligase_Ligand_SASA_summary WHERE [%Exposed] IS NOT NULL AND [%Buried] IS NOT NULL"
        ),
        "missing_data": _safe_scalar(
            "SELECT COUNT(*) FROM Ligase_Ligand_SASA_summary WHERE [%Exposed] IS NULL OR [%Buried] IS NULL",
            0,
        ),
    }

    return {
        "version_label": "Version 1.0",
        "short_label": "V1",
        "release_state": "Public V1 database release",
        "release_date": "Initial public V1 release",
        "update_cadence": "Annual review and update cycle",
        "update_policy": "New ligases, recruiter structures, scaffold annotations, and SASA-linked assets may be incorporated in future yearly releases after curation and validation.",
        "snapshot_date": snapshot_date,
        "stats": stats,
        "download_table_count": 5,
    }


# =============================================================================
#  PROPER APP FACTORY WITHOUT URL PREFIXES
#  (your routes stay exactly the s
# =============================================================================
def create_app():
    app = Flask(
        __name__,
        static_folder='static',
        template_folder='templates'
    )

    app.config["PROTAC_BUILDER_BASE_URL"] = get_protac_builder_base_url()

    # Register your API blueprint normally (no prefix)
    app.register_blueprint(ligases_bp, url_prefix="/api")

    app.secret_key = os.urandom(24)

    @app.context_processor
    def inject_protac_builder_config():
        return {
            "PROTAC_BUILDER_BASE_URL": app.config["PROTAC_BUILDER_BASE_URL"],
        }


    # ---------------------------------------------------------
    # Frontend pages (NO prefix)
    # ---------------------------------------------------------
    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/explorer")
    def explorer():
        return render_template("explorer.html")

    @app.route("/scaffolds")
    def scaffolds():
        return render_template("scaffolds.html")

    @app.route("/ligases")
    def ligases_page():
        return render_template("ligases.html")

    @app.route("/copy/COPYindex")
    def legacy_copyindex_home():
        return redirect(app.config["PROTAC_BUILDER_BASE_URL"], code=302)

    @app.route("/copy/COPYindex/build")
    def legacy_copyindex_build():
        session_id = str(request.args.get("session", "") or "").strip()
        if not session_id:
            return redirect(app.config["PROTAC_BUILDER_BASE_URL"], code=302)
        return redirect(build_protac_builder_session_url(session_id), code=302)

    LIGAND_REDIRECTS = {
        # "L00794": "L00266",
        # "L00582": "L00308",
        # "L00728": "L00047",
        # "L00799": "L00310",
        # "L00750": "L00092",
        # "L00764": "L00136",
        # "L00800": "L00385",
        # "L00804": "L00449",
        # "L00585": "L00003",
        # "L00801": "L00386",
        # future mappings
    }

    @app.route("/ligand/<code>")
    def ligand_page(code):

        # 1️⃣ Hard redirect map (canonical)
        if code in LIGAND_REDIRECTS:
            target = LIGAND_REDIRECTS[code]
            return redirect(f"/ligand/{target}", code=302)

        # 2️⃣ Normal render
        return render_template("ligand.html", recruiter_code=code)


    @app.route("/Ligases/<path:filename>")
    def serve_ligase_file(filename):
        if randy_client.remote_enabled():
            parts = filename.split("/", 2)
            if len(parts) >= 3 and parts[1].upper() == "PDB":
                return randy_client.proxy_file(
                    f"file/pdb/{randy_client.quote_part(parts[0])}/{randy_client.quote_path(parts[2])}",
                    mimetype="chemical/x-pdb",
                )
        base_dir = os.path.join(app.root_path, "Ligases")
        return send_from_directory(base_dir, filename)

    @app.route("/missing")
    def missing():
        return render_template("missing_data.html", SUPPORT_EMAIL="jxs794@miami.edu")

    @app.route("/about")
    def about():
        stats = {
            "total_ligases": query_db("SELECT COUNT(DISTINCT Ligase) AS n FROM Ligase_Scaffold_Data;")[0]["n"],
            "total_scaffolds": query_db("SELECT COUNT(DISTINCT Scaffold_ID) AS n FROM Ligase_Scaffold_Data;")[0]["n"],
            "avg_density": round(query_db("SELECT AVG(Recruiter_Density_Score) AS n FROM Ligase_Scaffold_Data;")[0]["n"], 2),
            "total_complexes": query_db("SELECT COUNT(*) AS n FROM Ligase_Ligand_SASA_summary;")[0]["n"],
            "top_ligase": query_db("SELECT Ligase FROM Ligase_Ligand_SASA_summary GROUP BY Ligase ORDER BY COUNT(*) DESC LIMIT 1;")[0]["Ligase"]
        }
        return render_template("about.html", stats=stats)

    @app.route("/docs")
    def docs():
        return render_template("docs.html")

    @app.route("/methods")
    def methods():
        return render_template("methods.html")

    @app.route("/schema")
    def schema():
        return render_template("schema.html")

    @app.route("/download-manifest")
    def download_manifest_page():
        manifest = build_download_manifest()
        return render_template("download_manifest.html", manifest=manifest)

    @app.route("/api-reference")
    def api_reference():
        return render_template("api-reference.html")

    @app.route("/release")
    def release():
        return render_template("release.html", release=build_release_context())

    @app.route("/contribute")
    def contribute():
        return render_template("contribute.html")

    @app.route("/case-studies")
    def case_studies():
        return render_template("case_studies.html")

    @app.route("/scaffold-network-full")
    def scaffold_network_full_page():
        return render_template("scaffold_network_full.html")

    @app.route("/scaffolds/<scaffold_id>")
    def scaffold_detail(scaffold_id):
        row = query_db("""
            SELECT DISTINCT Scaffold_ID, Scaffold_SMILES
            FROM Ligase_Recruiters_Scaffold
            WHERE Scaffold_ID = ?
        """, [scaffold_id], one=True)

        if not row:
            return render_template("missing_data.html", SUPPORT_EMAIL="jxs794@miami.edu")

        recruiters = query_db("""
            SELECT RECRUITER_CODE, Ligase
            FROM Ligase_Recruiters_Scaffold
            WHERE Scaffold_ID = ?
            ORDER BY Ligase
        """, [scaffold_id])

        return render_template(
            "scaffold_detail.html",
            scaffold=dict(row),
            recruiters=[dict(r) for r in recruiters]
        )
    

    @app.errorhandler(411)
    def missing_recruiter_error(error):
        code = getattr(error, "description", None)
        return render_template("missing_recruiter.html", recruiter_code=code, SUPPORT_EMAIL="jxs794@miami.edu"), 411
    
    @app.route("/missing-recruiter")
    def missing_recruiter():
        code = request.args.get("code", "UNKNOWN")
        return render_template("missing_recruiter.html", recruiter_code=code, SUPPORT_EMAIL="jxs794@miami.edu")
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("404.html"), 404
    

    @app.errorhandler(410)
    def gone_error(error):
        # generate random L00001 → L00500
        random_code = f"L{random.randint(1, 500):05d}"

        return render_template(
            "410.html",
            recruiter_code=getattr(error, "description", "Unknown"),
            random_recruiter=random_code,
            SUPPORT_EMAIL="jxs794@miami.edu"
        ), 410
    
    @app.route("/ligand-retired/<code>")
    def ligand_retired(code):
        random_code = f"L{random.randint(1,500):05d}"
        return render_template(
            "410.html",
            recruiter_code=code,
            random_recruiter=random_code,
            SUPPORT_EMAIL="jxs794@miami.edu"
        ), 410






    return app


# =============================================================================
#  MAGIC: AUTOMATIC PATH PREFIXING FOR /ligase
# =============================================================================
# This wrapper rewrites the HTTP SCRIPT_NAME so that Flask thinks it is under "/"
# while Tailscale Serve forwards paths under "/ligase".
#
# NO CHANGES NEEDED TO ROUTES OR FRONTEND.
# =============================================================================
class PrefixMiddleware(object):
    def __init__(self, app, prefix):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        # Only rewrite if path starts with the prefix
        if environ["PATH_INFO"].startswith(self.prefix):
            environ["SCRIPT_NAME"] = self.prefix
            environ["PATH_INFO"] = environ["PATH_INFO"][len(self.prefix):]

        return self.app(environ, start_response)


from Ligases.routes import increment_visits   # <-- MUST add

flask_app = create_app()

first_hit = {"done": False}

@flask_app.before_request
def register_visit_once():
    if not first_hit["done"]:
        increment_visits()
        first_hit["done"] = True

# Wrap the app so it lives under "/ligase"
# application = PrefixMiddleware(flask_app, prefix="/ligase")

application = flask_app


# =============================================================================
#  LOCAL DEV RUN
# =============================================================================
if __name__ == "__main__":
    flask_app.run(
        host="0.0.0.0",
        port=5025,
        debug=True
    )



