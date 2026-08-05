# E3 Ligandalyzer Project and RANDY Database/Asset Deployment Guide

This document explains how the E3 Recruiter / Ligandalyzer project is wired today, what data it depends on, why that matters for GitHub and Heroku, and what must change so the app can run on Heroku while the heavy database and molecular files live on RANDY.

The goal is simple:

- Heroku hosts the public Flask web app.
- GitHub stores the code and lightweight assets.
- RANDY, the always-on lab computer, stores the heavy SQLite databases and molecular data files.
- The Heroku app talks to RANDY over authenticated HTTPS using bearer tokens, similar to the Warhead Hunter and PROTAC Builder setup.

## 1. What This Project Is

This repository is the E3 Ligase Atlas / E3 Ligandalyzer app. It is a Flask web application for exploring E3 ligases, recruiter ligands, scaffold diversity, PDB structures, SDF files, SASA exposure data, chemical descriptors, and ELiAH gene-expression data.

The main application entrypoint is:

```text
Ligase_app.py
```

The main API implementation is:

```text
Ligases/routes.py
```

The current production command is:

```text
gunicorn Ligase_app:application
```

That command comes from:

```text
Procfile
```

The app is currently designed around local files and local SQLite databases. That is the main deployment issue.

## 2. Current Top-Level Project Layout

Important top-level files and folders:

```text
Ligase_app.py                 Flask app factory and page routes
Ligases/routes.py             API routes, database queries, file serving, downloads
Ligases/Ligase_Recruiter.db   Main E3 SQLite database, about 6 MB
Ligases/eliah.db              ELiAH SQLite database, about 3.9 to 4.1 GB
Ligases/Ligase_Recruiter2.db  Secondary/older SQLite database, about 5 MB
Ligases/<ligase>/PDB/         PDB structure files
Ligases/<ligase>/SDF/         SDF ligand files
Ligases/<ligase>/SDF_4Download/  SDF download files
templates/                    Flask HTML templates
static/                       CSS, JavaScript, icons, local RDKit JS/WASM
Ligase_Table/                 CSV source tables used to build SQLite data
BUILDERscrits/                Data build pipeline scripts
FixerScripts/                 Repair/cleanup scripts
tmp_sessions/                 Runtime/generated SDF session files
Procfile                      Heroku/Gunicorn process definition
environment.yml               Conda environment reference
package.json                  Tailwind/PostCSS development dependencies
```

Approximate size observations from the current workspace:

```text
Whole project:                 about 12 GB
Ligases folder:                about 6.3 GB
Ligases/eliah.db:              about 3.9 GB
Ligases/Ligase_Recruiter.db:   about 6.2 MB
Ligases/Ligase_Recruiter2.db:  about 5.2 MB
static folder:                 about 1.4 MB
templates folder:              about 496 KB
Ligase_Table folder:           about 3.2 MB
```

This size profile is the reason we should not push the data tree or `eliah.db` directly to GitHub or Heroku.

## 3. How The Flask App Starts

`Ligase_app.py` defines a `create_app()` factory.

Important behavior:

1. Creates the Flask app using local `static/` and `templates/`.
2. Registers the API blueprint from `Ligases.routes` at `/api`.
3. Defines normal frontend pages such as `/`, `/explorer`, `/ligases`, `/scaffolds`, `/about`, `/docs`, and `/contribute`.
4. Serves files under `/Ligases/<path:filename>` from the local `Ligases/` folder.
5. Imports `query_db()` from `Ligases.routes` and uses it directly for page-level stats.
6. Imports `increment_visits()` from `Ligases.routes` and calls it once on first request.
7. Exposes `application = flask_app`, which is what Gunicorn uses.

Local development runs here:

```text
host=0.0.0.0
port=5025
debug=True
```

Heroku runs this:

```text
web: gunicorn Ligase_app:application
```

There is a `PrefixMiddleware` class for serving the app under `/ligase`, probably for Tailscale Serve or a reverse proxy, but it is currently not active. The active line is:

```python
application = flask_app
```

## 4. Main Page Routes

These are defined in `Ligase_app.py`.

```text
GET /                         Home page
GET /explorer                 3D/PDB explorer page
GET /scaffolds                Scaffold dashboard page
GET /ligases                  Ligase/ELiAH page
GET /ligand/<code>            Recruiter ligand page
GET /Ligases/<path:filename>  Direct local Ligases file serving
GET /missing                  Missing data page
GET /about                    About/statistics page
GET /docs                     Documentation page
GET /api-reference            API reference page
GET /contribute               Contribution page
GET /scaffold-network-full    Full scaffold network page
GET /scaffolds/<scaffold_id>  Scaffold detail page
GET /missing-recruiter        Missing recruiter page
GET /ligand-retired/<code>    Retired recruiter page
```

The `/about` page currently queries the local SQLite database directly through `query_db()`.

## 5. Main API Routes

These are defined in `Ligases/routes.py` and mounted under `/api`.

Common dataset routes:

```text
GET /api/ligases
GET /api/featured-recruiters
GET /api/scaffold-data
GET /api/scaffold-summary
GET /api/scaffold-frequency
GET /api/scaffold-recruiters
GET /api/descriptors/<recruiter_code>
GET /api/metadata/<recruiter_code>
GET /api/ligase-summary
GET /api/recruiter-class-summary
GET /api/scaffold-class-summary
GET /api/ligase-ligand-stats
GET /api/global-stats
```

Structure and chemistry routes:

```text
GET /api/render-smiles/<smiles>
GET /api/render-smiles-by-code/<recruiter_code>
GET /api/render-2d-sasa/<recruiter_code>
GET /api/ligase-pdbs/<ligase>
GET /api/Ligases/<ligase>/PDB/<filename>
GET /api/render-sdf/<ligase>/<filename>
GET /api/recruiter-by-pdb
GET /api/ligand-sasa/<recruiter_code>
GET /api/ligand-visual/<recruiter_code>
GET /api/sasa-atoms/<recruiter_code>
GET /api/sasa-full/<recruiter_code>
GET /api/sasa-summary/<recruiter_code>
GET /api/scaffold/<recruiter_code>
GET /api/random-recruiter
GET /api/fixed-2d-smiles/<recruiter>
GET /api/scaffold-clusters
```

ELiAH routes:

```text
GET /api/eliah/ligases
GET /api/eliah/genes
GET /api/eliah/expression
GET /api/eliah/tissues
GET /api/eliah/tissue_profile
GET /api/eliah/search
GET /api/eliah/autocomplete
GET /api/eliah/expression_filter
```

Download/export routes:

```text
GET /api/download/manifest
GET /api/download/ligases
GET /api/download/recruiter-codes
GET /api/download/pdb/<ligase>/<filename>
GET /api/download/sdf/<ligase>/<filename>
GET /api/download/ligase/<ligase>/<asset_type>.zip
GET /api/download/all/<asset_type>.zip
GET /api/download/recruiter/<recruiter_code>.zip
GET /api/download/recruiters.zip
GET /api/download/tables
GET /api/download/table/<table_name>.csv
```

Runtime/helper routes:

```text
POST /api/convert_atom_to_v
GET /api/serve_session/<session_id>
GET /api/shipped-count
GET /api/visits
GET /api/tooltip/descriptors/<recruiter_code>
GET /api/tooltip/metadata/<recruiter_code>
GET /api/tooltip/all/<recruiter_code>
GET /api/search/recruiters
```

## 6. Current Database Setup

`Ligases/routes.py` hardcodes the two database paths:

```python
DB_PATH = os.path.join(os.path.dirname(__file__), "Ligase_Recruiter.db")
ELIAH_DB_PATH = os.path.join(os.path.dirname(__file__), "eliah.db")
```

So today the app expects:

```text
Ligases/Ligase_Recruiter.db
Ligases/eliah.db
```

This means Heroku would need those files inside the dyno filesystem unless we change the code.

That is a problem because:

- Heroku dynos have ephemeral filesystems.
- Large files should not live in the slug.
- GitHub is not the right place for multi-GB database files.
- `Ligases/eliah.db` is around 4 GB by itself.
- The full project is around 12 GB.

The main E3 database is small enough to bundle technically, but it still may be better to serve it from RANDY so there is one canonical data source.

## 7. Main SQLite Database Tables

The main SQLite database is:

```text
Ligases/Ligase_Recruiter.db
```

Current important row counts:

```text
Ligase_Chemical_Descriptors       602
Ligase_Ligand_Metadata            602
Ligase_Ligand_SASA_summary        602
Ligase_Ligand_SASA_atoms          16710
Ligase_Ligands_Smiles_3DMapped    16609
Ligase_Recruiters_Scaffold        602
Ligase_Scaffold_Data              388
Recruiter_Master_Map              602
```

Detected tables:

```text
Ligand_Instance_Recruiter_Codes
Ligase_Chemical_Descriptors
Ligase_Duplicate_Ligands
Ligase_Ligand_Metadata
Ligase_Ligand_SASA_atoms
Ligase_Ligand_SASA_summary
Ligase_Ligands_Smiles
Ligase_Ligands_Smiles_3DMapped
Ligase_Recruiters_Scaffold
Ligase_Recruiters_Superclustered
Ligase_SMILE_Codes
Ligase_SMILE_Codes_Atoms
Ligase_Scaffold_Data
Ligase_Scaffold_Frequency
Ligase_Scaffold_Summary
Ligase_Scaffold_Supercluster_Frequency
Ligase_Scaffold_Supercluster_Matrix
Ligase_Scaffold_Superclusters
Recruiter_Code_Crosswalk
Recruiter_Master_Map
Recruiter_SMILES_Map
Recruiter_SMILES_Wide
Scaffold_Unified_Map
```

The data model is mostly read-only from the web app's point of view. The API queries tables and returns JSON, SVG, CSV, ZIP files, or molecular files.

## 8. ELiAH Database

The ELiAH database is:

```text
Ligases/eliah.db
```

It is large:

```text
about 3.9 GB
```

The app uses this for the `/api/eliah/*` routes. The code expects tables such as:

```text
ligase_list
gene_expression_normalized
```

and likely tissue/sample-related tables used by the tissue and search endpoints.

This database is the strongest reason to use RANDY. It should not be committed to GitHub and should not be placed in a Heroku slug.

## 9. Molecular Asset Setup

The app also depends on files inside:

```text
Ligases/<Ligase>/PDB/*.pdb
Ligases/<Ligase>/SDF/*.sdf
Ligases/<Ligase>/SDF_4Download/*.sdf
```

Examples:

```text
Ligases/VHL/PDB/4W9F_3JU_1.pdb
Ligases/CRBN/SDF/CRBN_Y70.sdf
Ligases/VHL/SDF_4Download/4W9F_3JU.sdf
```

Frontend pages fetch these through API routes such as:

```text
/api/ligase-pdbs/<ligase>
/api/Ligases/<ligase>/PDB/<filename>
/api/render-sdf/<ligase>/<filename>
/api/download/pdb/<ligase>/<filename>
/api/download/sdf/<ligase>/<filename>
/api/download/ligase/<ligase>/<asset_type>.zip
/api/download/all/<asset_type>.zip
```

Right now those routes use local filesystem access. If Heroku does not have the `Ligases/` tree, those routes will fail unless they proxy to RANDY.

## 10. Frontend Flow

The app templates are not static-only pages. They call many backend APIs.

Important examples:

`templates/index.html`:

```text
/api/ligases
/api/scaffold-class-summary
/api/recruiter-class-summary
/api/featured-recruiters
/api/render-smiles/<smiles>
```

`templates/explorer.html`:

```text
/api/ligase-pdbs/<ligase>
/api/Ligases/<ligase>/PDB/<file>
/api/recruiter-by-pdb
/api/render-sdf/<ligase>/<pdb_file>
/api/convert_atom_to_v
```

`templates/ligand.html`:

```text
/api/ligand-visual/<recruiter_code>
/api/fixed-2d-smiles/<recruiter_code>
/api/render-2d-sasa/<recruiter_code>
/api/render-smiles/<smiles>
/api/scaffold/<recruiter_code>
/api/render-sdf/<ligase>/<pdb_file>
```

`templates/scaffolds.html` and `templates/scaffold_network_full.html`:

```text
/api/scaffold-data
/api/scaffold-clusters
/api/render-smiles/<smiles>
```

`templates/ligases.html`:

```text
/api/eliah/ligases
/api/eliah/genes
/api/eliah/expression
/api/eliah/tissues
/api/eliah/tissue_profile
/api/eliah/expression_filter
/api/eliah/autocomplete
/api/eliah/search
```

This matters because moving data to RANDY is not only a database change. The Heroku app needs a remote data and asset access strategy for the pages to continue working.

## 11. Current Build Pipeline

The app's displayed database appears to be built from CSVs in:

```text
Ligase_Table/
```

The simple build script is:

```text
BUILDERscrits/16__BUILDdb.py
```

That script:

1. Reads every CSV in `Ligase_Table/`.
2. Creates one SQLite table per CSV file.
3. Writes a SQLite database named `Ligase_Recruiter.db`.
4. Replaces the existing database if `REPLACE_EXISTING = True`.

Important mismatch:

`16__BUILDdb.py` writes to:

```text
Ligase_Recruiter.db
```

in the current working directory, but the web app reads:

```text
Ligases/Ligase_Recruiter.db
```

So after rebuilding, the final database likely needs to be copied or built directly into `Ligases/Ligase_Recruiter.db`.

There are many additional data preparation scripts in:

```text
BUILDERscrits/
FixerScripts/
```

These fetch ligase structures, clean PDBs, compute SASA, map SMILES, compute descriptors, generate scaffolds, and repair duplicate/missing records. They are not normal Heroku runtime code. They are data build/maintenance tools.

## 12. RANDY Pattern In The Other Projects

The existing RANDY service is in:

```text
/path/to/warhead-hunter/RANDY/app.py
```

That service is a Flask app. It uses:

```text
PROTAC_BACKUP_TOKEN
PROTAC_BACKUP_DIR
WARHEAD_HUNTER_JOBS_DIR
```

It authenticates requests with:

```text
Authorization: Bearer <token>
```

It stores data into:

```text
protac_backup.sqlite3
protac_events.jsonl
protac_events.csv
protac_components.csv
protac_linker_library_usage.csv
warhead_hunter_handoffs.csv
warhead_hunter_job_archives.csv
```

It exposes endpoints such as:

```text
GET  /healthz
POST /backup/protac-event
POST /backup/protac-events
GET  /backup/summary
GET  /backup/events
GET  /backup/protacs
GET  /backup/components
GET  /backup/linker-libraries
POST /backup/hunter-job-files
POST /backup/hunter-job-archive
POST /backup/hunter-job-materialize
GET  /backup/hunter-jobs
GET  /backup/hunter-job/<job_id>
GET  /backup/hunter-job/<job_id>/file/<relative_path>
```

Warhead Hunter and PROTAC Builder use small Python clients to talk to RANDY.

Important existing env var pattern:

```text
RANDY_BACKUP_BASE_URL
RANDY_ARCHIVE_BASE_URL
RANDY_BACKUP_TOKEN
RANDY_ARCHIVE_TOKEN
WARHEAD_HANDOFF_TOKEN
PROTAC_BACKUP_TOKEN
WARHEAD_HUNTER_JOB_API_BASE
WARHEAD_HUNTER_JOB_API_TOKEN
```

The client pattern is:

1. Read base URL and token from environment variables.
2. Normalize the base URL.
3. Send HTTP requests with `Authorization: Bearer <token>`.
4. Treat RANDY as the remote source of truth.
5. Optionally cache downloaded files locally as an optimization, not as the authority.

For E3, we should copy this pattern, but the endpoints should serve E3 database queries and E3 molecular assets rather than Warhead Hunter jobs.

## 13. The Best RANDY Architecture For E3

Recommended architecture:

```text
Browser
  |
  v
Heroku Flask app
  |
  | authenticated server-to-server HTTPS
  v
RANDY E3 data service
  |
  v
Local SQLite databases and Ligases/ molecular asset folder
```

The browser should not need the RANDY token. The browser should call Heroku. Heroku should call RANDY.

Why:

- The token stays secret in Heroku config vars.
- The public web app can keep the same `/api/...` URLs.
- RANDY can stay behind Tailscale/Funnel or another controlled public endpoint.
- Heroku remains lightweight.
- GitHub does not need the giant data files.

## 14. Required New Environment Variables

On Heroku for the E3 app:

```text
E3_DATA_BACKEND=remote
E3_RANDY_BASE_URL=https://randy.example-or-tailscale-name/backup/e3
E3_RANDY_TOKEN=<shared-secret-token>
E3_RANDY_TIMEOUT_SECONDS=30
E3_PUBLIC_BASE_URL=https://your-heroku-app.herokuapp.com
FLASK_SECRET_KEY=<stable-secret-key>
```

Optional:

```text
E3_LOCAL_DB_PATH=Ligases/Ligase_Recruiter.db
E3_LOCAL_ELIAH_DB_PATH=Ligases/eliah.db
E3_LOCAL_ASSET_ROOT=Ligases
E3_REMOTE_CACHE_DIR=/tmp/e3_remote_cache
```

On RANDY:

```text
E3_RANDY_TOKEN=<same-shared-secret-token>
E3_DATA_DIR=/absolute/path/to/E3Recruiter_Ligandalyzer
E3_DB_PATH=/absolute/path/to/E3Recruiter_Ligandalyzer/Ligases/Ligase_Recruiter.db
E3_ELIAH_DB_PATH=/absolute/path/to/E3Recruiter_Ligandalyzer/Ligases/eliah.db
E3_ASSET_ROOT=/absolute/path/to/E3Recruiter_Ligandalyzer/Ligases
```

After the initial RANDY copy, the current known database paths are:

```text
E3_DB_PATH=/srv/e3-ligandalyzer/Databases/Ligase_Recruiter.db
E3_ELIAH_DB_PATH=/srv/e3-ligandalyzer/Databases/eliah.db
```

The molecular asset root still needs to exist on RANDY before PDB/SDF routes can be fully remote:

```text
E3_ASSET_ROOT=/srv/e3-ligandalyzer/Ligases
```

If only the databases have been copied so far, database-backed JSON routes can be wired first, but PDB/SDF viewer and download routes still need the `Ligases/<ligase>/PDB`, `SDF`, and `SDF_4Download` asset tree copied or mounted on RANDY.

Use a separate E3 token if possible instead of reusing `PROTAC_BACKUP_TOKEN`. Reusing the old token works, but separate tokens make it easier to revoke one tool without breaking the others.

## 15. Required RANDY Endpoints For E3

RANDY needs a small E3 data service integrated into the existing shared RANDY Flask app.

The preferred workflow in this repo is:

```text
Edit and validate the copied RANDY app in:
RANDY/app.py

and the helper module it imports:
RANDY/e3_data_routes.py
```

After validation, those RANDY-side changes can be manually copied back into the real RANDY deployment.

E3 routes should live under this prefix on the shared RANDY server:

```text
/backup/e3
```

Heroku should use:

```text
E3_RANDY_BASE_URL=https://<randy-public-host>/backup/e3
```

Required endpoints:

```text
GET  /backup/e3/healthz
POST /backup/e3/query
GET  /backup/e3/ligase-pdbs/<ligase>
GET  /backup/e3/file/pdb/<ligase>/<path:filename>
GET  /backup/e3/file/sdf/<ligase>/<path:filename>
GET  /backup/e3/download/ligase/<ligase>/<asset_type>.zip
GET  /backup/e3/download/all/<asset_type>.zip
GET  /backup/e3/download/table/<table_name>.csv
```

The old standalone file:

```text
RANDY_E3_DATA_SERVER.py
```

should now be treated as a deprecated compatibility/reference copy, not the preferred production runtime path.

The most important endpoint is `/backup/e3/query`. It should accept a safe query contract, not arbitrary SQL from the public internet.

The current bridge contract is a read-only SQL allowlist:

```json
{
  "database": "main",
  "sql": "SELECT DISTINCT Ligase FROM Ligase_Scaffold_Data ORDER BY Ligase",
  "params": []
}
```

The `/backup/e3/query` endpoint should only allow:

- `SELECT` or `WITH` statements.
- Parameterized queries.
- A maximum row limit.
- No semicolon-separated multi-statements.
- No writes, schema changes, `PRAGMA`, or destructive SQL.

## 16. Required Heroku Code Changes

Right now `Ligases/routes.py` opens SQLite directly:

```python
conn = sqlite3.connect(DB_PATH)
```

We need to introduce a data access layer so route code does not care whether data is local or remote.

Recommended new files:

```text
Ligases/data_client.py
Ligases/randy_client.py
```

Current implementation note: this repo now has `Ligases/randy_client.py`, and the existing `query_db()` / `query_eliah_db()` helpers in `Ligases/routes.py` switch to RANDY when:

```text
E3_DATA_BACKEND=remote
```

Local SQLite remains the default for development when `E3_DATA_BACKEND` is unset.

`Ligases/data_client.py` should expose:

```python
query_db(query, args=(), one=False)
query_eliah_db(query, args=(), one=False)
asset_url_or_proxy(...)
download_asset(...)
```

`Ligases/randy_client.py` should:

1. Read `E3_RANDY_BASE_URL`.
2. Read `E3_RANDY_TOKEN`.
3. Send authenticated requests to RANDY.
4. Handle timeouts and 404s cleanly.
5. Return rows in the same shape currently returned by SQLite.

Then change `Ligases/routes.py` so the route functions call the data layer instead of raw `sqlite3.connect(...)`.

This remote behavior should remain in place. The RANDY-side change is to make the existing shared RANDY app answer the `/backup/e3/*` requests instead of running a separate E3-only Flask process.

## 17. Required File-Serving Changes

The app currently serves local files with `send_from_directory()` or `send_file()`.

Routes that must change for Heroku/RANDY:

```text
/api/ligase-pdbs/<ligase>
/api/Ligases/<ligase>/PDB/<filename>
/api/render-sdf/<ligase>/<filename>
/api/download/pdb/<ligase>/<filename>
/api/download/sdf/<ligase>/<filename>
/api/download/ligase/<ligase>/<asset_type>.zip
/api/download/all/<asset_type>.zip
/api/download/recruiter/<recruiter_code>.zip
/api/download/recruiters.zip
/Ligases/<path:filename>
```

For single files, Heroku can either:

1. Proxy bytes from RANDY to the browser.
2. Return a short-lived signed RANDY URL.

Proxying is simpler and keeps RANDY private. It means Heroku receives the file from RANDY and streams it to the browser.

For ZIP downloads, there are two choices:

1. Build ZIPs on RANDY and stream them through Heroku.
2. Build ZIPs on Heroku after fetching many files from RANDY.

Use option 1. RANDY has the files locally. Heroku should not do heavy ZIP assembly for thousands of molecular files.

## 18. GitHub Cleanup Before Push

Do not push the full current tree to GitHub as-is.

Add or verify `.gitignore` entries for:

```text
node_modules/
__pycache__/
*.pyc
.DS_Store
tmp_sessions/
logs/
*.log
*.db
*.sqlite
*.sqlite3
Ligases/**/*.db
Ligases/eliah.db
Ligases/Ligase_Recruiter*.db
Ligases/*/PDB/
Ligases/*/SDF/
Ligases/*/SDF_4Download/
*.pdb
*.sdf
*.pse
```

Be careful with CSVs. Some CSVs are source data and may belong in GitHub, especially the small `Ligase_Table/*.csv` files. Large generated CSVs and logs should stay out unless they are intentionally versioned.

A clean GitHub-friendly repo should contain:

```text
Application Python code
Templates
Static CSS/JS/icons
Small documented source CSVs if needed
Build scripts
README and this deployment guide
Procfile
requirements.txt or equivalent dependency files
```

It should not contain:

```text
eliah.db
Large SQLite files
PDB/SDF bulk datasets
node_modules
tmp session outputs
huge logs
generated ZIPs
```

## 19. Heroku Dependency Cleanup

Current dependency declaration is `environment.yml`, which is useful for conda but not enough for standard Heroku Python deployment.

Heroku normally expects:

```text
requirements.txt
runtime.txt
Procfile
```

The app uses:

```text
Flask
gunicorn
pandas
numpy
rdkit
biopython
sqlalchemy
matplotlib
requests
```

`requests` will be needed for RANDY access.

RDKit can be tricky on Heroku. Options:

1. Use `rdkit-pypi` if compatible with the Python version.
2. Use conda buildpack.
3. Move RDKit rendering to RANDY too, and let Heroku avoid RDKit.

The app currently renders SMILES/SASA SVGs through RDKit in Flask routes. If Heroku RDKit installation becomes painful, the clean architecture is to move RDKit render endpoints to RANDY and have Heroku proxy them.

## 20. Security Model

The RANDY token must never be placed in frontend JavaScript or templates.

Correct:

```text
Browser -> Heroku /api/...
Heroku -> RANDY with Authorization: Bearer token
RANDY -> Heroku
Heroku -> Browser
```

Incorrect:

```text
Browser -> RANDY directly with token embedded in JS
```

RANDY should validate:

```text
Authorization: Bearer <E3_RANDY_TOKEN>
```

RANDY should reject missing or wrong tokens with HTTP 401.

RANDY should also prevent unsafe file paths:

- No `..`
- No absolute paths from user input
- Only serve files under `E3_ASSET_ROOT`
- Only allow expected extensions such as `.pdb`, `.sdf`, `.csv`, `.zip`, `.json`, `.svg`

## 21. Recommended Migration Plan

Phase 1: Document and freeze current state.

1. Keep this guide in the repo.
2. Identify exactly which files are code and which are generated data.
3. Add `.gitignore`.
4. Decide whether `Ligase_Table/*.csv` should be committed.

Phase 2: Add local/remote data abstraction.

1. Add `Ligases/data_client.py`.
2. Move `query_db()` and `query_eliah_db()` behind that layer.
3. Keep local SQLite as default for development.
4. Add remote mode controlled by `E3_DATA_BACKEND=remote`.

Phase 3: Add E3 endpoints to RANDY.

1. Add `/backup/e3/healthz`.
2. Add authenticated `/backup/e3/query`.
3. Add authenticated file-serving endpoints for PDB and SDF.
4. Add RANDY-side ZIP creation endpoints for downloads.

Phase 4: Convert Heroku app to use RANDY.

1. Set `E3_DATA_BACKEND=remote`.
2. Set `E3_RANDY_BASE_URL`.
3. Set `E3_RANDY_TOKEN`.
4. Test core pages:
   - `/`
   - `/explorer`
   - `/ligand/LRxxxxx`
   - `/scaffolds`
   - `/ligases`
   - `/about`
5. Test core APIs:
   - `/api/ligases`
   - `/api/featured-recruiters`
   - `/api/ligand-visual/<code>`
   - `/api/eliah/ligases`
   - `/api/render-sdf/<ligase>/<file>`
   - `/api/download/manifest`

Phase 5: Push code to GitHub.

1. Confirm no big files are staged.
2. Confirm no tokens are in the repo.
3. Push only code and lightweight supporting files.

Phase 6: Deploy Heroku.

1. Create Heroku app.
2. Set config vars.
3. Deploy from GitHub or CLI.
4. Confirm Heroku can reach RANDY.
5. Confirm RANDY logs show E3 requests.

## 22. Minimal Test Checklist

Local app with local DB:

```bash
python Ligase_app.py
curl http://127.0.0.1:5025/api/ligases
curl http://127.0.0.1:5025/api/global-stats
```

RANDY E3 service:

```bash
curl -H "Authorization: Bearer $E3_RANDY_TOKEN" \
  "$E3_RANDY_BASE_URL/healthz"
```

Heroku app in remote mode:

```bash
curl https://your-heroku-app.herokuapp.com/api/ligases
curl https://your-heroku-app.herokuapp.com/api/global-stats
curl https://your-heroku-app.herokuapp.com/api/eliah/ligases
```

File serving:

```bash
curl -I https://your-heroku-app.herokuapp.com/api/download/manifest
curl -I https://your-heroku-app.herokuapp.com/api/download/ligases
```

## 22A. Immediate RANDY Service Setup From Current State

The preferred RANDY deployment path is to integrate the E3 routes into the existing RANDY Flask server, not to run:

```text
python RANDY_E3_DATA_SERVER.py
```

Use this repo's copied RANDY files as the edit/validation area:

```text
RANDY/app.py
RANDY/e3_data_routes.py
```

Then manually copy the validated RANDY-side changes back to the real RANDY app.

RANDY should be configured with:

```bash
export E3_RANDY_TOKEN="replace-with-the-token-you-saved"
export E3_DATA_DIR="/absolute/path/to/E3Recruiter_Ligandalyzer"
export E3_DB_PATH="/absolute/path/to/E3Recruiter_Ligandalyzer/Ligases/Ligase_Recruiter.db"
export E3_ELIAH_DB_PATH="/absolute/path/to/E3Recruiter_Ligandalyzer/Ligases/eliah.db"
export E3_ASSET_ROOT="/absolute/path/to/E3Recruiter_Ligandalyzer/Ligases"
export E3_TABLE_ROOT="/absolute/path/to/E3Recruiter_Ligandalyzer/Ligase_Table"
```

Heroku should be configured with:

```bash
heroku config:set E3_DATA_BACKEND=remote
heroku config:set E3_RANDY_BASE_URL="https://<randy-public-host>/backup/e3"
heroku config:set E3_RANDY_TOKEN="replace-with-the-same-token"
heroku config:set E3_RANDY_TIMEOUT_SECONDS=30
```

Local remote-mode test from this repo:

```bash
export E3_DATA_BACKEND=remote
export E3_RANDY_BASE_URL="https://<randy-public-host>/backup/e3"
export E3_RANDY_TOKEN="replace-with-the-same-token"
python Ligase_app.py
```

Then test:

```bash
curl http://127.0.0.1:5025/api/ligases
curl http://127.0.0.1:5025/api/global-stats
curl http://127.0.0.1:5025/api/eliah/ligases
```

If database routes work but PDB/SDF routes fail, copy the `Ligases/<ligase>/PDB`, `Ligases/<ligase>/SDF`, and `Ligases/<ligase>/SDF_4Download` folders to:

```text
/srv/e3-ligandalyzer/Ligases
```

Browser pages:

```text
/
/about
/explorer
/scaffolds
/ligases
/api-reference
```

## 23. Known Issues Found During Crawl

These are not all fatal, but they matter before production deployment.

1. Database paths are hardcoded to local files in `Ligases/routes.py`.
2. `Ligases/eliah.db` is around 4 GB and cannot be treated like a normal repo/deployment file.
3. The molecular asset tree is large and currently assumed to exist locally.
4. Some routes duplicate or overlap, especially PDB serving and scaffold page handling.
5. `Ligases/__init__.py` defines a blueprint with `url_prefix='/api/ligases'`, but `Ligase_app.py` imports the blueprint from `Ligases.routes` and registers it at `/api`. The active route behavior comes from `Ligases.routes`.
6. Some runtime routes write local files, such as visit and shipment logs. Heroku filesystem writes are ephemeral, so these should move to RANDY or another persistent store.
7. `BUILDERscrits/16__BUILDdb.py` writes `Ligase_Recruiter.db` in the current directory, while the app reads `Ligases/Ligase_Recruiter.db`.
8. Broad `git status` is slow in this workspace because of large data and dependency trees. Git hygiene needs attention before pushing.
9. There are zero-byte database-looking files at the project root:
   - `Ligase_Recruiter.db`
   - `Ligase.db`
   These should not be confused with the real app database in `Ligases/Ligase_Recruiter.db`.

## 24. Plain-English Summary

Right now the E3 app works like this:

```text
Flask app opens local SQLite files and local PDB/SDF files directly.
```

That is fine on a lab machine, but it is not fine for Heroku.

The Heroku version should work like this:

```text
Flask app on Heroku receives browser requests.
For data or files, Heroku asks RANDY using a secret bearer token.
RANDY reads the real SQLite databases and molecular files from disk.
RANDY sends the result back to Heroku.
Heroku sends the final JSON/file/SVG/CSV/ZIP response to the browser.
```

That keeps GitHub clean, keeps Heroku lightweight, and lets RANDY remain the free always-on database/file host.
