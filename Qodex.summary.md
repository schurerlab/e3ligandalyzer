# Qodex.summary

## Task
Fix scaffold hover molecule preview placement.

## Original Goal
Make scaffold hover molecule previews visible on the scaffold page, especially in the small network viewer, instead of being pushed offscreen or hidden near the footer.

## Assumptions
- The scaffold dashboard’s small Cytoscape network is the primary UX problem, so it should get the strongest fix.
- Top scaffold cards and Plotly points should keep using the shared floating tooltip unless that would clearly break existing behavior.
- The full scaffold network page can stay tooltip-based, but it benefits from viewport clamping and stale-request protection.

## Files Inspected
- `templates/scaffolds.html` — inspect the small scaffold network, top scaffold cards, Plotly hover handlers, shared tooltip logic, and modal behavior.
- `templates/scaffold_network_full.html` — inspect the full-network tooltip and modal behavior for the same clipping/race issue.
- `templates/scaffold_detail.html` — use the existing viewport-safe tooltip positioning pattern as a reference.
- `Qodex.summary.md` — replace the prior task summary with this scaffold preview fix.

## Files Changed
- `templates/scaffolds.html` — added an inline scaffold network preview panel, switched the small Cytoscape network hover behavior to use it, hardened the shared floating tooltip, and added stale-request guards.
- `templates/scaffold_network_full.html` — added viewport clamping and stale-request protection to the floating scaffold tooltip, and removed duplicate SMILES fetch/render work.
- `Qodex.summary.md` — updated for this scaffold hover preview task.

## Files Created
- `Qodex.summary.md` — rewritten to capture this task’s implementation and validation details.

## Implementation Summary
The scaffold dashboard now uses an inline preview panel directly below the small `#scaffold-network` viewer instead of relying on the old floating tooltip for Cytoscape node hover.

That panel now shows:
- scaffold title/ID,
- ligase badges,
- rendered molecule SVG,
- SMILES text,
- a loading state while the SVG is fetched.

The panel keeps the last hovered scaffold visible on mouseout and changes the subtitle to a gentle “Hover another scaffold to update this preview” message, which avoids flicker and prevents the preview from disappearing near the footer.

The shared floating tooltip used by Plotly hover points and scaffold cards was also improved:
- fixed-position tooltip now clamps to the viewport,
- it uses `clientX/clientY`-compatible positioning logic,
- SVG content is size-constrained,
- stale async `/api/render-smiles/...` responses are ignored.

The full scaffold network page kept its floating tooltip UX, but that tooltip now also clamps to the viewport, avoids stale async overwrite races, and no longer performs the same render fetch twice.

## Key Decisions
- Implemented the recommended inline preview panel for the small dashboard network because it is the most stable fix for a compact card near the footer/right edge.
- Preserved the floating tooltip for top scaffold cards and Plotly hover points, but made it viewport-safe instead of replacing those interactions outright.
- Kept the last dashboard network preview visible after mouseout to reduce flicker and help users inspect the structure.
- Added simple request-id guards for both the dashboard preview and floating tooltips so fast hover changes cannot let older SVG fetches overwrite newer ones.

## Commands Run
- `rg -n "scaffold-network|showMolTooltip|hideMolTooltip|tooltipDiv|mol-tooltip|plotly_hover|mouseover|mouseout|render-smiles|showModal|Open Full View" templates` — locate all scaffold hover/preview logic.
- `sed -n '1,320p' templates/scaffolds.html` — inspect dashboard structure and hover setup.
- `sed -n '320,760p' templates/scaffolds.html` — inspect shared tooltip, modal, and network hover code.
- `sed -n '1,360p' templates/scaffold_network_full.html` — inspect full-network tooltip and modal code.
- `sed -n '1,360p' templates/scaffold_detail.html` — inspect viewport-safe tooltip positioning reference.
- `python Ligase_app.py` — run the local Flask app for browser validation on `http://127.0.0.1:5025`.

## Validation Results
- Manual browser validation was performed on `http://127.0.0.1:5025/scaffolds`:
  - The scaffold dashboard loaded successfully.
  - The small scaffold network card displayed the new inline preview panel directly below the network.
  - Hovering a real node in the small network updated the panel successfully with:
    - scaffold title (`LR-SCAF00372`)
    - ligase badge (`CRBN`)
    - rendered SVG structure
    - SMILES text
  - The inline preview remained fully visible inside the dashboard card area instead of floating offscreen.
  - The mouseout state kept the preview visible and updated the subtitle to “Hover another scaffold to update this preview.”
- Manual browser validation was also performed on `http://127.0.0.1:5025/scaffold-network-full`:
  - The page loaded successfully after tooltip changes.
  - No browser console errors were introduced on either scaffold page.
- Direct browser confirmation of top scaffold card hover tooltip behavior was not completed in this run, although that code path was intentionally preserved and the shared tooltip used by those cards was hardened.
- Direct browser confirmation of Plotly hover tooltip behavior was also not completed in this run, although the same shared tooltip path was preserved and improved.

## Known Issues
- The small dashboard network preview currently keeps the last hovered scaffold visible rather than hiding entirely on mouseout. This is intentional UX, but if a stricter hide-on-leave behavior is preferred it can be changed later.
- Top scaffold card hover and Plotly hover should still work through the shared tooltip path, but they should receive one final human spot-check in the browser because this run focused validation on the small network and full-network pages.

## Manual Verification
1. Open `/scaffolds`.
2. Hover nodes in the small Scaffold Network card.
3. Confirm the molecule preview is visible inside or directly below the network card and does not go offscreen.

## Suggested Next Prompt
Please polish the scaffold dashboard preview further by adding a tiny fade transition and a compact “click node to open scaffold page” helper line inside the inline network preview panel.
