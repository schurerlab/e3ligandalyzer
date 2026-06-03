# Qodex.summary

## Task
Speed up ligand detail initial loading.

## Original Goal
Reduce ligand page load time by removing duplicate `/api/ligand-visual` calls, avoiding unnecessary SMILES refetches, reusing SASA data from the main payload, and using backend-resolved PDB filenames instead of client-side probing.

## Assumptions
- `/api/ligand-visual/<code>` is the intended bootstrap payload for the ligand detail page and is safe to treat as the primary source of truth during initial render.
- `metadata.SMILES` in the ligand-visual payload is canonical enough for initial 2D render, external links, and properties in the common case.
- Client-side PDB variant probing should remain available only as a fallback in case `pdb_file` or `pdb_path` is missing from the bootstrap payload.
- Missing recruiter and incomplete-data behavior should continue redirecting to `/missing-recruiter?code=<code>` when the backend returns `404` or `411`.

## Files Inspected
- `templates/ligand.html` — traced the startup fetch sequence, SASA summary loading, SMILES resolution, 3D load path, download globals, and PROTAC popup dependencies.
- `Ligases/routes.py` — inspected `get_ligand_visual()`, `fixed-2d-smiles`, and related ligand routes to confirm payload shape and duplicate backend lookups.
- `Ligase_app.py` — confirmed `/ligand/<code>` page routing remained unchanged.
- `Qodex.summary.md` — replaced with this task summary.

## Files Changed
- `templates/ligand.html` — consolidated startup onto one bootstrap fetch, made SASA summary reuse the bootstrap payload, made fixed-SMILES fetch fallback-only, and used backend-resolved PDB filenames/paths for initial 3D load.
- `Ligases/routes.py` — removed repeated composite-key lookups inside `get_ligand_visual()` while preserving the route’s response shape and missing-data behavior.
- `Qodex.summary.md` — updated for this ligand-load performance pass.

## Files Created
- `Qodex.summary.md` — rewritten to capture this task’s implementation and validation details.

## Implementation Summary
The ligand detail page was making three initial calls to `/api/ligand-visual/<code>`:
- an early availability check,
- the real bootstrap fetch,
- and another fetch inside `loadSASASummary()`.

It was also making an extra `/api/fixed-2d-smiles/<code>` request during normal startup even when the main ligand payload already contained a usable canonical SMILES, and the 3D viewer was probing many possible PDB filenames with `HEAD` requests even when the backend had already resolved the correct file.

The page now uses a single bootstrap loader:
- `loadLigandBootstrap(recruiterCode)` fetches `/api/ligand-visual/<code>` once,
- stores the result in `window.ligandVisualData`,
- handles `404` and `411` redirects directly,
- and drives the rest of the initial render from that payload.

SASA summary rendering now reads from the bootstrap payload instead of refetching the same route. SMILES resolution now uses the payload first and only calls `/api/fixed-2d-smiles/<code>` when the bootstrap payload lacks a usable SMILES. Initial 3D loading now prefers `pdb_path` / `pdb_file` from the bootstrap payload and only falls back to variant probing if those fields are missing.

On the backend, `get_ligand_visual()` no longer re-queries the composite key multiple times during the same request. It now resolves the composite key once, reuses it for metadata, summary, atom data, and PDB resolution, and keeps the same JSON contract.

## Key Decisions
- Removed the early “availability check” fetch and let the real bootstrap request handle both existence and rendering decisions.
- Kept `/api/fixed-2d-smiles/<code>` as a fallback instead of deleting it entirely, so partial payloads still have a safe recovery path.
- Kept `getProteinPdbPath()` and `HEAD` probing as fallback-only behavior for resilience, but stopped using it by default when `pdb_file`/`pdb_path` is already available.
- Stored the full bootstrap payload in `window.ligandVisualData` so existing helpers can reuse it without a broad frontend rewrite.
- Refactored `get_ligand_visual()` narrowly instead of changing its response shape, to avoid risking regressions in remote-mode or other callers.

## Commands Run
- `rg -n "ligand-visual|fixed-2d-smiles|loadSASASummary|getProteinPdbPath|render3D|render-smiles|render-2d-sasa|currentPDB|currentLigase|missing-recruiter|api/scaffold|fetch\\(|\\.head|HEAD|$.ajax|$.get" templates/ligand.html Ligases/routes.py Ligase_app.py Ligases` — locate all startup requests and related helpers.
- `rg -n "ligand-visual|fixed-2d-smiles|loadSASASummary|getProteinPdbPath|render3D|DOMContentLoaded|currentPDB|currentLigase|missing-recruiter" templates/ligand.html` — inspect the ligand page startup flow.
- `rg -n "def get_ligand_visual|ligand-visual|fixed-2d-smiles|render-sdf|recruiter-smiles" Ligases/routes.py` — inspect the relevant backend routes.
- `sed -n '540,740p' templates/ligand.html` — inspect the initial page bootstrap logic.
- `sed -n '1010,1385p' templates/ligand.html` — inspect SASA summary and 3D path resolution.
- `sed -n '923,1200p' Ligases/routes.py` — inspect and refactor `get_ligand_visual()`.
- `python -m py_compile Ligase_app.py Ligases/routes.py Ligases/randy_client.py` — verify Python syntax.
- `python - <<'PY' ... test_client ... PY` — verify `/ligand/LR00471` and `/api/ligand-visual/LR00471` still serve correctly.

## Validation Results
- Syntax validation passed for:
  - `Ligase_app.py`
  - `Ligases/routes.py`
  - `Ligases/randy_client.py`
- Local Flask test-client validation passed:
  - `/ligand/LR00471` returned `200` with `text/html`
  - `/api/ligand-visual/LR00471` returned `200` with `application/json`
- Code-path validation from inspection confirms:
  - initial ligand load now fetches `/api/ligand-visual/<code>` once
  - `loadSASASummary()` no longer fetches `/api/ligand-visual/<code>`
  - `/api/fixed-2d-smiles/<code>` is now fallback-only
  - initial 3D load now prefers `pdb_path` / `pdb_file` from the bootstrap payload before using `HEAD` probing
- Manual browser Network-tab verification was not run in this workspace because no interactive browser session was available here, so those checks should still be performed in a real browser.

## Known Issues
- The ligand page still fetches `/api/scaffold/<code>` separately when scaffold data is not already present in the bootstrap payload; that is unchanged in this pass.
- `/api/render-smiles/<smiles>` is still required for initial 2D SVG generation; caching or precomputed SVG delivery could speed this up further in a later pass.
- `get_ligand_visual()` still does several database queries per request; this pass removed obvious duplicate composite-key lookups, but deeper backend consolidation and caching remain possible.
- 3D rendering itself is still one of the heaviest client-side operations; lazy-loading or deferred surface rendering would be a strong next optimization.

## Manual Verification
1. Open `/ligand/LR00471`.
2. Confirm `/api/ligand-visual/LR00471` is called once during initial load.
3. Confirm `/api/fixed-2d-smiles/LR00471` is not called unless the bootstrap payload lacks SMILES.
4. Confirm SASA summary, 2D render, 3D render, SDF download, and PROTAC popup still work.
5. Confirm missing recruiter fallback still works for incomplete data.

## Suggested Next Prompt
Please implement the second ligand performance pass by adding lightweight caching for `/api/ligand-visual/<code>` and `/api/render-smiles/<smiles>`, and then defer noncritical 3D work until after the 2D/content panels are visible.
