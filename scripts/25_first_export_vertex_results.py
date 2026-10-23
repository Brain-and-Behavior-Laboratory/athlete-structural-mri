from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd

from common import analysis_paths, effect_sizes, load_config


def cluster_command() -> str:
    fsldir = os.environ.get("FSLDIR", "")
    if fsldir:
        candidate = Path(fsldir) / "bin" / "fsl-cluster"
        if candidate.exists():
            return str(candidate)
    for name in ("fsl-cluster", "cluster"):
        found = shutil.which(name)
        if found:
            return found
    raise RuntimeError("Could not locate FSL fsl-cluster/cluster command.")


def parse_rows(text: str):
    rows = []
    for line in text.splitlines():
        fields = line.strip().split()
        if fields and fields[0].isdigit() and len(fields) >= 14:
            rows.append(fields[:14])
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()
    cfg = load_config(args.config)
    paths = analysis_paths(cfg)
    alpha = float(cfg["first"]["corrected_alpha"])
    threshold = 1.0 - alpha
    cluster = cluster_command()
    output_rows = []

    for info_path in sorted(paths["first_work"].glob("vertex/*/*/analysis.json")):
        work = info_path.parent
        info = json.loads(info_path.read_text(encoding="utf-8"))
        order = pd.read_csv(work / "analysis_order.csv")
        data = np.asarray(nib.load(str(work / "vertex.nii.gz")).dataobj)

        for idx in (1, 2):
            corrp = work / f"rand_tfce_corrp_tstat{idx}.nii.gz"
            tstat = work / f"rand_tstat{idx}.nii.gz"
            if not corrp.exists() or not tstat.exists():
                continue
            index_img = work / f"cluster_index_tstat{idx}.nii.gz"
            cmd = [
                cluster,
                f"--in={corrp}",
                f"--thresh={threshold}",
                f"--cope={tstat}",
                f"--oindex={index_img}",
                "--scalarname=1-p",
                "--connectivity=26",
                "--mm",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            table_rows = parse_rows(result.stdout)
            if not table_rows:
                continue
            labels = np.asarray(nib.load(str(index_img)).dataobj)
            for fields in table_rows:
                cluster_id = int(fields[0])
                mask = labels == cluster_id
                subject_means = data[mask, :].mean(axis=0)
                if len(subject_means) != len(order):
                    raise RuntimeError("FIRST vertex subject dimension does not match analysis order.")
                a = subject_means[order["group"].to_numpy() == info["group_a"]]
                b = subject_means[order["group"].to_numpy() == info["group_b"]]
                eff = effect_sizes(a, b)
                output_rows.append(
                    {
                        "comparison": info["comparison"],
                        "structure": info["structure"],
                        "contrast_index": idx,
                        "direction": info[f"tstat{idx}"],
                        "cluster_index": cluster_id,
                        "cluster_size_vox": int(fields[1]),
                        "max_corrected_1_minus_p": float(fields[2]),
                        "p_fwe": 1.0 - float(fields[2]),
                        "corrected_peak_x_mm": float(fields[3]),
                        "corrected_peak_y_mm": float(fields[4]),
                        "corrected_peak_z_mm": float(fields[5]),
                        "peak_t": float(fields[9]),
                        "peak_t_x_mm": float(fields[10]),
                        "peak_t_y_mm": float(fields[11]),
                        "peak_t_z_mm": float(fields[12]),
                        "mean_t": float(fields[13]),
                        "cluster_mean_group_a": float(a.mean()),
                        "cluster_mean_group_b": float(b.mean()),
                        **eff,
                    }
                )
    out = pd.DataFrame(output_rows)
    out_path = paths["first_csv"] / "first_vertex_clusters.csv"
    out.to_csv(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
