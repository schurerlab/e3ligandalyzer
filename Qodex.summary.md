# Qodex.summary

## Task
Debug Heroku remote-mode E3 ligand/recruiter resolution.

## Original Goal
Fix the Heroku-side bug where ligand pages load but the app still reaches `/missing-recruiter?code=...`, while preserving the working RANDY `backup_receiver.app:APP` backend contract.

## Assumptions
- The live RANDY backend contract is already correct and should not be changed from the Heroku repo.
- The current shell does not contain live production `E3_RANDY_BASE_URL` or `E3_RANDY_TOKEN`, so remote validation must be simulated safely unless those are already present.
- Local SQLite data in `Ligases/Ligase_Recruiter.db` is representative enough to validate recruiter mappings and payload shape.

## Files Inspected
- `Ligases/randy_client.py` — confirm remote-mode flagging, base URL normalization, token use, and proxy/query helpers.
- `Ligases/routes.py` — inspect `/api/ligand-visual`, recruiter lookup helpers, render/download routes, and any local filesystem assumptions.
- `Ligase_app.py` — inspect `/ligand/<code>`, `/missing-recruiter`, and `/Ligases/<path:filename>` proxy behavior.
- `templates/ligand.html` — inspect the client-side fetch chain that redirects to `/missing-recruiter`.
- `templates/missing_recruiter.html` — confirm fallback behavior.
- `requirements.txt` — confirm the earlier Heroku RDKit fix is still present.
- `.python-version` — confirm the Python version fix is still present.

## Files Changed
- `Ligases/routes.py` — replaced dyno-local PDB checks in recruiter-detail flow with backend-aware PDB resolution, added safer JSON error responses for `/api/ligand-visual`, and updated random recruiter validation to use the active backend.
- `templates/ligand.html` — tightened client-side handling for `/api/ligand-visual` 404/411/non-OK responses so the missing-recruiter fallback is only used intentionally.
- `Qodex.summary.md` — updated for this debugging run.

## Files Created
- `Qodex.summary.md` — concise record of findings, changes, validation, and manual verification.

## Implementation Summary
Root cause: the Heroku-side `/api/ligand-visual/<recruiter_code>` route was still treating dyno-local files under `Ligases/<Ligase>/PDB/...` as the source of truth. In remote mode, that route used remote RANDY SQL for descriptors and SASA data, but it still ran `os.path.exists(...)` against the Heroku filesystem to decide whether the recruiter had a valid PDB. On Heroku, those files are not present locally because they live on RANDY, so valid recruiters such as `LR00125` and `LR00452` were incorrectly classified as missing and the frontend redirected to `/missing-recruiter`.

The fix was to make recruiter-detail PDB validation backend-aware. `Ligases/routes.py` now resolves the effective PDB filename from the active backend:
- in local mode, from local `Ligases/<ligase>/PDB/` files with variant-aware matching;
- in remote mode, from RANDY’s `/backup/e3/ligase-pdbs/<ligase>` listing via the existing `randy_client` abstraction.

`/api/ligand-visual/<recruiter_code>` now returns structured JSON for success, missing-data (`411`), and fatal failures (`500`) instead of rendering HTML templates from an API route. The ligand page JS was updated to treat `404` and `411` as intentional missing-recruiter cases and to stop assuming every non-network response is valid JSON payload data.

I also updated `/api/random-recruiter` so its “safe recruiter” filter no longer depends on local PDB files in remote mode.

## Key Decisions
- Kept the fix on the Heroku side only, because the RANDY `backup_receiver.app:APP` contract was already validated and did not need changes.
- Patched the narrowest failing layer: recruiter-detail PDB validation inside `/api/ligand-visual`, instead of rewriting route architecture or frontend routing.
- Returned JSON from `/api/ligand-visual` for API failures, because the client-side page code fetches that endpoint and should not receive rendered HTML templates.
- Left `requirements.txt` and `.python-version` untouched after confirming they already contain the expected Heroku build fixes (`rdkit` and `3.13`).

## Commands Run
- `rg -n "missing-recruiter|missing_recruiter|ligand/|/ligand|LR00125|LR00452|E3_DATA_BACKEND|E3_RANDY_BASE_URL|E3_RANDY_TOKEN|randy_client|sqlite|Ligase_Recruiter|Recruiter|Ligand|render-sdf|render-pdb|download/table|download/ligase|ligase-pdbs" .` — find request/data flow and stale assumptions.
- `sed -n '1,260p' Ligases/randy_client.py` — inspect remote client behavior.
- `sed -n '1,360p' Ligases/routes.py` — inspect core route helpers.
- `sed -n '1,260p' Ligase_app.py` — inspect page and file proxy routes.
- `sed -n '1,320p' templates/ligand.html` — inspect client-side recruiter-detail flow.
- `python - <<'PY' ... sqlite lookup for LR00125/LR00452 ... PY` — confirm both recruiters exist in the mapping table.
- `python - <<'PY' ... local file existence checks for LR00125/LR00452 ... PY` — confirm variant patterns and local asset shape.
- `python -m py_compile Ligase_app.py Ligases/randy_client.py Ligases/routes.py` — syntax validation.
- `python - <<'PY' ... Flask test client with monkeypatched remote RANDY helpers ... PY` — simulate remote mode safely without secrets and validate recruiter-detail/data/download routes.
- `rg -n "rdkit|rdkit-pypi" requirements.txt` — confirm Heroku dependency fix is present.
- `cat .python-version` — confirm Python version fix is present.

## Validation Results
- `python -m py_compile Ligase_app.py Ligases/randy_client.py Ligases/routes.py` passed.
- Local SQLite inspection confirmed:
  - `LR00125` maps to `DCAF1 / 8OG7 / VMR / Variant 1`
  - `LR00452` maps to `TRIM21 / 7HN8 / A23 / Variant 2`
- Remote-mode simulation with monkeypatched `randy_client` calls passed for:
  - `/api/ligases` → `200`
  - `/api/ligase-pdbs/CRBN` → `200`
  - `/ligand/LR00125` → `200`
  - `/missing-recruiter?code=LR00125` → `200`
  - `/api/Ligases/CRBN/PDB/4CI1_EF2.pdb` → `200`, `chemical/x-pdb`
  - `/api/render-sdf/CRBN/4CI1_EF2.pdb` → `200`, `chemical/x-mdl-sdfile`
  - `/api/download/table/Ligase_Scaffold_Data.csv` → `200`, `text/csv`
  - `/api/download/ligase/CRBN/pdbs.zip` → `200`, `application/zip`
  - `/api/ligand-visual/LR00125` → `200`, JSON `ok: true`
  - `/api/ligand-visual/LR00452` → `200`, JSON `ok: true`
- Live remote validation against the real RANDY host was not run from this shell because `E3_RANDY_BASE_URL` and `E3_RANDY_TOKEN` are not set here.

## Known Issues
- This run did not exercise the real production RANDY host directly, so final confirmation on Heroku should still be done with the real remote env vars in place.
- `templates/ligand.html` still contains an embedded `/missing-recruiter` string in its JS logic because the fallback remains part of the intended UX; seeing that string in raw HTML is not itself evidence of a bad redirect.
- `Ligases/routes.py` still contains legacy debug `print(...)` statements in several detail routes. They are functional but noisy.

## Manual Verification
1. On Heroku or in a shell with the real env vars set, confirm:
   `python - <<'PY'`
   `import os`
   `print("E3_DATA_BACKEND:", os.getenv("E3_DATA_BACKEND"))`
   `print("E3_RANDY_BASE_URL set:", bool(os.getenv("E3_RANDY_BASE_URL")))`
   `print("E3_RANDY_TOKEN set:", bool(os.getenv("E3_RANDY_TOKEN")))`
   `PY`
   Expected: `E3_DATA_BACKEND` is `remote`, and the base URL/token booleans are `True`.
2. Check recruiter-detail API behavior:
   `python - <<'PY'`
   `import Ligase_app`
   `app = Ligase_app.create_app()`
   `c = app.test_client()`
   `for path in ["/api/ligand-visual/LR00125", "/api/ligand-visual/LR00452"]:` 
   `    r = c.get(path)`
   `    print(path, r.status_code, r.is_json, (r.get_json() or {}).get("ok"))`
   `PY`
   Expected: both return `200`, JSON, `ok=True`.
3. In the browser on Heroku, open:
   - `/ligand/LR00125`
   - `/ligand/LR00452`
   Expected: the page stays on the ligand detail page and does not redirect to `/missing-recruiter`.
4. Verify proxy/download endpoints in remote mode:
   - `/api/ligase-pdbs/CRBN`
   - `/api/Ligases/CRBN/PDB/4CI1_EF2.pdb`
   - `/api/render-sdf/CRBN/4CI1_EF2.pdb`
   - `/api/download/table/Ligase_Scaffold_Data.csv`
   - `/api/download/ligase/CRBN/pdbs.zip`
   Expected: `200` responses with the expected content types.

## Suggested Next Prompt
Please add a small committed regression test that exercises `/api/ligand-visual/<recruiter_code>` in both local and mocked-remote mode so future refactors cannot reintroduce dyno-local file checks into remote recruiter resolution.
