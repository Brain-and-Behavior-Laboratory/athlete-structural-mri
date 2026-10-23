from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import pandas as pd

from common import analysis_paths, load_config


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


def parse_table(text: str):
    rows = []
    for line in text.splitlines():
        fields = line.strip().split()
        if not fields or not fields[0].isdigit() or len(fields) < 14:
            continue
        rows.append(fields[:14])
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()
    cfg = load_config(args.config)
    paths = analysis_paths(cfg)
    alpha = float(cfg["vbm"]["corrected_alpha"])
    threshold = 1.0 - alpha
    cluster = cluster_command()

    output_rows = []
    for info_path in sorted(paths["vbm_work"].glob("*/analysis.json")):
        work = info_path.parent
        info = json.loads(info_path.read_text(encoding="utf-8"))
        for idx in (1, 2):
            corrp = work / "stats" / f"vbm_tfce_corrp_tstat{idx}.nii.gz"
            tstat = work / "stats" / f"vbm_tstat{idx}.nii.gz"
            if not corrp.exists() or not tstat.exists():
                raise FileNotFoundError(f"Missing VBM randomise output for {work.name}, tstat{idx}")
            cmd = [
                cluster,
                f"--in={corrp}",
                f"--thresh={threshold}",
                f"--cope={tstat}",
                "--scalarname=1-p",
                "--connectivity=26",
                "--mm",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            for fields in parse_table(result.stdout):
                output_rows.append(
                    {
                        "analysis": info["comparison"],
                        "contrast_index": idx,
                        "direction": info[f"tstat{idx}"],
                        "cluster_index": int(fields[0]),
                        "cluster_size_vox": int(fields[1]),
                        "max_corrected_1_minus_p": float(fields[2]),
                        "p_tfce_fwe": 1.0 - float(fields[2]),
                        "peak_corrected_x_mm": float(fields[3]),
                        "peak_corrected_y_mm": float(fields[4]),
                        "peak_corrected_z_mm": float(fields[5]),
                        "cog_x_mm": float(fields[6]),
                        "cog_y_mm": float(fields[7]),
                        "cog_z_mm": float(fields[8]),
                        "peak_t": float(fields[9]),
                        "peak_t_x_mm": float(fields[10]),
                        "peak_t_y_mm": float(fields[11]),
                        "peak_t_z_mm": float(fields[12]),
                        "mean_t": float(fields[13]),
                    }
                )
    out = pd.DataFrame(output_rows)
    out_path = paths["vbm_csv"] / "vbm_clusters.csv"
    out.to_csv(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
