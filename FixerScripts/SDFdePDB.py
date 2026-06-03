#!/usr/bin/env python3
"""
Batch converter:  Ligases/<LIGASE>/PDB/*.pdb  →  Ligases/<LIGASE>/SDF_4Download/*.sdf
Each .sdf contains only the HETATM records from its .pdb counterpart.
Requires Open Babel (obabel) in PATH.
"""
import os, subprocess, tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "Ligases"))

for ligase in os.listdir(ROOT):
    lig_dir = os.path.join(ROOT, ligase)
    pdb_dir = os.path.join(lig_dir, "PDB")
    if not os.path.isdir(pdb_dir):
        continue

    out_dir = os.path.join(lig_dir, "SDF_4Download")
    os.makedirs(out_dir, exist_ok=True)

    print(f"🔹 Processing ligase: {ligase}")
    for fname in os.listdir(pdb_dir):
        if not fname.lower().endswith(".pdb"):
            continue

        pdb_path = os.path.join(pdb_dir, fname)
        sdf_name = os.path.splitext(fname)[0] + ".sdf"
        sdf_path = os.path.join(out_dir, sdf_name)

        # Skip if already exists
        if os.path.exists(sdf_path):
            continue

        # Extract HETATM lines only
        het_lines = [l for l in open(pdb_path) if l.startswith("HETATM")]
        if not het_lines:
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdb") as tmp:
            tmp.writelines([l.encode() for l in het_lines])
            tmp_pdb = tmp.name

        cmd = ["obabel", tmp_pdb, "-O", sdf_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {fname} → {sdf_name}")
        else:
            print(f"❌ {fname} failed:\n{result.stderr}")

print("🎯 All done.")
