# Qodex.summary

## Task
Fix Canonical Public API Domain

## Original Goal
Ensure all public E3 Ligase Ligandalyzer API paths, examples, manifest links, and generated download URLs use `https://e3ligandalyzer.com` / `https://e3ligandalyzer.com/api` instead of the Heroku app hostname.

## Assumptions
- The canonical public application domain is `https://e3ligandalyzer.com`.
- The canonical public API base is `https://e3ligandalyzer.com/api`.
- Deployment may still run behind Randy/Heroku internally, so public docs and generated URLs should not rely on request hostnames.
- `PUBLIC_SITE_URL` can safely be used as an override when needed, but should default to `https://e3ligandalyzer.com`.
- The raw `/api/download/manifest` endpoint must remain machine-readable JSON with the same overall structure.
- This task should not alter release-stat logic, V1 release wording, or database-count behavior.

## Files Inspected
- `Ligase_app.py` — inspected app config/context injection and looked for an existing public URL helper pattern.
- `Ligases/routes.py` — inspected `/api/download/manifest` support code and absolute URL generation for manifest/download links.
- `templates/api-reference.html` — inspected how `api_base` was constructed and where public copy-paste examples were rendered.
- `templates/download_manifest.html` — inspected visible manifest metadata, raw JSON links, and download buttons.
- `E3_RANDY_HEROKU_DATABASE_GUIDE.md` — checked remaining Heroku references to confirm they are private maintainer/deployment documentation rather than public app output.
- `Qodex.summary.md` — replaced with this task summary.

## Files Changed
- `Ligase_app.py` — added canonical `PUBLIC_SITE_URL` / `PUBLIC_API_BASE` helpers and injected them into template context.
- `Ligases/routes.py` — added canonical public URL helpers and updated manifest absolute-URL generation to use the public API base instead of `request.host_url`.
- `templates/api-reference.html` — switched all visible examples and “Open” links to the injected canonical `PUBLIC_API_BASE`.
- `templates/download_manifest.html` — updated visible raw-manifest links and endpoint text to use the canonical API base.
- `Qodex.summary.md` — replaced with this task summary.

## Files Created
- No new project code files were created in this task.
- `Qodex.summary.md` was recreated for this task summary.

## Implementation Summary
- A single canonical public URL source now defines the public site root and API base:
  - `https://e3ligandalyzer.com`
  - `https://e3ligandalyzer.com/api`
- The API Reference page no longer derives its base URL from `request.host_url`; it now uses the canonical public API base for Bash, Python, browser-JS, CSV, ZIP, and raw-manifest examples.
- The raw download manifest generator no longer emits absolute URLs based on the active request host. It now generates public-facing URLs using the canonical public API base for:
  - `base_url`
  - dataset-wide ZIP downloads
  - table download URLs
  - per-ligase bundle URLs
  - other manifest-generated download links
- The human-readable Download Manifest page now displays and links to the canonical public API domain as well.
- Raw API behavior was preserved: `/api/download/manifest` still returns raw JSON and remains suitable for `curl`, Python, and workflow automation.

## Key Decisions
- Canonical public site URL:
  - `https://e3ligandalyzer.com`
- Canonical public API base:
  - `https://e3ligandalyzer.com/api`
- `PUBLIC_SITE_URL` support:
  - added as an environment-driven helper with default `https://e3ligandalyzer.com`
  - `PUBLIC_API_BASE` is derived from it
- Manifest generation:
  - updated `_api_url(...)` in `Ligases/routes.py` to use the canonical public API base instead of `request.host_url`
- API examples:
  - kept absolute because they are meant to be copied into terminals and scripts
- Remaining Heroku references:
  - only remain in `E3_RANDY_HEROKU_DATABASE_GUIDE.md`
  - they are maintainer/deployment documentation, not public templates or generated app output

## Commands Run
- `sed -n '1,220p' Ligase_app.py` — inspected app config and context setup.
- `sed -n '2960,3095p' Ligases/routes.py` — inspected manifest URL helper logic.
- `sed -n '1,260p' templates/api-reference.html` — inspected API base generation and examples.
- `sed -n '1,260p' templates/download_manifest.html` — inspected manifest-page links and metadata.
- `rg -n "request\\.host_url|request\\.url_root|request\\.host|_external=True|herokuapp\\.com|e3ligandalyzer-adb8adfde220|api_base|base_url|PUBLIC_SITE_URL|https://e3ligandalyzer\\.com" -g '!node_modules/**' .` — found request-host and hostname exposure points.
- `python3 -m py_compile Ligase_app.py Ligases/routes.py` — syntax validation.
- `rg -n "e3ligandalyzer-adb8adfde220|herokuapp\\.com" .` — checked for remaining Heroku references.
- `conda run -n viraldb python Ligase_app.py` — started the local app for route and content validation.
- `curl -s http://127.0.0.1:5025/api-reference | grep -i "https://e3ligandalyzer.com/api"` — confirmed canonical API base appears in API Reference.
- `curl -s http://127.0.0.1:5025/api-reference | grep -i "herokuapp"` — confirmed public API Reference output does not expose Heroku.
- `curl -s http://127.0.0.1:5025/api/download/manifest | python3 -m json.tool >/dev/null` — confirmed raw manifest remains valid JSON.
- `curl -s http://127.0.0.1:5025/api/download/manifest | grep -i "https://e3ligandalyzer.com"` — confirmed canonical domain appears in raw generated URLs.
- `curl -s http://127.0.0.1:5025/api/download/manifest | grep -i "herokuapp"` — confirmed raw manifest output does not expose Heroku.
- `curl -s http://127.0.0.1:5025/download-manifest | grep -i "https://e3ligandalyzer.com/api"` — confirmed human-readable manifest shows canonical API base.
- `curl -s http://127.0.0.1:5025/download-manifest | grep -i "herokuapp"` — confirmed human-readable manifest does not expose Heroku.
- `for route in /api-reference /download-manifest /api/download/manifest /docs /methods /schema /release /explorer /scaffolds; do ...; done` — route smoke tests.

## Validation Results
- Syntax validation:
  - `Ligase_app.py` compiled successfully
  - `Ligases/routes.py` compiled successfully
- `/api-reference`:
  - renders `https://e3ligandalyzer.com/api`
  - does not expose `herokuapp`
- `/download-manifest`:
  - renders `https://e3ligandalyzer.com/api`
  - download buttons and raw-manifest links point at the canonical public API base
  - does not expose `herokuapp`
- `/api/download/manifest`:
  - still returns valid raw JSON
  - generated URLs now use `https://e3ligandalyzer.com`
  - does not expose `herokuapp`
- Public-hostname exposure search:
  - no Heroku matches remain in public templates or generated public output
  - remaining matches are private deployment-guide examples only
- Route smoke tests:
  - `/api-reference` → `200`
  - `/download-manifest` → `200`
  - `/api/download/manifest` → `200`
  - `/docs` → `200`
  - `/methods` → `200`
  - `/schema` → `200`
  - `/release` → `200`
  - `/explorer` → `200`
  - `/scaffolds` → `200`

## Known Issues
- The app should still be smoke-checked after deployment through the real public domain to confirm the environment override behavior is correct in production.
- Heroku-hostname examples remain in `E3_RANDY_HEROKU_DATABASE_GUIDE.md` because that file is maintainer-facing deployment documentation rather than a public app page or generated API output.
- This task intentionally did not change release-stat logic or release-page metric behavior.

## Manual Verification
1. Visit `/api-reference`.
2. Confirm the Base URL says `https://e3ligandalyzer.com/api`.
3. Confirm Bash, Python, CSV, and browser JS examples use `https://e3ligandalyzer.com/api`.
4. Visit `/download-manifest`.
5. Confirm the Base URL and download buttons use `https://e3ligandalyzer.com/api`.
6. Visit `/api/download/manifest`.
7. Confirm raw JSON still works and generated URLs use `https://e3ligandalyzer.com`.
8. Confirm no public page displays `herokuapp.com`.

## Suggested Next Prompt
Please add a small `/api/release` endpoint and a frozen machine-readable V1 release metadata file so future yearly releases can expose stable historical release records alongside the canonical public API domain.
