#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
from datetime import datetime
from urllib.parse import quote, urlencode
from flask import Flask, render_template, send_from_directory, request, redirect, jsonify, abort
from Ligases.routes import ligases_bp, query_db, build_download_manifest
from Ligases import randy_client
from e3_database import E3DatabaseError, configured_asset_root, get_database
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Request

import random


logger = logging.getLogger(__name__)


def get_support_email() -> str:
    return (os.environ.get("E3_SUPPORT_EMAIL", "jmschulz@med.miami.edu") or "jmschulz@med.miami.edu").strip()


def get_public_site_url() -> str:
    return (os.environ.get("PUBLIC_SITE_URL", "https://e3ligandalyzer.com") or "https://e3ligandalyzer.com").rstrip("/")


def get_public_api_base() -> str:
    return f"{get_public_site_url()}/api"


def get_protac_builder_base_url() -> str:
    return (os.environ.get("PROTAC_BUILDER_BASE_URL", "https://protacbuilder.com") or "https://protacbuilder.com").rstrip("/")


def build_protac_builder_session_url(session_id: str) -> str:
    query = urlencode({"session": str(session_id or "").strip()})
    return f"{get_protac_builder_base_url()}/builder?{query}"


def _extract_scalar(row, key="value", fallback=None):
    if row is None:
        return fallback
    try:
        if isinstance(row, dict):
            return row.get(key, fallback)
        return row[key]
    except Exception:
        pass
    try:
        return row[0]
    except Exception:
        return fallback


def _safe_scalar(query, fallback=None):
    try:
        row = query_db(query, one=True)
        return _extract_scalar(row, fallback=fallback)
    except Exception:
        logger.exception("Release stat query failed: %s", query)
    return fallback


def build_release_stats():
    try:
        counts = get_database().release_counts()
        return {
            "ligases": counts["ligases"],
            "recruiter_records": counts["recruiter_entities"],
            "physical_instances": counts["recruiter_instances"],
            "pdb_structures": counts["distinct_pdbs"],
            "scaffolds": counts["scaffolds"],
            "complete_sasa": counts["recruiter_instances"],
        }
    except E3DatabaseError:
        logger.exception("V1 release statistics are unavailable")
        return {}


def build_release_context():
    database = get_database()
    metadata = database.release_metadata()
    stats = build_release_stats()

    return {
        "version_label": f"Version {metadata.get('Release_Version', 'unknown')}",
        "short_label": metadata.get("Schema_Version", "V1"),
        "release_state": "Immutable SQLite scientific release",
        "release_date": metadata.get("Release_Date", "Unknown"),
        "database_cutoff": metadata.get("Database_Cutoff_Date", "Unknown"),
        "update_cadence": "Annual review and update cycle",
        "update_policy": "New ligases, recruiter structures, scaffold annotations, and SASA-linked assets may be incorporated in future yearly releases after curation and validation.",
        "stats": stats,
        "download_table_count": int(metadata.get("Manifest_Source_Table_Count", 0) or 0),
        "stats_source_note": "Statistics and provenance are read from the immutable E3 Ligandalyzer V1 SQLite release.",
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

    app.config["PUBLIC_SITE_URL"] = get_public_site_url()
    app.config["PUBLIC_API_BASE"] = get_public_api_base()
    app.config["PROTAC_BUILDER_BASE_URL"] = get_protac_builder_base_url()
    app.config["SUPPORT_EMAIL"] = get_support_email()

    # Register your API blueprint normally (no prefix)
    app.register_blueprint(ligases_bp, url_prefix="/api")

    app.secret_key = os.urandom(24)

    @app.context_processor
    def inject_protac_builder_config():
        return {
            "PUBLIC_SITE_URL": app.config["PUBLIC_SITE_URL"],
            "PUBLIC_API_BASE": app.config["PUBLIC_API_BASE"],
            "PROTAC_BUILDER_BASE_URL": app.config["PROTAC_BUILDER_BASE_URL"],
            "SUPPORT_EMAIL": app.config["SUPPORT_EMAIL"],
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
        if code in LIGAND_REDIRECTS:
            target = LIGAND_REDIRECTS[code]
            return redirect(f"/ligand/{target}", code=302)

        database = get_database()
        resolved = database.entity_for_identifier(code)
        if resolved and resolved["kind"] == "entity":
            return redirect(f"/recruiter/{resolved['entity']['Recruiter_ID']}", code=302)
        if resolved and resolved["kind"] == "instance":
            return render_template(
                "ligand.html",
                initial_instance_id=resolved["instance"]["Recruiter_Instance_ID"],
            )

        legacy_entities = database.legacy_identifier_entities(code)
        if len(legacy_entities) == 1:
            return redirect(f"/recruiter/{legacy_entities[0]}", code=302)
        if len(legacy_entities) > 1:
            return redirect(f"/api/search/recruiters?q={code}", code=302)
        return render_template("missing_data.html"), 404

    @app.route("/recruiter/<recruiter_id>")
    def recruiter_page(recruiter_id):
        database = get_database()
        entity = database.recruiter_entity(recruiter_id)
        if not entity:
            return render_template("missing_data.html"), 404
        return render_template(
            "recruiter.html",
            recruiter=entity,
            instances=database.recruiter_instances(recruiter_id),
            ligases=database.entity_ligases(recruiter_id),
        )

    @app.route("/instance/<instance_id>")
    def instance_page(instance_id):
        database = get_database()
        instance = database.recruiter_instance(instance_id)
        if not instance:
            return render_template("missing_data.html"), 404
        return redirect(f"/ligand/{instance['Recruiter_Instance_ID']}", code=302)


    @app.route("/Ligases/<path:filename>")
    def serve_ligase_file(filename):
        # Compatibility URL only: its root is the selected release asset tree.
        # It must never quietly fall through to the historical Ligases directory.
        asset_root = configured_asset_root()
        if not asset_root or not asset_root.is_dir():
            abort(404)
        base_dir = asset_root / "Ligases"
        return send_from_directory(base_dir, filename)

    @app.route("/missing")
    def missing():
        return render_template("missing_data.html")

    @app.route("/about")
    def about():
        counts = get_database().release_counts()
        stats = {
            "total_ligases": counts["ligases"],
            "total_scaffolds": counts["scaffolds"],
            "total_complexes": counts["recruiter_instances"],
            "top_ligase": get_database().ligases()[0] if get_database().ligases() else "N/A",
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

    @app.route("/contact")
    def contact():
        return render_template("contact.html")

    @app.route("/feedback")
    def feedback():
        return render_template("feedback.html")

    @app.route("/faq")
    def faq():
        return render_template("faq.html")

    @app.route("/report-issue")
    def report_issue():
        return render_template("report_issue.html")

    @app.route("/case-studies")
    def case_studies():
        return render_template("case_studies.html")

    @app.route("/scaffold-network-full")
    def scaffold_network_full_page():
        return render_template("scaffold_network_full.html")

    @app.route("/scaffolds/<scaffold_id>")
    def scaffold_detail(scaffold_id):
        database = get_database()
        row = database.scaffold(scaffold_id)

        if not row:
            return render_template("missing_data.html")

        recruiters = database.scaffold_recruiters(scaffold_id)

        return render_template(
            "scaffold_detail.html",
            scaffold=row,
            recruiters=recruiters
        )
    

    @app.errorhandler(411)
    def missing_recruiter_error(error):
        code = getattr(error, "description", None)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Missing recruiter-linked data.", "recruiter_code": code}), 411
        return render_template("missing_recruiter.html", recruiter_code=code), 411
    
    @app.route("/missing-recruiter")
    def missing_recruiter():
        code = request.args.get("code", "UNKNOWN")
        return render_template("missing_recruiter.html", recruiter_code=code)
    
    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith("/api/"):
            description = getattr(error, "description", None) or "Not found."
            return jsonify({"error": description}), 404
        return render_template("404.html"), 404
    

    @app.errorhandler(410)
    def gone_error(error):
        # generate random L00001 → L00500
        random_code = f"L{random.randint(1, 500):05d}"

        return render_template(
            "410.html",
            recruiter_code=getattr(error, "description", "Unknown"),
            random_recruiter=random_code
        ), 410
    
    @app.route("/ligand-retired/<code>")
    def ligand_retired(code):
        random_code = f"L{random.randint(1,500):05d}"
        return render_template(
            "410.html",
            recruiter_code=code,
            random_recruiter=random_code
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



