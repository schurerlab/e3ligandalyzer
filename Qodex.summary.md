# Qodex.summary

## Task
Audit and Fix API Reference Commands

## Original Goal
Test every command added to the E3 Ligase Ligandalyzer API Reference page and fix any broken backend routes, examples, manifests, or downloads so the documented commands work against `https://e3ligandalyzer.com/api`.

## Assumptions
- The canonical public API base is `https://e3ligandalyzer.com/api`.
- The deployed public app may run in remote Randy-backed mode even when local development runs against the checked-in SQLite/filesystem snapshot.
- The public API Reference should only show commands that were validated locally after the code changes, and public production should be re-smoke-tested after deployment.
- `LR00001` is a verified recruiter-centric example for descriptors, SMILES, ligand-visual, SASA, and SVG rendering in the local dataset.
- `CRBN` is a verified ligase example for download discovery and ligase bundle examples.
- `LR00006,LR00007,LR00008` are verified CRBN recruiter bundle examples in the local dataset and align with recruiter-code discovery output.

## Files Inspected
- `templates/api-reference.html` — inventoried every documented Bash, Python, CSV, ZIP, and browser-JS example and checked which endpoints were missing or misleading.
- `templates/download_manifest.html` — verified how human-readable manifest links depend on raw manifest content.
- `Ligase_app.py` — inspected API/public error handling and found the app-level 404 handler overriding API JSON behavior.
- `Ligases/routes.py` — inspected download manifest generation, recruiter bundle routes, recruiter-code discovery, SASA routes, ligand-visual, descriptor lookup, CSV exports, and SVG rendering.
- `Ligases/randy_client.py` — inspected Randy query/proxy behavior and found it could surface upstream request URLs in raised exceptions.
- `RANDY/e3_data_routes.py` — inspected available remote backup endpoints to understand what the public app can already proxy or query.
- `Qodex.summary.md` — replaced with this task summary.

## Files Changed
- `Ligase_app.py`
  - Added JSON behavior for API-path 404 and 411 responses so bad API calls do not render HTML site pages.
- `Ligases/routes.py`
  - Added API JSON error handlers.
  - Fixed manifest/download ligase discovery to stop depending only on local asset folders.
  - Added remote-aware asset resolution helpers.
  - Fixed `/api/download/ligases` to return real ligase entries and bundle URLs.
  - Fixed `/api/download/recruiter-codes` to report working downloadable recruiter examples.
  - Added remote-mode support for `/api/download/recruiter/<code>.zip` and `/api/download/recruiters.zip`.
  - Fixed `/api/sasa-full/<code>` to query real columns and return clean JSON.
  - Fixed `/api/sasa-atoms/<code>` JSON serialization.
  - Fixed `/api/render-smiles-by-code/<code>` so valid SVG renders succeed and errors return JSON.
  - Changed `/api/descriptors/<code>` to return a clean 404 JSON error for unknown recruiter codes.
- `Ligases/randy_client.py`
  - Added sanitized remote-service error handling.
  - Added remote file existence checks and byte-download helpers.
  - Prevented upstream Randy URLs from leaking through raw `requests` exception strings.
- `templates/api-reference.html`
  - Added a clearer “Run this first” BASE setup block.
  - Added troubleshooting for empty `$BASE`.
  - Added the missing `all/sdfs.zip` example.
  - Added the missing `Ligase_Ligand_SASA_atoms.csv` and `Ligase_Recruiters_Scaffold.csv` CSV examples.
  - Swapped multi-recruiter examples to verified CRBN recruiter codes.
- `Qodex.summary.md`
  - Replaced with this task summary.

## Files Created
- `scripts/smoke_test_api_reference.py`
  - Stdlib-only smoke test for the documented JSON, CSV, ZIP, and SVG API Reference examples.
- `Qodex.summary.md`
  - Recreated for this task.

## Implementation Summary
- I first built an endpoint inventory from `templates/api-reference.html`.
- Documented command groups found:
  - Setup and manifest:
    - `export BASE="https://e3ligandalyzer.com/api"`
    - manifest JSON examples
  - Download API:
    - manifest
    - filtered manifest
    - ligase index
    - recruiter-code discovery
    - ligase ZIP bundles
    - recruiter ZIP bundles
    - dataset-wide ZIP bundles
  - JSON API:
    - ligase list
    - featured recruiters
    - scaffold routes
    - descriptors
    - recruiter SMILES
    - ligand visual
    - SASA full
    - SVG render
    - ELiAH expression
  - CSV API:
    - table index
    - scaffold CSV
    - SASA summary CSV
    - SASA atoms CSV
    - descriptors CSV
    - recruiter scaffold CSV
  - Python snippets:
    - ligase ZIP download
    - recruiter ZIP download
    - featured recruiter pandas load
    - descriptors CSV load
  - Browser JS:
    - ligases fetch
    - featured recruiters fetch
- I then ran a live public smoke pass against `https://e3ligandalyzer.com/api` and found 7 broken areas before patching:
  - `/api/download/manifest` returned `ligase_count: 0` and `ligases: []`
  - `/api/download/ligases` returned `[]`
  - `/api/download/recruiter-codes?ligase=CRBN&limit=25` returned no working example codes because all `has_pdb` / `has_sdf` flags were false
  - `/api/download/recruiter/LR00001.zip` returned 404
  - `/api/download/recruiters.zip?codes=LR00001,LR00002,LR00003` returned 404
  - `/api/sasa-full/LR00001` returned 500 and exposed the Randy URL
  - `/api/render-smiles-by-code/LR00001` returned 500 because of an RDKit drawing option mismatch
- Root causes found:
  - Manifest, ligase index, and recruiter-code discovery were still using local-only asset discovery helpers in remote mode.
  - Recruiter bundle routes had no remote-mode implementation at all.
  - `/api/sasa-full/<code>` queried a non-existent `atom_index` column.
  - `/api/render-smiles-by-code/<code>` used `MolDrawOptions.atomPalette`, which is not available in this runtime.
  - App-level 404 handling returned HTML for bad API calls.
  - Randy client exceptions surfaced raw upstream request text.
- After patching, local smoke verification passed all documented examples.

## Key Decisions
- Verified example ligases and recruiter codes:
  - `CRBN` for ligase/download discovery
  - `LR00001` for descriptors, recruiter SMILES, ligand visual, SASA, and SVG
  - `LR00006,LR00007,LR00008` for verified CRBN multi-recruiter bundle examples
- Manifest ligase discovery:
  - local mode still uses real local asset directories
  - remote mode now builds ligase entries from the recruiter mapping table plus remote asset resolution instead of empty local-folder scans
- Recruiter-code discovery:
  - local mode uses exact local filenames
  - remote mode resolves downloadable assets through Randy-backed file checks so `has_pdb`, `has_sdf`, and `example_codes` are meaningful
- Recruiter ZIP bundles:
  - local mode still zips local files directly
  - remote mode now downloads the mapped Randy-backed files and assembles the ZIP in the public app
- SASA full payload:
  - now uses `atom_id` ordering and returns JSON-safe dict rows
  - unknown recruiter codes return a structured 404 JSON error
- SVG validation:
  - success requires SVG/XML-like output
  - failures return JSON errors instead of tiny text payloads
- Error sanitization:
  - API 404/411 now stay JSON
  - Randy client failures are sanitized before they reach public routes
- Endpoints removed or marked experimental:
  - none removed
  - all visible API Reference examples are kept, but the multi-recruiter examples were updated to verified CRBN codes

## Commands Run
- Inventory and route inspection:
  - `sed -n ... templates/api-reference.html`
  - `sed -n ... Ligases/routes.py`
  - `sed -n ... Ligases/randy_client.py`
  - `sed -n ... RANDY/e3_data_routes.py`
  - `rg -n ...`
- Live public API checks before patching:
  - `curl -sS "https://e3ligandalyzer.com/api/download/manifest" | python3 -m json.tool`
  - `curl -sS "https://e3ligandalyzer.com/api/download/recruiter-codes?ligase=CRBN&limit=25" | python3 -m json.tool`
  - `curl -sS "https://e3ligandalyzer.com/api/download/ligases" | python3 -m json.tool`
  - `curl -sS "https://e3ligandalyzer.com/api/descriptors/LR00001" | python3 -m json.tool`
  - `curl -sS "https://e3ligandalyzer.com/api/recruiter-smiles/LR00001" | python3 -m json.tool`
  - `curl -sS "https://e3ligandalyzer.com/api/ligand-visual/LR00001" | python3 -m json.tool`
  - `curl -sS "https://e3ligandalyzer.com/api/sasa-full/LR00001" | python3 -m json.tool`
  - `curl -sS "https://e3ligandalyzer.com/api/render-smiles-by-code/LR00001" | head -c 240`
  - ZIP spot checks with `curl -L` and `zipfile`
- Syntax validation:
  - `python3 -m py_compile Ligase_app.py Ligases/routes.py Ligases/randy_client.py scripts/smoke_test_api_reference.py`
- Local app validation:
  - `conda run -n viraldb python Ligase_app.py`
  - `python3 scripts/smoke_test_api_reference.py --base-url http://127.0.0.1:5025/api`
  - targeted invalid-call checks for unknown recruiter codes and ligases

## Validation Results
- Public pre-fix failure matrix:
  - Failed:
    - `GET /api/download/manifest`
    - `GET /api/download/ligases`
    - `GET /api/download/recruiter-codes?ligase=CRBN&limit=25`
    - `GET /api/download/recruiter/LR00001.zip`
    - `GET /api/download/recruiters.zip?codes=LR00001,LR00002,LR00003`
    - `GET /api/sasa-full/LR00001`
    - `GET /api/render-smiles-by-code/LR00001`
  - Passed:
    - the remaining documented JSON, CSV, and large ligase/all ZIP routes
- Local post-fix smoke result:
  - `python3 scripts/smoke_test_api_reference.py --base-url http://127.0.0.1:5025/api`
  - Result: all 31 checks passed
- Confirmed locally after patching:
  - `/api/download/manifest` returns valid JSON with `ligase_count: 21`
  - `/api/download/manifest` includes ligase entries such as `CRBN`
  - `/api/download/ligases` returns a populated ligase list with bundle URLs
  - `/api/download/recruiter-codes?ligase=CRBN&limit=25` returns working example codes including `LR00006`, `LR00007`, `LR00008`
  - `/api/sasa-full/LR00001` returns structured JSON with `ok`, `summary`, and `atoms`
  - `/api/render-smiles-by-code/LR00001` returns SVG/XML output
  - documented ZIP endpoints return valid non-empty ZIPs locally
  - documented CSV endpoints return parseable CSV locally
  - invalid API calls now return JSON errors locally
- No local API error now exposed:
  - `randy.rove-vernier.ts.net`
  - Heroku hostnames
  - Python stack traces
  - private filesystem paths

## Known Issues
- The remote Randy-backed branches were fixed in code, but the public production domain still needs a post-deploy smoke run to confirm the live site now matches the local passing state.
- The public pre-fix smoke script still fails against the currently deployed production instance until these code changes are deployed.
- Local ZIP counts include `manifest.json` because locally assembled ZIP responses now carry metadata; remote proxy ZIPs on the currently deployed public site may not yet include that file until deployment.
- This task intentionally did not change Release Notes statistics or release-page metric logic.

## Manual Verification
1. Visit `/api-reference`.
2. Copy the `export BASE="https://e3ligandalyzer.com/api"` command.
3. Run the manifest command.
4. Run recruiter-code discovery for CRBN.
5. Run descriptor, SMILES, ligand-visual, SASA, SVG, CSV, and ZIP examples.
6. Confirm each documented example works or has clearly documented behavior.
7. Confirm no command uses the Heroku hostname.
8. Confirm invalid examples return clean JSON errors without internal URLs.

## Suggested Next Prompt
Please add `scripts/smoke_test_api_reference.py` to deployment verification or CI so every documented API Reference command must pass before future API Reference or backend changes can ship.
