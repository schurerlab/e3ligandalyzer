"""In-process acceptance test for Randy's immutable V1 E3 API."""
from __future__ import annotations

import os

from backup_receiver.app import APP
from backup_receiver.e3_data_routes import _token
from backup_receiver.e3_release_backend import ReleaseBackend


EXPECTED = {
    "Recruiter_Registry": 610,
    "Recruiter_Instance_Catalog": 1378,
    "Scaffold_Registry": 429,
    "Ligase_Recruiter_Catalog": 623,
    "Ligase_Scaffold_Data": 453,
}


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise AssertionError(detail)


def get(client, headers, path: str, **kwargs):
    response = client.get(path, headers=headers, buffered=False, **kwargs)
    return response


def main() -> None:
    backend = ReleaseBackend(os.environ["E3_RELEASE_ROOT"])
    client = APP.test_client()
    headers = {"Authorization": "Bearer " + _token()}

    response = get(client, headers, "/backup/e3/healthz")
    require(response.status_code == 200, f"healthz={response.status_code}")
    response.close()
    response = get(client, headers, "/backup/e3/release-info")
    release = response.get_json()
    require(response.status_code == 200 and release["database_sha256"] == backend.manifest["database"]["sha256"], "release-info")
    response.close()

    for table, expected in EXPECTED.items():
        response = client.post("/backup/e3/query", headers=headers, json={"sql": f"SELECT COUNT(*) AS n FROM {table}", "one": True})
        require(response.status_code == 200 and response.get_json()["rows"][0]["n"] == expected, f"{table} count")

    for row in backend.asset_rows():
        instance_id = row["Recruiter_Instance_ID"]
        response = get(client, headers, f"/backup/e3/instances/{instance_id}/pdb")
        require(response.status_code == 200, f"instance PDB {instance_id}={response.status_code}")
        response.close()

    response = get(client, headers, "/backup/e3/instances/LR00148-01/sdf")
    require(response.status_code == 200, f"A1IEV SDF={response.status_code}")
    response.close()
    response = get(client, headers, "/backup/e3/instances/LR00001-01/sdf")
    require(response.status_code == 404, f"missing SDF={response.status_code}")
    response.close()

    print({"ok": True, "instances": len(backend.asset_rows()), "sha256": backend.manifest["database"]["sha256"]})


if __name__ == "__main__":
    main()
