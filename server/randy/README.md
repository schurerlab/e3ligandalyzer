# Randy immutable V1 backend

This directory is the version-controlled source capture for the Randy E3
scientific backend.  In production these files are installed at:

`/home/jxs794/PROTAC_BUILDER/backup_receiver/`

`e3_release_backend.py` validates the selected release manifest and SQLite
SHA-256 before opening the database in read-only mode.  `e3_data_routes.py`
exposes Randy's authenticated `/backup/e3` API, including manifest-indexed
`/instances/<Recruiter_Instance_ID>/pdb` and optional `/sdf` routes.

The web application uses `E3_DATA_MODE=remote_backend` and its Randy client to
consume this API.  The hosted application never mounts the release SQLite or
asset tree.  `test_v1_isolated.py` is the in-process Randy acceptance test;
run it on Randy with `E3_RELEASE_ROOT` set to the immutable release directory.
