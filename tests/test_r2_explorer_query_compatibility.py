import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
R2_RELEASE = ROOT / "releases" / "v1.0-locked-20260908-r2-app-validation"


class R2ExplorerQueryCompatibilityTests(unittest.TestCase):
    """Exercise R2 through an isolated Flask process, never Randy's SQLite."""

    def test_normalized_instance_queries_preserve_explorer_contract(self):
        script = r'''
import json
import sqlite3
from e3_database import configured_database_path
from Ligase_app import flask_app

client = flask_app.test_client()

def fetch(path):
    response = client.get(path)
    return response.status_code, response.get_json()

simple_status, simple = fetch("/api/recruiter-by-pdb?pdb_id=5FNU&ligand=L6I")
rnf_status, rnf = fetch("/api/recruiter-by-pdb?pdb_id=3V3L&ligand=V3L&variant=1")
multiple_status, multiple = fetch("/api/recruiter-by-pdb?pdb_id=3V3L&ligand=V3L")
prd_status, prd = fetch("/api/recruiter-by-pdb?pdb_id=8F15&ligand=PRD_002515&variant=1")
unknown_status, unknown = fetch("/api/recruiter-by-pdb?pdb_id=ZZZZ&ligand=NOT_A_COMPONENT")
code_status, codes = fetch("/api/download/recruiter-codes?ligase=KEAP1&limit=3")
manifest_status, manifest = fetch("/api/download/manifest?recruiter_code=LR00089")

with sqlite3.connect(f"file:{configured_database_path()}?mode=ro", uri=True) as conn:
    inactive = conn.execute(
        "SELECT pdb_id, Source_Entity_ID FROM Recruiter_Instance_Catalog "
        "WHERE Registry_Status = 'HISTORICAL_INACTIVE' LIMIT 1"
    ).fetchone()
if inactive:
    inactive_status, inactive_payload = fetch(
        f"/api/recruiter-by-pdb?pdb_id={inactive[0]}&ligand={inactive[1]}"
    )
    assert inactive_status == 404 and inactive_payload["error"] == "No recruiter instance found"
else:
    # The locked R2 artifact used by this isolated app fixture contains only
    # the 1,372 active observations. The route still carries the explicit
    # status filter for releases retaining historical allocations.
    inactive_status = None

assert simple_status == 200 and simple["Recruiter_Instance_ID"] == "LR00089-01"
assert simple["Source_Entity_ID"] == simple["Ligand"] == "L6I"
assert rnf_status == 200 and rnf["Recruiter_Instance_ID"] == "LR00362-01"
assert multiple_status == 409 and {row["Recruiter_Instance_ID"] for row in multiple["instances"]} == {"LR00362-01", "LR00362-02"}
assert prd_status == 200 and prd["Recruiter_Instance_ID"] == "LR00055-01"
assert prd["Source_Entity_ID"] == prd["Ligand"] == "PRD_002515"
assert unknown_status == 404 and unknown["error"] == "No recruiter instance found"
# The selected R2 app-validation bundle intentionally has no legacy download
# asset root.  These routes may report 503 for that separate asset condition,
# but must never fail from a missing normalized-catalog column.
assert code_status in {200, 503} and manifest_status in {200, 503}
for payload in (codes, manifest):
    assert "no such column" not in json.dumps(payload).lower()

print(json.dumps({
    "simple": simple_status, "rnf": rnf_status, "multiple": multiple_status,
    "prd": prd_status, "unknown": unknown_status, "inactive": inactive_status,
    "code_index": code_status, "manifest": manifest_status,
}, sort_keys=True))
'''
        environment = os.environ.copy()
        for variable in (
            "E3_DATA_BACKEND", "E3_USE_RANDY", "E3_RANDY_BASE_URL",
            "RANDY_E3_BASE_URL", "E3_RANDY_TOKEN", "RANDY_E3_TOKEN",
        ):
            environment.pop(variable, None)
        environment.update({
            "E3_DATA_MODE": "local_release",
            "E3_RELEASE_ROOT": str(R2_RELEASE),
            "PYTHONPATH": str(ROOT),
        })
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        results = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(results["simple"], 200)
        self.assertEqual(results["rnf"], 200)
        self.assertEqual(results["multiple"], 409)
        self.assertEqual(results["prd"], 200)
        self.assertEqual(results["unknown"], 404)
        self.assertIn(results["inactive"], (404, None))

    def test_source_uses_normalized_instance_fields_for_r2_aliases(self):
        source = (ROOT / "Ligases" / "routes.py").read_text(encoding="utf-8")
        self.assertIn("i.Source_Entity_ID AS Ligand", source)
        self.assertIn("s.Variant AS Variant", source)
        self.assertIn("i.Registry_Status = 'ACTIVE'", source)
        self.assertNotIn("AND Ligand = ? COLLATE NOCASE", source)
        self.assertNotIn("SELECT Recruiter_ID, Recruiter_Instance_ID, Ligase, pdb_id, Ligand, Variant\n        FROM Recruiter_Instance_Catalog", source)
