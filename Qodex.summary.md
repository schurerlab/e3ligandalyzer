# Qodex.summary

## Task
Integrate E3 Ligandalyzer RANDY-side routes into the shared RANDY Flask app.

## Original Goal
Refactor the RANDY-side E3 integration so the E3 data service runs inside the copied shared RANDY Flask app at `RANDY/app.py`, with E3 endpoints under `/backup/e3`, instead of relying on a second standalone Flask server from `RANDY_E3_DATA_SERVER.py`.

## Assumptions
- The copied `RANDY/app.py` is the safe validation target and its final changes will be manually copied back to the real RANDY deployment.
- Existing frontend and Heroku-side E3 routes should keep their current URL shapes and remote-mode behavior.
- `Ligase_Table/*.csv` is the intended source for RANDY-side table CSV downloads in remote mode.
- The local workspace may or may not contain the real SQLite databases and full ligase asset tree during validation.

## Files Inspected
- `RANDY/app.py`
- `RANDY_E3_DATA_SERVER.py`
- `Ligases/randy_client.py`
- `Ligases/routes.py`
- `Ligase_app.py`
- `E3_RANDY_HEROKU_DATABASE_GUIDE.md`

## Files Changed
- `RANDY/app.py`
- `RANDY/e3_data_routes.py`
- `RANDY_E3_DATA_SERVER.py`
- `Ligases/routes.py`
- `E3_RANDY_HEROKU_DATABASE_GUIDE.md`
- `Qodex.summary.md`

## Files Created
- `RANDY/e3_data_routes.py`
- `Qodex.summary.md`

## Implementation Summary
E3 RANDY routes were moved into a new helper module, `RANDY/e3_data_routes.py`, and that helper is now registered on the existing RANDY `APP` in `RANDY/app.py`. The shared RANDY app now exposes authenticated E3 endpoints under `/backup/e3` for health checks, read-only SQLite queries, ligase PDB listing, PDB/SDF file serving, ligase/all ZIP downloads, and CSV table downloads.

The new E3 helper keeps authentication scoped to E3 routes only through a blueprint-specific `before_request` check. It also uses environment-driven paths with repo-local defaults, validates read-only SQL, blocks destructive SQL keywords, enforces path-safety checks, preserves PDB/SDF variant resolution, and limits downloads to expected asset types and CSV files under allowed roots.

Heroku-side compatibility was preserved. The existing `Ligases/randy_client.py` behavior was left intact, and `Ligases/routes.py` was patched narrowly so ELiAH schema introspection uses `SELECT ... FROM pragma_table_info(...)` instead of `PRAGMA table_info(...)`, keeping remote mode compatible with the new read-only SQL restrictions.

## Key Decisions
- Used a helper module plus blueprint registration rather than expanding `RANDY/app.py` directly, to keep the shared RANDY app maintainable and minimize risk to unrelated RANDY routes.
- Scoped auth to `/backup/e3` only, rather than adding a global RANDY auth hook.
- Kept `RANDY_E3_DATA_SERVER.py` as a deprecated reference file instead of deleting it, because it still documents the earlier standalone implementation.
- Served `/backup/e3/download/table/<table>.csv` from `E3_TABLE_ROOT` CSV files, matching the requested production architecture and keeping RANDY-side table downloads file-based.
- Preserved alias asset types such as `pdbs`, `sdfs`, `all`, and `structures` for compatibility with existing Heroku-side download routes, while also supporting the minimum requested `pdb` and `sdf`.

## Commands Run
- `sed -n '1,260p' RANDY/app.py`
- `sed -n '1,320p' RANDY_E3_DATA_SERVER.py`
- `sed -n '1,260p' Ligases/randy_client.py`
- `sed -n '1,320p' Ligases/routes.py`
- `sed -n '1,260p' Ligase_app.py`
- `sed -n '1,260p' E3_RANDY_HEROKU_DATABASE_GUIDE.md`
- `rg -n "..." Ligases/routes.py Ligase_app.py`
- `ls -la RANDY`
- `python -m py_compile Ligases/randy_client.py Ligases/routes.py Ligase_app.py RANDY/app.py RANDY/e3_data_routes.py`
- `python - <<'PY' ... import RANDY.app ... PY`
- `python - <<'PY' ... Flask test client checks ... PY`

## Validation Results
- Syntax compilation passed for `Ligases/randy_client.py`, `Ligases/routes.py`, `Ligase_app.py`, `RANDY/app.py`, and `RANDY/e3_data_routes.py`.
- Import validation passed for `import RANDY.app`.
- Shared RANDY Flask test-client checks passed for:
  - `/backup/e3/healthz` without auth returning `401`
  - `/backup/e3/healthz` with auth returning `200`
  - `/backup/e3/query` with auth and `SELECT 1 AS ok` returning `200` and a `rows` array
  - existing RANDY `/healthz` still returning `200`
- Manual asset-file endpoint checks were not completed against real ligase files because that depends on local data presence and known filenames.

## Known Issues
- The new RANDY-side `/backup/e3/download/table/<table>.csv` endpoint now serves CSV files from `E3_TABLE_ROOT`, while the Heroku local-mode implementation still generates CSV exports from SQLite. That is intentional for the requested RANDY architecture but should be verified against the actual CSV inventory on RANDY.
- Full live validation of PDB/SDF/ZIP downloads depends on the real ligase asset tree and known test filenames being present.
- Remote-mode ELiAH schema discovery now depends on SQLite supporting `pragma_table_info(...)` as a table-valued function, which is standard on modern SQLite builds but should still be verified on the target RANDY runtime.

## Manual Verification
1. In this repo, set a temporary token:
   `export E3_RANDY_TOKEN="test-token"`
2. Run a quick shared-RANDY import/test locally:
   `python - <<'PY'`
   `from RANDY.app import APP`
   `client = APP.test_client()`
   `print(client.get("/backup/e3/healthz").status_code)`
   `print(client.get("/backup/e3/healthz", headers={"Authorization": "Bearer test-token"}).status_code)`
   `print(client.post("/backup/e3/query", json={"database": "main", "sql": "SELECT 1 AS ok", "params": [], "one": False}, headers={"Authorization": "Bearer test-token"}).get_json())`
   `PY`
3. If local data files exist, check:
   `GET /backup/e3/ligase-pdbs/VHL`
   `GET /backup/e3/file/pdb/VHL/<known-file>.pdb`
   `GET /backup/e3/file/sdf/VHL/<known-file>.sdf`
   `GET /backup/e3/download/table/<known-table>.csv`
4. Confirm existing RANDY routes still behave normally, especially `/healthz` and the established `/backup/*` routes unrelated to E3.
5. After manually copying the validated RANDY changes back to the real RANDY deployment, set:
   `E3_RANDY_TOKEN`, `E3_DATA_DIR`, `E3_DB_PATH`, `E3_ELIAH_DB_PATH`, `E3_ASSET_ROOT`, and `E3_TABLE_ROOT`
6. On Heroku, set:
   `E3_DATA_BACKEND=remote`
   `E3_RANDY_BASE_URL=https://<randy-host>/backup/e3`
   `E3_RANDY_TOKEN=<same-token>`
7. Verify Heroku-side remote mode by calling:
   `/api/ligases`
   `/api/ligase-pdbs/VHL`
   `/api/render-sdf/VHL/<known-file>.sdf`
   `/api/download/ligase/VHL/pdbs.zip`

## Suggested Next Prompt
Please add a small local regression test script that exercises the new RANDY `/backup/e3` routes against real sample ligase files if they exist, and report any remaining remote-mode mismatches between `Ligases/routes.py` and the RANDY helper.
