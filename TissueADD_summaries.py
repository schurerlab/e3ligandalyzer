#!/usr/bin/env python3
"""
Ligase CSV Stats Generator — Streaming Accurate Version
──────────────────────────────────────────────
Computes all stats from gene_expression_with_tissue.csv
without splitting data incorrectly.
Accurate for very large datasets.
"""

import csv, math, json
from pathlib import Path
from collections import defaultdict

IN_FILE = Path("Ligases/gene_expression_with_tissue.csv")
OUT_DIR = Path("Ligases/CSVcache")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Running accumulators
lig_sum = defaultdict(float)
lig_abs_sum = defaultdict(float)
lig_sq_sum = defaultdict(float)
lig_count = defaultdict(int)

lig_tissue_sum = defaultdict(float)
lig_tissue_count = defaultdict(int)

# Global stats for enrichment
global_sum = 0.0
global_sq_sum = 0.0
global_n = 0

print(f"📘 Streaming {IN_FILE.name} ...")

with open(IN_FILE, newline='') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader, 1):
        try:
            z = float(row["Z_score"])
            g = row["Gene"]
            t = row["Tissgrp"]
        except (KeyError, ValueError):
            continue

        # Per-gene accumulators
        lig_sum[g] += z
        lig_abs_sum[g] += abs(z)
        lig_sq_sum[g] += z*z
        lig_count[g] += 1

        # Per-gene × tissue
        key = (g, t)
        lig_tissue_sum[key] += z
        lig_tissue_count[key] += 1

        # Global
        global_sum += z
        global_sq_sum += z*z
        global_n += 1

        if i % 5_000_000 == 0:
            print(f"🧩 Processed {i:,} rows...")

print(f"✅ Finished streaming {global_n:,} rows")

# ==========================
# 🔹 Compute summaries
# ==========================
global_mean = global_sum / global_n
global_std = math.sqrt(global_sq_sum / global_n - global_mean**2)

mean_abs = {g: lig_abs_sum[g]/lig_count[g] for g in lig_count}
std_z = {g: math.sqrt(lig_sq_sum[g]/lig_count[g] - (lig_sum[g]/lig_count[g])**2)
         for g in lig_count}

# Write per-ligase stats
with open(OUT_DIR / "ligase_mean_abs_z.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Ligase", "mean_abs_z"])
    for g,v in mean_abs.items(): w.writerow([g, round(v,3)])

with open(OUT_DIR / "ligase_std_z.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Ligase", "std_z"])
    for g,v in std_z.items(): w.writerow([g, round(v,3)])

# Per-tissue averages + enrichment
with open(OUT_DIR / "ligase_tissue_avg.csv", "w", newline="") as f1, \
     open(OUT_DIR / "ligase_tissue_enrichment.csv", "w", newline="") as f2:
    w1, w2 = csv.writer(f1), csv.writer(f2)
    w1.writerow(["Ligase","Tissgrp","avg_z"])
    w2.writerow(["Ligase","Tissgrp","enrichment_z"])
    for (g,t),s in lig_tissue_sum.items():
        avg = s/lig_tissue_count[(g,t)]
        enr = (avg - global_mean)/global_std if global_std else 0
        w1.writerow([g,t,round(avg,3)])
        w2.writerow([g,t,round(enr,3)])

# Specificity index
lig_tissue_values = defaultdict(list)
for (g,t),s in lig_tissue_sum.items():
    lig_tissue_values[g].append(s/lig_tissue_count[(g,t)])
variances = {g: (sum((x - (sum(v)/len(v)))**2 for x in v)/len(v))
             for g,v in lig_tissue_values.items() if len(v)>1}
global_var = sum(variances.values())/len(variances)
spec_index = [(g, round(1 - (v/global_var if global_var else 0),3))
              for g,v in variances.items()]

with open(OUT_DIR / "ligase_specificity_index.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Ligase","Specificity"])
    w.writerows(spec_index)

# Optional JSON cache
for csv_file in OUT_DIR.glob("*.csv"):
    import pandas as pd
    df = pd.read_csv(csv_file)
    df.to_json(csv_file.with_suffix(".json"), orient="records", indent=2)

print("🏁 Done — all CSVs and JSONs written accurately.")
