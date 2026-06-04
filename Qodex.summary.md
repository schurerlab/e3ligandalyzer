# Qodex.summary

## Task
Add Database Issue Reporting Workflow

## Original Goal
Add a button to ligand pages and create a new page that lets users report database/tool issues such as peptide-like fragments, BRD/BIRD-like incomplete molecules, incomplete ligand extraction, missing data, duplicate records, or broken downloads. Update public contact email to `jmschulz@med.miami.edu`.

## Assumptions
- The public reporting workflow should remain client-side only, using copy-to-clipboard plus `mailto:` rather than backend submission, because no secure mail infrastructure is present in this repo.
- `/report-issue` is the preferred route and should behave like the other static researcher-facing pages in `Ligase_app.py`.
- The best ligand-page placement is the existing action bar next to the PDB, SDF, and PROTAC actions because it is already the primary task cluster on the page.
- Ligand context is available after the existing bootstrap fetch in `templates/ligand.html`, so the report link can be updated there without broader page rewrites.
- Public contact email should come from one shared app config/context source instead of repeated hard-coded strings.
- Validation should use `python` rather than `python3` because this workspace’s `.python-version` targets Python 3.13, while the system `python3` is 3.9 and cannot import the existing `dict | None` annotations already present in `Ligases/routes.py`.

## Files Inspected
- `Ligase_app.py`: route style, context injection, missing-page renders, and public contact handling.
- `Ligases/routes.py`: import/runtime expectations and route compatibility context.
- `templates/ligand.html`: detail-page layout, action-bar placement, and available ligand bootstrap variables.
- `templates/contribute.html`: existing contribution and contact workflow.
- `templates/missing_data.html`: current copy-report behavior and missing-data context flow.
- `templates/missing_recruiter.html`: recruiter-specific missing-data report flow.
- `templates/about.html`: public-facing contact CTA.
- `templates/docs.html`: collaborator FAQ and public contact text.
- `templates/methods.html`: related-resource discoverability.
- `templates/release.html`: related-resource discoverability.
- `templates/base.html`: shared page structure.
- `static/components/footer.js`: connect links and site-wide discoverability.
- `README.md`: public-facing contact section.

## Files Changed
- `Ligase_app.py`: added shared support-email config/context, added `/report-issue`, and removed repeated hard-coded support-email template args.
- `templates/ligand.html`: added a visible `Report Issue` button in the action bar and JS to prefill recruiter, ligase, ligand, PDB, page URL, and source context.
- `templates/contribute.html`: updated contact email, added the new reporting path to hero actions and content sections.
- `templates/missing_data.html`: kept copy-report flow and added a link into `/report-issue` with missing-data context.
- `templates/missing_recruiter.html`: kept copy-report flow and added a link into `/report-issue` with recruiter context.
- `templates/about.html`: updated the public contact CTA and added a report-issue button.
- `templates/docs.html`: updated collaborator/contact guidance to use the new email and report page.
- `templates/methods.html`: added `/report-issue` to related resources.
- `templates/release.html`: added `/report-issue` to related resources.
- `static/components/footer.js`: updated contact/feedback email and added a footer link for reporting database issues.
- `README.md`: updated the public contact email.

## Files Created
- `templates/report_issue.html`: dedicated publication-friendly database-issue reporting page with structured email builder, preview, copy, and `mailto` workflow.
- `Qodex.summary.md`: implementation record and validation summary for this task.

## Implementation Summary
- Added a new `/report-issue` page that explains what kinds of database, curation, extraction, asset, visualization, and download problems should be reported and clearly states that the page only helps generate an email.
- Built a client-side report generator with optional reporter name/email, issue category, recruiter and structure context fields, expected versus observed behavior fields, evidence, file/path/API endpoint context, a live plain-text preview, a copy button, and a `mailto:jmschulz@med.miami.edu` button.
- Added query-string prefill support for `recruiter_code`, `ligase`, `ligand`, `pdb`, `issue_type`, `page`, and `source`.
- Added a new `Report Issue` button to the ligand-page action bar and wired it to prefill available context after the existing ligand bootstrap data load completes.
- Added discoverability links from the missing-data pages, contribute page, about page, release page, methods page, and footer.
- Centralized the public support email through app config/context and updated public-facing old email references to `jmschulz@med.miami.edu`.

## Key Decisions
- Used a mailto/copy-report workflow instead of backend email submission because the repo does not show an existing secure email-delivery path and the task explicitly discouraged adding one.
- Placed the ligand-page report button in the existing action bar so it is visible without disrupting the scientific content layout or requiring large template rewrites.
- Included issue categories directly matching the requested reviewer-facing scenarios: peptide-like fragments, BRD/BIRD-like incomplete molecules, single-ligand extraction issues, missing structure/SASA assets, incorrect recruiter/ligase/scaffold assignments, duplicate records, broken visualizations, broken download/API endpoints, and external-link issues.
- Replaced public hard-coded email strings where they surfaced in rendered pages and the footer, while moving future public email usage to a shared `SUPPORT_EMAIL` context value.

## Commands Run
- `rg -n "jxs794@miami\.edu|jmschulz@med\.miami\.edu|SUPPORT_EMAIL|mailto:|Contact|Feedback" .`
  Found old public email references and contact surfaces before editing.
- `rg -n "report|missing|contribute|about|docs|schema|methods|release|download_manifest|api-reference" Ligase_app.py templates static/components`
  Mapped relevant routes and templates before editing.
- `sed -n ...` on `Ligase_app.py`, `templates/ligand.html`, `templates/contribute.html`, `templates/missing_data.html`, `templates/missing_recruiter.html`, `templates/docs.html`, `templates/about.html`, `templates/methods.html`, `templates/release.html`, `templates/base.html`, and `static/components/footer.js`
  Inspected route patterns, existing UI placement, and contact text.
- `python -m py_compile Ligase_app.py Ligases/routes.py`
  Syntax validation under the project’s Python 3.13 interpreter succeeded.
- `python - <<'PY' ... test_client route smoke tests ... PY`
  Verified `/report-issue`, `/report-issue?...`, `/ligand/LR00001`, `/contribute`, `/missing`, `/missing-recruiter`, `/about`, and `/docs` all returned HTTP 200.
- `python - <<'PY' ... rendered HTML string checks ... PY`
  Confirmed report-page issue options, copy button, ligand-page report button, and preserved PDB/SDF/PROTAC controls.
- `rg -n "jxs794@miami\.edu|mailto:jxs794|SUPPORT_EMAIL|mailto:" .`
  Confirmed old public hard-coded email is gone and remaining `SUPPORT_EMAIL` references are shared template variables.

## Validation Results
- Route smoke tests passed for `/report-issue`, `/report-issue?recruiter_code=LR00001&ligase=CRBN&ligand=test&pdb=1XYZ&source=ligand-page`, `/ligand/LR00001`, `/contribute`, `/missing`, `/missing-recruiter`, `/about`, and `/docs`.
- Old public email references to `jxs794@miami.edu` were removed from public-facing app content and replaced with `jmschulz@med.miami.edu` or shared `SUPPORT_EMAIL` template usage.
- `/report-issue` renders and includes the requested issue categories, copy-report action, and email-report action.
- The ligand page still renders, still includes the PDB/SDF/PROTAC actions, and now includes a `Report Issue` button targeting `/report-issue`.
- Missing-data and contribute surfaces now expose the new reporting workflow.
- Prefill behavior was validated at the template and client-side script level via rendered HTML inspection and parameter wiring checks.

## Known Issues
- I did not perform a full browser-interaction pass in a live tab, so clipboard behavior, `mailto:` launch behavior, and the dynamic post-bootstrap report-link values were validated from code and rendered HTML rather than by clicking through in a browser.
- The local system `python3` binary is Python 3.9 and cannot import the existing `Ligases/routes.py` because that file already uses Python 3.10+ union-type syntax. The repo’s configured interpreter is `python` 3.13, which I used for route validation.
- A future GitHub issue-template or backend ticketing integration is still separate follow-up work.

## Manual Verification
1. Visit `/ligand/LR00001`.
2. Click `Report Issue`.
3. Confirm `/report-issue` opens with recruiter context prefilled.
4. Select `Peptide-like fragment / incomplete molecule`.
5. Enter observed issue text.
6. Confirm the report preview updates.
7. Click `Copy Report` and confirm useful plain text is copied.
8. Click `Email Report` and confirm it opens an email to `jmschulz@med.miami.edu`.
9. Visit `/contribute`, `/missing`, and `/missing-recruiter` and confirm reporting links are visible.
10. Confirm old public email addresses are no longer visible.

## Suggested Next Prompt
Add an optional GitHub issue-template or authenticated backend issue tracker integration for `/report-issue`, while preserving the current mailto/copy-report workflow as a no-credential fallback.
