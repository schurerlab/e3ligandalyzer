# 🧬 E3 Ligandalyzer

<p align="center">
  <strong>E3 Ligandalyzer: a public, structure-first atlas for E3 ligase recruiters, scaffolds, SASA exposure, and downloadable PROTAC-design assets.</strong>
</p>

<p align="center">
  <em>Explore curated E3 ligase-recruiter complexes, inspect recruiter chemistry, compare scaffold families, download PDB/SDF/CSV data, and send recruiter assets into downstream degrader-design workflows.</em>
</p>

<p align="center">
  <a href="https://e3ligandalyzer.com">
    <img src="https://img.shields.io/badge/Launch-E3%20Ligandalyzer-success?style=for-the-badge&logo=flask" alt="Launch E3 Ligandalyzer">
  </a>
  <a href="https://e3ligandalyzer.com/explorer">
    <img src="https://img.shields.io/badge/Open-Recruiter%20Explorer-blue?style=for-the-badge&logo=plotly" alt="Open recruiter explorer">
  </a>
  <a href="https://e3ligandalyzer.com/api-reference">
    <img src="https://img.shields.io/badge/View-API%20Reference-orange?style=for-the-badge&logo=readthedocs" alt="View API reference">
  </a>
  <a href="https://e3ligandalyzer.com/download-manifest">
    <img src="https://img.shields.io/badge/Data-Download%20Manifest-blueviolet?style=for-the-badge&logo=databricks" alt="Open download manifest">
  </a>
</p>

<p align="center">
  <a href="https://github.com/Joey305/e3ligandalyzer">
    <img src="https://img.shields.io/badge/Repository-Joey305%2Fe3ligandalyzer-lightgrey?style=for-the-badge&logo=github" alt="GitHub repository">
  </a>
  <a href="mailto:jmschulz@med.miami.edu?subject=E3%20Ligandalyzer%20Question%20%2F%20Collaboration">
    <img src="https://img.shields.io/badge/Contact-Joseph%20M.%20Schulz-blue?style=for-the-badge&logo=gmail" alt="Contact Joseph M. Schulz">
  </a>
</p>

---

<a id="overview"></a>

## 🌍 Public Resource

**E3 Ligandalyzer** is a Flask-based web resource for targeted protein degradation researchers who need a practical way to move between E3 ligase biology, recruiter chemistry, structural files, scaffold families, and downloadable data.

The live public tool is available at:

* **Website:** [https://e3ligandalyzer.com](https://e3ligandalyzer.com)
* **Public API:** [https://e3ligandalyzer.com/api](https://e3ligandalyzer.com/api)
* **API Reference:** [https://e3ligandalyzer.com/api-reference](https://e3ligandalyzer.com/api-reference)
* **Download Manifest:** [https://e3ligandalyzer.com/download-manifest](https://e3ligandalyzer.com/download-manifest)

The project is designed to make the repository safe and useful as a public companion to the deployed resource while keeping production secrets, local databases, session state, and large runtime artifacts outside Git.

---

<a id="authors"></a>

## 👥 Authors

**Joseph M. Schulz**

University of Miami / Schürer Lab ecosystem

For scientific questions, data corrections, feature ideas, or collaboration:

<p align="center">
  <a href="mailto:jmschulz@med.miami.edu?subject=E3%20Ligandalyzer%20Question%20%2F%20Collaboration">
    <img src="https://img.shields.io/badge/Questions%20%2F%20Collaboration-jmschulz%40med.miami.edu-blue?style=for-the-badge" alt="Email Joseph M. Schulz">
  </a>
  <a href="https://e3ligandalyzer.com/contact">
    <img src="https://img.shields.io/badge/Public%20Page-Contact-lightgrey?style=for-the-badge" alt="Contact page">
  </a>
  <a href="https://e3ligandalyzer.com/report-issue">
    <img src="https://img.shields.io/badge/Submit-Data%20Issue-red?style=for-the-badge" alt="Report a data issue">
  </a>
</p>

---

<a id="tool-map"></a>

## 🧭 Tool Map

The public site exposes both human-facing pages and machine-readable API routes.

| Page | Purpose |
| --- | --- |
| [Home](https://e3ligandalyzer.com) | Public entry point for the E3 recruiter atlas. |
| [Explorer](https://e3ligandalyzer.com/explorer) | Interactive recruiter exploration with ligase, scaffold, recruiter-class, and QED filters. |
| [Ligases](https://e3ligandalyzer.com/ligases) | Ligase-centered overview for browsing curated E3 systems. |
| [Scaffolds](https://e3ligandalyzer.com/scaffolds) | Scaffold diversity, connectivity, and recruiter-family views. |
| [Scaffold Network](https://e3ligandalyzer.com/scaffold-network-full) | Full scaffold-network visualization. |
| `https://e3ligandalyzer.com/ligand/<LR#####>` | Direct recruiter detail page, including structure-linked assets when available. |
| `https://e3ligandalyzer.com/scaffolds/<scaffold_id>` | Direct scaffold detail page. |
| [Docs](https://e3ligandalyzer.com/docs) | Researcher-facing guide to the resource and common workflows. |
| [Methods](https://e3ligandalyzer.com/methods) | Dataset construction, curation, and analysis context. |
| [Schema](https://e3ligandalyzer.com/schema) | Table-level data model and field descriptions. |
| [Release](https://e3ligandalyzer.com/release) | Current public release notes, update policy, and snapshot context. |
| [API Reference](https://e3ligandalyzer.com/api-reference) | Endpoint examples for JSON, CSV, PDB, SDF, ZIP bundles, and manifests. |
| [Download Manifest](https://e3ligandalyzer.com/download-manifest) | Browser view of the machine-readable public download manifest. |
| [Case Studies](https://e3ligandalyzer.com/case-studies) | Applied examples for using E3 Ligandalyzer in degrader-design workflows. |
| [Contribute](https://e3ligandalyzer.com/contribute) | Submission path for new structures, corrections, and collaborator input. |
| [Report Issue](https://e3ligandalyzer.com/report-issue) | Structured issue-reporting page for suspicious records or broken assets. |
| [Feedback](https://e3ligandalyzer.com/feedback) | General feedback for usability, data coverage, and feature requests. |
| [FAQ](https://e3ligandalyzer.com/faq) | Quick answers for common data, API, and usage questions. |

---

<a id="features"></a>

## 🚀 Highlights

* **Structure-first recruiter browsing**
  * Navigate curated E3 ligase-recruiter complexes by ligase, recruiter code, PDB mapping, scaffold, and physicochemical descriptors.
  * Open direct recruiter pages with canonical `LR#####` identifiers.

* **Interactive molecular visualization**
  * Render 2D recruiter structures and SASA-aware recruiter depictions through RDKit-backed endpoints.
  * Load PDB/SDF assets for structural inspection, modeling, and downstream design work.

* **Scaffold and diversity analysis**
  * Compare Murcko-like scaffold groupings, scaffold classes, recruiter density, connectivity, Shannon diversity, and ligase-level scaffold distributions.
  * Move between scaffold dashboards, direct scaffold pages, and global scaffold-network views.

* **Public data access**
  * Pull JSON summaries, CSV table exports, PDB files, SDF files, and ZIP bundles from the public API.
  * Use the download manifest to discover available assets without manually guessing paths.

* **PROTAC Builder handoff**
  * Recruiter assets can be sent into the broader PROTAC Builder workflow, with public defaults pointing to [https://protacbuilder.com](https://protacbuilder.com).

* **Public-release oriented**
  * Production secrets are read from environment variables.
  * Local databases, sessions, logs, credential files, and runtime artifacts are ignored by Git.

---

<a id="quick-start"></a>

## ⚡ Quick Start

```bash
git clone https://github.com/Joey305/e3ligandalyzer.git
cd e3ligandalyzer

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python Ligase_app.py
```

Then open:

```text
http://127.0.0.1:5025
```

The local app defaults to port `5025`. Production deployments should set `PUBLIC_SITE_URL=https://e3ligandalyzer.com`.

---

<a id="configuration"></a>

## 🔐 Configuration

E3 Ligandalyzer is configured through environment variables. Do not commit real `.env` files.

| Variable | Purpose |
| --- | --- |
| `PUBLIC_SITE_URL` | Canonical public root URL. Defaults to `https://e3ligandalyzer.com`. |
| `PROTAC_BUILDER_BASE_URL` | Base URL for PROTAC Builder handoff links. Defaults to `https://protacbuilder.com`. |
| `E3_SUPPORT_EMAIL` | Public support/contact email shown in templates. |
| `E3_LOCAL_DB_PATH` | Local path to the primary Ligandalyzer SQLite database. |
| `E3_LOCAL_ELIAH_DB_PATH` | Local path to the ELiAH/tissue-expression SQLite database. |
| `E3_DATA_BACKEND` / `E3_USE_RANDY` | Enable remote RANDY-backed data access instead of local SQLite/files. |
| `E3_RANDY_BASE_URL` | Authenticated remote data-service URL. |
| `E3_RANDY_TOKEN` | Bearer token for the remote data service. Keep private. |
| `E3_SHIPMENT_STORAGE` | Shipment event storage mode: `auto`, `postgres`, `sqlite`, `randy`, or `csv-fallback`. |
| `DATABASE_URL` | Postgres URL for durable production storage when available. |
| `E3_SHIPMENT_DB_PATH` | Local SQLite path for shipment-count persistence. |

For Heroku or other production platforms, prefer config vars/secrets managers over files in the repository.

---

<a id="api"></a>

## ⚡ Public API

Set the canonical public API base URL:

```bash
export BASE="https://e3ligandalyzer.com/api"
```

Common discovery endpoints:

```bash
curl "$BASE/ligases"
curl "$BASE/global-stats"
curl "$BASE/download/manifest"
curl "$BASE/download/ligases"
curl "$BASE/download/recruiter-codes?ligase=CRBN&limit=25"
```

Recruiter and scaffold data:

```bash
curl "$BASE/descriptors/LR00001"
curl "$BASE/metadata/LR00001"
curl "$BASE/ligand-sasa/LR00001"
curl "$BASE/scaffold-data?ligase=CRBN"
curl "$BASE/scaffold-summary"
curl "$BASE/scaffold-clusters"
```

Downloads:

```bash
curl -L -o E3Ligandalyzer_CRBN_structures.zip "$BASE/download/ligase/CRBN/all.zip"
curl -L -o E3Ligandalyzer_LR00001_bundle.zip "$BASE/download/recruiter/LR00001.zip"
curl "$BASE/download/tables"
curl -L -o Ligase_Scaffold_Data.csv "$BASE/download/table/Ligase_Scaffold_Data.csv"
```

For the full maintained endpoint list and copy-paste examples, use the live [API Reference](https://e3ligandalyzer.com/api-reference).

---

<a id="project-structure"></a>

## 🧩 Project Structure

```text
e3ligandalyzer/
├── Ligase_app.py                 # Flask app factory, page routes, deployment entrypoint
├── Ligases/
│   ├── routes.py                 # Public API, data queries, rendering, downloads
│   ├── randy_client.py           # Authenticated remote data-service client
│   ├── shipment_store.py         # Durable shipment-count storage backends
│   └── <Ligase>/                 # Curated ligase folders and structure assets
├── Ligase_Table/                 # Public CSV table exports and data snapshots
├── static/                       # CSS, JavaScript, icons, RDKit assets, vendor assets
├── templates/                    # Flask/Jinja pages for the public web tool
├── scripts/                      # Maintenance and smoke-test utilities
├── RANDY/                        # Remote data-service helpers for private infrastructure
├── requirements.txt              # Python runtime dependencies
├── Procfile                      # Gunicorn process definition
└── README.md
```

---

<a id="public-release-safety"></a>

## ✅ Public Release Safety

Before moving the repository from private to public:

* Keep real `.env`, `.env.*`, credential JSON, key files, database files, local sessions, logs, and `instance/` state out of Git.
* Use `.env.example` only for placeholder values.
* Confirm production tokens are configured through Heroku config vars, GitHub secrets, or another secrets manager.
* Check the current diff before publishing:

```bash
git status --short
git diff -- README.md .gitignore
```

* Run a final targeted secret scan:

```bash
rg -n "sk-|ghp_|github_pat_|AKIA|AIza|xox[baprs]-|DATABASE_URL|TOKEN|SECRET|PASSWORD" .
```

The committed code should reference secret names, not secret values.

---

<a id="deployment"></a>

## 🚢 Deployment Notes

The app exposes `application = flask_app` for WSGI deployment and includes a `Procfile` for Gunicorn-based hosting.

Recommended production configuration:

```bash
PUBLIC_SITE_URL=https://e3ligandalyzer.com
PROTAC_BUILDER_BASE_URL=https://protacbuilder.com
E3_SUPPORT_EMAIL=jmschulz@med.miami.edu
E3_SHIPMENT_STORAGE=postgres
DATABASE_URL=<managed-postgres-url>
```

For deployments where large SQLite databases and molecular files are not stored on the app host, configure the RANDY-backed data service with:

```bash
E3_DATA_BACKEND=randy
E3_RANDY_BASE_URL=https://<private-randy-host>/backup/e3
E3_RANDY_TOKEN=<shared-secret>
```

---

<a id="citation"></a>

## 📚 Citation & Attribution

If you use E3 Ligandalyzer in research, cite or acknowledge the resource as:

> Schulz, J. M. E3 Ligandalyzer: a structure-first atlas for E3 ligase recruiters, scaffold analysis, and PROTAC-design data access.

Please also cite the original PDB structures, source datasets, and software libraries used in your downstream analysis as appropriate.

---

<a id="contact"></a>

## 🤝 Contact

Questions, corrections, collaborations, and feature requests are welcome.

* **Email:** [jmschulz@med.miami.edu](mailto:jmschulz@med.miami.edu?subject=E3%20Ligandalyzer%20Question%20%2F%20Collaboration)
* **Website:** [https://e3ligandalyzer.com](https://e3ligandalyzer.com)
* **Report an issue:** [https://e3ligandalyzer.com/report-issue](https://e3ligandalyzer.com/report-issue)
