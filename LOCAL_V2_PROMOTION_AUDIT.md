# Local V2 promotion audit

## Scope and release linkage

This is a local-only promotion.  The active application release is resolved
from `E3_RELEASE_ROOT` when set, otherwise from `releases/current`.  From that
single root the application derives both:

- `database/E3_Ligandalyzer_v1.0.sqlite`
- `assets/`

`e3_database.py` verifies the database SHA-256 against the release manifest
before opening a read-only SQLite URI connection.  It also enables
`PRAGMA query_only=ON`.  Thus a selected versioned release cannot silently
combine its database with a different asset root.

## Historical route trace and V2 handling

| Route/function family | Historical behavior | V2 behavior |
| --- | --- | --- |
| `e3_database.configured_database_path` | `E3_DATABASE_PATH` / `E3_LOCAL_DB_PATH`, then `data/` | Derives the database from `E3_RELEASE_ROOT` or `releases/current` first. |
| `/api/instances/<id>/pdb` | Built a path from `Step4_PDB` under the app's `Ligases/<ligase>/PDB` | Looks up the exact instance in `manifests/Web_Asset_Manifest.csv`; verifies the selected `Source_Instance_Key`; serves only that manifest path. |
| `/api/instances/<id>/sdf` | Built a path from `Source_SDF` under legacy `SDF_4Download` | Looks up the release manifest. It returns only a shared authoritative chemistry SDF, and returns 404 when none is available. |
| `/api/instances/<id>/visual` | Supplied PDB/SDF URLs and SASA data | Uses the exact manifest-backed PDB/SDF URLs, database SASA rows, and atom provenance. |
| `/api/instances/<id>/sasa*`, `/mapped-atoms`, `/render-2d-sasa` | SQLite SASA / RDKit depiction | Continue to use the selected read-only V2 database; no filesystem structure fallback. |
| `/api/recruiters/<id>/render-2d`, `/api/render-smiles` | RDKit entity-level 2D depiction | Continue to render from V2 canonical chemistry in SQLite. |
| `/api/ligase-pdbs`, `/api/Ligases/...`, `/Ligases/...`, download helpers | Traversed application `Ligases/` directories; several old variant-search blocks remain as unreachable legacy code after early returns | Their active local root is `assets/Ligases/` in the selected release. Exact instance APIs are the supported viewer/download contract; unavailable generic SDF names return 404 rather than probing historical files. |
| `/api/render-sdf`, `/api/render-3d-sdf` | Searched historical SDF/SDF_3DDisplay directories | Their active local lookup root is release-owned only; no historical directory is used. |
| Session SDF route | `tmp_sessions/` app-generated temporary state | Outside the immutable scientific release; it is not an authoritative chemistry asset route. |

The normal 3D viewer contract is an exact physical recruiter instance, not a
PDB ID or ligand-code lookup.  The promoted structural representation is
therefore staging **Step 4 `PRosettaC_PDB`**: it is the selected E3/recruiter
coordinate context named by each active `Step4_PDB` record.  Step 1 and Step 3
were not substituted.

## Asset policy

- Every active instance has one fresh, hash-verified Step 4 PDB at
  `assets/Ligases/<Ligase>/PDB/<Recruiter_Instance_ID>.pdb`.
- Chemistry SDFs are shared by `Source_Entity_ID` only when a validated
  staging chemistry SDF exists.  They are not inferred from old per-instance
  files.  BIRD/PRD observations intentionally have no fragment SDF and use
  their whole-entity exact PDB.
- A1IEV uses
  `Chemistry_Input/CCD_Derived/A1IEV_from_CCD_InChI.sdf`.
- `Web_Asset_Orphan_Audit.csv` classifies every release asset as either
  `ACTIVE_REFERENCED` or `SHARED_ACTIVE_CHEMISTRY`; `ORPHAN = 0`.

## Promotion validation summary

- Database SHA-256: `dda4290bc65d0c8c65a59b845c95699f802311305ab81d42b2895732cbd6bb40`
- SQLite integrity check: `ok`
- Active canonical recruiters / instances / scaffolds / ligases:
  `604 / 1372 / 428 / 35`
- Exact PDB manifest rows / unique PDB targets / HTTP-resolvable instance PDB routes:
  `1372 / 1372 / 1372`
- Recruiter pages resolving over local HTTP: `604 / 604`
- Post-cutoff TRIM21 PDB IDs `32QL`–`32QR`: absent.
- The seven explicit MDM2 exclusions: absent.

The release builder is `scripts/promote_v2_local_release.py`.  It builds a
temporary clean bundle, copies and validates the database and assets, locks
the final bundle read-only, then atomically replaces `releases/current` with a
symlink to `v1.0-corrected`.
