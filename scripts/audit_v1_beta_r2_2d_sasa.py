#!/usr/bin/env python
"""Exercise every V1 Beta R2 2D SASA endpoint against the local bundle."""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
SCI = Path("/Users/jxs794/Desktop/E3Ligandalyzer")
RELEASE = APP / "releases/v1.0-beta-r2-20260912"
sys.path.insert(0, str(APP))

# This must happen before importing the Flask application/database singleton.
os.environ["E3_RELEASE_ROOT"] = str(RELEASE)
os.environ["E3_REMOTE_BACKEND"] = "0"

from Ligase_app import flask_app  # noqa: E402
from e3_database import E3Database  # noqa: E402


def main() -> None:
    database = E3Database()
    instances = database._all(
        "SELECT Recruiter_Instance_ID FROM Recruiter_Instance_Catalog ORDER BY Recruiter_Instance_ID"
    )
    client = flask_app.test_client()
    rows = []
    failures = []
    mapped_count = unavailable_count = 0
    for record in instances:
        instance_id = record["Recruiter_Instance_ID"]
        mapping = database.instance_atom_mapping(instance_id)
        validated_mapping = [
            row for row in mapping
            if row.get("Mapping_Status") == "VALIDATED_CANONICAL_ATOM_MAPPING"
        ]
        expected_mapped = bool(validated_mapping)
        response = client.get(f"/api/instances/{instance_id}/render-2d-sasa")
        svg_ok = response.status_code == 200 and response.mimetype == "image/svg+xml" and b"<svg" in response.data
        unavailable_ok = response.status_code == 409 and b"validated 2D atom mapping" in response.data
        status = "PASS_MAPPED" if expected_mapped and svg_ok else "PASS_UNAVAILABLE" if not expected_mapped and unavailable_ok else "FAIL"
        if expected_mapped:
            mapped_count += 1
        else:
            unavailable_count += 1
        if status == "FAIL":
            failures.append(
                f"{instance_id}: validated_mappings={len(validated_mapping)} status={response.status_code}"
            )
        rows.append({
            "Recruiter_Instance_ID": instance_id,
            "provenance_rows": len(mapping),
            "validated_mapping_rows": len(validated_mapping),
            "endpoint_status": response.status_code,
            "endpoint_result": status,
        })
        response.close()
    destination = SCI / "Corpus_Audit" / "V1_Beta_R2_2D_SASA_Audit.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"instances={len(rows)} mapped={mapped_count} unavailable={unavailable_count} failures={len(failures)}")
    if failures:
        print("\n".join(failures[:50]))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
