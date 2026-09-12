# E3 Ligandalyzer V1 application migration

## Runtime contract

The Flask application reads the immutable V1 release through
`e3_database.E3Database`.  It opens SQLite with `mode=ro`, enables
`PRAGMA query_only`, and accepts only `SELECT`, `WITH`, and `PRAGMA` queries.
The release path is configured by `E3_DATABASE_PATH` (or the temporary legacy
alias `E3_LOCAL_DB_PATH`), defaulting to `data/E3_Ligandalyzer_v1.0.sqlite`.

This application copy is byte-identical to the supplied scientific release;
the upstream pipeline artifact is never opened for write or changed.

## Identifier model

| Meaning | V1 identifier | Application route |
| --- | --- | --- |
| Canonical chemical/recruiter entity | `Recruiter_ID` | `/recruiter/<Recruiter_ID>` |
| Exact observed physical structure instance | `Recruiter_Instance_ID` | `/ligand/<Recruiter_Instance_ID>` |
| Historical/source identifier | `PreRegistry_RECRUITER_CODE`, `Source_Entity_ID`, or ligand code | `/ligand/<code>` resolves only an exact, unambiguous match |

An entity page lists every physical instance.  `/instance/<id>` is retained as
a 302 compatibility redirect to the canonical `/ligand/<id>` rich viewer.
Source identifiers that map to multiple entities are sent to search instead of
silently picking a record.

## Canonical rich structure viewer

`/ligand/<Recruiter_Instance_ID>` uses the established interactive NGL/RDKit
viewer with an exact V1 payload from `/api/instances/<id>/visual`.  The payload
contains the selected instance, its parent entity, every sibling instance,
stored SASA/mapping rows, and direct exact-asset endpoints.  The viewer never
derives PDB/SDF filenames: `/api/instances/<id>/pdb` and
`/api/instances/<id>/sdf` serve only the path recorded in that V1 instance.
Sibling changes update the URL/history and clear the active 3D scene before the
next exact instance is rendered.  Entity URLs (`/recruiter/<Recruiter_ID>`) are
overviews and cannot silently select an observation.

The 3D SASA overlay is derived only from the selected instance's stored
`Ligase_Ligand_SASA_atoms` rows intersected with its stored
`Ligase_Ligands_Smiles_3DMapped` rows.  The merge key is the selected
`Recruiter_Instance_ID`, `SASA_atom_id`, and `instance_sdf_atom_index`; it is
not a parent-entity atom index or a coordinate-nearest-neighbor calculation.
The viewer also uses a per-render generation token, so superseded async NGL
loads cannot add an old SASA component after a later mode toggle or instance
selection.

Entity pages expose a normal canonical depiction at
`/api/recruiters/<Recruiter_ID>/render-2d`.  It uses only
`Recruiter_Catalog.Canonical_SMILES` and deliberately has no structural SASA
coloring.

## Legacy-to-V1 crosswalk

| Legacy use | V1 source and behavior |
| --- | --- |
| `Ligand_Instance_Recruiter_Codes` and per-row recruiter codes | `Recruiter_Catalog` for entity identity plus `Recruiter_Instance_Catalog` for exact structures. |
| `Ligase_Chemical_Descriptors` | Same-named V1 table, joined to `Recruiter_Catalog` by `Recruiter_ID`. |
| `Ligase_Ligand_Metadata` | `Recruiter_Instance_Catalog` for structural provenance and the V1 metadata table for instance-level annotations. |
| SASA summary, atoms, and atom mapping | `Ligase_Ligand_SASA_summary`, `Ligase_Ligand_SASA_atoms`, and `Ligase_Ligands_Smiles_3DMapped`, all queried by `Recruiter_Instance_ID`. |
| Recruiter/ligase relationship | `Ligase_Recruiter_Catalog`, queried at entity level. |
| Scaffold listing and detail | `Scaffold_Catalog` and `Ligase_Scaffold_Data`; entity members come from `Recruiter_Catalog`. |
| Old source/master maps | `Source_Entity_Recruiter_Crosswalk` and `Source_Entity_Ambiguity`. |
| Old V1 release-derived counts | `Recruiter_Registry`, `Recruiter_Instance_Registry`, `Scaffold_Registry`, and `__release_info`. |

## Deliberate non-equivalences and follow-up work

V1 does not provide legacy supercluster, centroid, normalized-diversity, or
Shannon-entropy fields.  Related compatibility responses return `null` rather
than fabricating values.  The specialized legacy molecular visual endpoints
also retain old asset naming/path expectations; they need a V1 asset manifest
before they can reliably render V1 coordinates or files.

`Ligases/eliah.db` remains a separate tissue-expression application database,
not part of the scientific V1 release.  Remote RANDY deployment is deliberately
out of scope for this local migration.
