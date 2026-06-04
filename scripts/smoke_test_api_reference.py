#!/usr/bin/env python3
"""Smoke-test the public API Reference examples for E3 Ligase Ligandalyzer."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass


DEFAULT_BASE_URL = "https://e3ligandalyzer.com/api"


@dataclass
class CheckResult:
    name: str
    ok: bool
    status: int | None
    detail: str


def fetch(url: str, timeout: int):
    req = urllib.request.Request(url, headers={"User-Agent": "e3-ligandalyzer-api-smoke/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, dict(resp.headers), body
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def json_check(base_url: str, path: str, *, required_keys=None, list_min_len=None, validator=None, timeout=60):
    status, headers, body = fetch(base_url + path, timeout)
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:
        return CheckResult(path, False, status, f"invalid JSON: {type(exc).__name__}")

    if status != 200:
        detail = payload.get("error") if isinstance(payload, dict) else f"unexpected status {status}"
        return CheckResult(path, False, status, str(detail))

    if required_keys:
        missing = [key for key in required_keys if key not in payload]
        if missing:
            return CheckResult(path, False, status, f"missing keys: {', '.join(missing)}")
    if list_min_len is not None:
        if not isinstance(payload, list) or len(payload) < list_min_len:
            size = len(payload) if isinstance(payload, list) else "non-list"
            return CheckResult(path, False, status, f"expected list with >= {list_min_len} rows, got {size}")
    if validator:
        ok, detail = validator(payload)
        if not ok:
            return CheckResult(path, False, status, detail)

    summary = ""
    if isinstance(payload, dict):
        summary = ",".join(list(payload)[:6])
    elif isinstance(payload, list):
        summary = f"list[{len(payload)}]"
    return CheckResult(path, True, status, summary)


def csv_check(base_url: str, path: str, *, timeout=90):
    status, headers, body = fetch(base_url + path, timeout)
    if status != 200:
        return CheckResult(path, False, status, body.decode("utf-8", "replace")[:120])
    text = body.decode("utf-8", "replace")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or not rows[0]:
        return CheckResult(path, False, status, "empty CSV")
    if len(rows) < 2:
        return CheckResult(path, False, status, "header present but no data rows")
    return CheckResult(path, True, status, f"{len(rows[0])} cols, {len(rows)-1} data rows")


def zip_check(base_url: str, path: str, *, timeout=180):
    status, headers, body = fetch(base_url + path, timeout)
    if status != 200:
        return CheckResult(path, False, status, body.decode("utf-8", "replace")[:120])
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            names = zf.namelist()
    except Exception as exc:
        return CheckResult(path, False, status, f"invalid ZIP: {type(exc).__name__}")
    if not names:
        return CheckResult(path, False, status, "ZIP is empty")
    return CheckResult(path, True, status, f"{len(names)} entries; sample={names[:3]}")


def svg_check(base_url: str, path: str, *, timeout=60):
    status, headers, body = fetch(base_url + path, timeout)
    text = body.decode("utf-8", "replace")
    if status != 200:
        return CheckResult(path, False, status, text[:120])
    if "<svg" not in text and not text.lstrip().startswith("<?xml"):
        return CheckResult(path, False, status, f"non-SVG payload: {text[:120]!r}")
    return CheckResult(path, True, status, text[:80].replace("\n", " "))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL to test")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    checks = [
        ("JSON", json_check, "/download/manifest", {"base_url", "ligase_count", "ligases", "tables"}, None, lambda p: (bool(p.get("ligase_count", 0) > 0 and p.get("ligases")), "manifest has no ligase entries")),
        ("JSON", json_check, "/download/manifest?ligase=CRBN", {"ligase_count", "ligases"}, None, lambda p: (bool(p.get("ligases")), "CRBN-filtered manifest has no ligase entries")),
        ("JSON", json_check, "/download/manifest?recruiter_code=LR00001", {"bundle_download", "entries", "count"}, None, lambda p: (bool(p.get("entries")), "recruiter manifest has no entries")),
        ("JSON", json_check, "/download/ligases", None, 1, None),
        ("JSON", json_check, "/download/recruiter-codes?ligase=CRBN&limit=25", {"count", "example_codes", "results"}, None, lambda p: (bool(p.get("example_codes")), "recruiter-code discovery returned no example codes")),
        ("ZIP", zip_check, "/download/ligase/CRBN/all.zip", None, None, None),
        ("ZIP", zip_check, "/download/ligase/CRBN/pdbs.zip", None, None, None),
        ("ZIP", zip_check, "/download/ligase/CRBN/sdfs.zip", None, None, None),
        ("ZIP", zip_check, "/download/recruiter/LR00001.zip", None, None, None),
        ("ZIP", zip_check, "/download/recruiters.zip?codes=LR00001,LR00002,LR00003", None, None, None),
        ("ZIP", zip_check, "/download/all/pdbs.zip", None, None, None),
        ("ZIP", zip_check, "/download/all/sdfs.zip", None, None, None),
        ("ZIP", zip_check, "/download/all/structures.zip", None, None, None),
        ("JSON", json_check, "/ligases", None, 1, None),
        ("JSON", json_check, "/featured-recruiters?ligase=CRBN&min_qed=0.5&limit=25", None, 1, None),
        ("JSON", json_check, "/scaffold-data?ligase=VHL", None, 1, None),
        ("JSON", json_check, "/scaffold-summary", None, 1, None),
        ("JSON", json_check, "/scaffold-frequency?ligase=CRBN", None, 1, None),
        ("JSON", json_check, "/scaffold-recruiters?ligase=CHIP", None, 1, None),
        ("JSON", json_check, "/descriptors/LR00001", None, 1, None),
        ("JSON", json_check, "/recruiter-smiles/LR00001", {"RECRUITER_CODE", "SMILES"}, None, lambda p: (bool(p.get("SMILES")), "recruiter SMILES missing")),
        ("JSON", json_check, "/ligand-visual/LR00001", {"ok", "descriptor", "metadata", "sasa_summary", "sasa_atoms"}, None, lambda p: (bool(p.get("ok")), "ligand-visual did not report ok=true")),
        ("JSON", json_check, "/sasa-full/LR00001", {"ok", "recruiter_code", "summary", "atoms"}, None, lambda p: (bool(p.get("ok")) and bool(p.get("atoms")), "sasa-full did not return atoms")),
        ("SVG", svg_check, "/render-smiles-by-code/LR00001", None, None, None),
        ("JSON", json_check, "/eliah/expression?gene=CRBN", None, 1, None),
        ("JSON", json_check, "/download/tables", None, 1, None),
        ("CSV", csv_check, "/download/table/Ligase_Scaffold_Data.csv", None, None, None),
        ("CSV", csv_check, "/download/table/Ligase_Ligand_SASA_summary.csv", None, None, None),
        ("CSV", csv_check, "/download/table/Ligase_Ligand_SASA_atoms.csv", None, None, None),
        ("CSV", csv_check, "/download/table/Ligase_Chemical_Descriptors.csv", None, None, None),
        ("CSV", csv_check, "/download/table/Ligase_Recruiters_Scaffold.csv", None, None, None),
    ]

    results: list[CheckResult] = []
    for kind, fn, path, required_keys, list_min_len, validator in checks:
        if fn is json_check:
            if required_keys:
                result = fn(base_url, path, required_keys=required_keys, validator=validator)
            else:
                result = fn(base_url, path, list_min_len=list_min_len, validator=validator)
        else:
            result = fn(base_url, path)
        result.name = f"{kind} {path}"
        results.append(result)

    print(f"{'STATUS':6} {'HTTP':4} {'CHECK':65} DETAIL")
    print("-" * 120)
    failed = 0
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        http = "" if result.status is None else str(result.status)
        print(f"{status:6} {http:4} {result.name[:65]:65} {result.detail}")
        if not result.ok:
            failed += 1

    if failed:
        print(f"\n{failed} checks failed.", file=sys.stderr)
        return 1

    print(f"\nAll {len(results)} checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
