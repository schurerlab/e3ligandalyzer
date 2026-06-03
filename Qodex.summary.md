# Qodex.summary

## Task
Persist shipped recruiter count across app restarts.

## Original Goal
Make the number of recruiters shipped to PROTAC Builder survive Flask/Heroku app resets and investigate adding a RANDY backup so the count is durable across runs.

## Assumptions
- “Shipped to PROTAC Builder” should count successful PROTAC Builder session creation, not pre-conversion attempts.
- `session_id` is the best available idempotency key for avoiding duplicate shipment events.
- The existing RANDY E3 service contract remains rooted at `backup_receiver.app:APP` under `/backup/e3`, and the repo’s `RANDY/` copy is the correct place to stage backend changes.
- Heroku may not provide a persistent filesystem, so local SQLite is appropriate for local/dev or mounted-volume deployments, while Postgres or RANDY should be used for durable production persistence.

## Files Inspected
- `Ligases/routes.py` — traced the shipment logging path, `/api/shipped-count`, and `convert_atom_to_v()`.
- `Ligases/randy_client.py` — inspected the existing authenticated RANDY E3 client conventions.
- `Ligase_app.py` — confirmed blueprint registration and API wiring.
- `templates/about.html` — confirmed the shipped-count UI only reads `total`.
- `templates/explorer.html` — confirmed the “Use as Ligase Recruiter” flow posts to `/api/convert_atom_to_v`.
- `templates/ligand.html` — confirmed the ligand page uses the same conversion route and builder session flow.
- `RANDY/app.py` — confirmed the shared RANDY Flask app already registers the E3 routes.
- `RANDY/e3_data_routes.py` — inspected the existing `/backup/e3/*` namespace and auth pattern before adding shipment endpoints.
- `README.md` — updated deployment notes.
- `requirements.txt` — checked available dependencies and added Postgres driver support.

## Files Changed
- `Ligases/routes.py` — moved shipment counting to the successful session path, stopped logging raw request payloads, made analytics logging non-fatal, and switched `/api/shipped-count` to the new storage abstraction.
- `Ligases/randy_client.py` — added shipment-specific RANDY helper methods and shipment backup config fallbacks.
- `RANDY/e3_data_routes.py` — added authenticated shipment write/count endpoints backed by durable SQLite.
- `requirements.txt` — added `psycopg2-binary` for Postgres-backed shipment storage.
- `README.md` — added shipment persistence and deployment configuration notes.
- `Qodex.summary.md` — replaced with this task summary.

## Files Created
- `Ligases/shipment_store.py` — new persistent shipment storage abstraction supporting `auto`, `sqlite`, `postgres`, `randy`, and `csv-fallback`.
- `.env.example` — example shipment persistence and RANDY environment settings.

## Implementation Summary
The reset bug came from using `Ligases/Ligases_Shipped_To_Builder.csv` as the only source of truth for `/api/shipped-count`. On Heroku, that file lives on the dyno filesystem, so writes disappear on restart, dyno replacement, and redeploy.

The app now records shipment events through `Ligases/shipment_store.py`. The storage layer chooses a single source of truth based on `E3_SHIPMENT_STORAGE`:
- `postgres` when `DATABASE_URL` is present and supported,
- `randy` when RANDY shipment storage is configured,
- `sqlite` for local/dev or mounted persistent volumes,
- `csv-fallback` only as a compatibility fallback.

`convert_atom_to_v()` now records the shipment after a `session_id` has been created and the output SDF has been written, so the count represents successful PROTAC Builder sessions instead of earlier attempts. Duplicate writes are suppressed via `session_id` uniqueness.

RANDY now exposes:
- `POST /backup/e3/shipments`
- `GET /backup/e3/shipments/count`

Those endpoints use the existing bearer-token pattern and store shipment events in a dedicated SQLite database at `E3_SHIPMENT_DB_PATH`, defaulting on RANDY to `/home/jxs794/PROTAC_BUILDER/data/e3_shipments.db`.

## Key Decisions
- Chose successful PROTAC Builder sessions as the metric semantics because the prior implementation logged before session creation and therefore overstated true successful handoffs.
- Used a single primary source of truth for the count rather than summing local and RANDY stores, which avoids double counting.
- Kept RANDY backup non-blocking so conversion still succeeds if backup storage is temporarily unavailable.
- Preserved frontend compatibility by continuing to return `{"total": N}` while adding `ok`, `source`, and `backup_ok`.
- Removed raw request payload logging from `convert_atom_to_v()` so SDF payloads are not printed to logs.

## Commands Run
- `rg -n "Ligases_Shipped_To_Builder|shipped-count|log_ligase_shipment|convert_atom_to_v|ship|shipment|PROTACSUITE|upload-ligand|builder\\?session|DATABASE_URL|sqlite|backup_receiver|E3_RANDY|RANDY" .` — locate all shipment, builder, DB, and RANDY references.
- `sed -n '1,260p' Ligases/routes.py` — inspect the main API file.
- `sed -n '1,260p' Ligases/randy_client.py` — inspect RANDY client helpers.
- `sed -n '1,260p' Ligase_app.py` — inspect Flask app wiring.
- `sed -n '2240,2475p' Ligases/routes.py` — inspect the exact shipment logging and conversion path.
- `sed -n '1,360p' RANDY/e3_data_routes.py` — inspect RANDY E3 routes and auth.
- `sed -n '900,970p' templates/about.html` — inspect shipped-count frontend handling.
- `sed -n '1500,1625p' templates/explorer.html` — inspect explorer conversion caller.
- `sed -n '1780,1955p' templates/ligand.html` — inspect ligand conversion caller.
- `python -m py_compile Ligase_app.py Ligases/routes.py Ligases/randy_client.py Ligases/shipment_store.py` — verify E3 app syntax.
- `python -m py_compile RANDY/app.py RANDY/e3_data_routes.py` — verify RANDY-side syntax.
- `python - <<'PY' ... shipment_store ... PY` — verify SQLite count persistence and duplicate suppression directly through the new storage layer.
- `python - <<'PY' ... create_app() test_client ... PY` — verify `/api/shipped-count` returns stable JSON from the new store.
- `python - <<'PY' ... convert_atom_to_v ... PY` — verify a real conversion request still succeeds and increments the shipment count after session creation.
- `python - <<'PY' ... RANDY/e3_data_routes.py ... PY` — verify RANDY shipment auth, write, duplicate suppression, and count behavior.

## Validation Results
- Syntax validation passed for:
  - `Ligase_app.py`
  - `Ligases/routes.py`
  - `Ligases/randy_client.py`
  - `Ligases/shipment_store.py`
  - `RANDY/app.py`
  - `RANDY/e3_data_routes.py`
- SQLite persistence validation passed:
  - initial count was `0`
  - after recording `session-1`, count became `1`
  - replaying `session-1` did not increment the count
- Flask route validation passed:
  - `/api/shipped-count` returned `200`
  - response shape included `total`, `ok`, `source`, and `backup_ok`
  - count remained readable after app recreation with the same DB path
- Conversion-path validation passed:
  - `/api/convert_atom_to_v` returned `200`
  - a real `session_id` was generated
  - `/api/shipped-count` incremented to `1` only after successful session creation
- RANDY endpoint validation passed:
  - unauthorized `POST /backup/e3/shipments` returned `401`
  - authorized POST stored the first event
  - replaying the same `session_id` was treated as a duplicate
  - `GET /backup/e3/shipments/count` returned `200` with `total: 1`
- Live Heroku and live RANDY network validation was not run because no real production credentials or remote deployment access were available in this workspace.

## Known Issues
- `E3_SHIPMENT_STORAGE=sqlite` is only durable when `E3_SHIPMENT_DB_PATH` points to persistent storage; on plain Heroku dynos without a mounted volume, SQLite remains ephemeral.
- Postgres mode now has code support and dependency support, but a real Postgres connection was not exercised locally because no live `DATABASE_URL` was available.
- The legacy `Ligases/converted-ligases-by-user.csv` analytics file is still written when possible, but it is now explicitly non-critical and not used as the shipped-count source of truth.

## Manual Verification
1. Check `/api/shipped-count` before shipping a recruiter.
2. Ship a recruiter to PROTAC Builder.
3. Check `/api/shipped-count` again and confirm it increments.
4. Restart/redeploy the app.
5. Check `/api/shipped-count` again and confirm it did not reset.
6. If RANDY backup is enabled, verify the RANDY count endpoint or storage file/database also has the event.

## Suggested Next Prompt
Please add a small admin/debug route or CLI script that reports the active shipment storage mode and validates the configured store connectivity without exposing secrets.
