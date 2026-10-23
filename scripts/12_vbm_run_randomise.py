from __future__ import annotations

import argparse
from pathlib import Path

from common import analysis_paths, load_config, require_commands, run_command


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = analysis_paths(cfg)
    require_commands(["randomise"])

    sigma = cfg["vbm"].get("smoothing_sigma_mm", 3)
    sigma_name = str(int(sigma)) if float(sigma).is_integer() else str(sigma)
    n_perm = int(cfg["vbm"]["permutations"])
    tfce_option = str(cfg["vbm"].get("tfce_option", "-T"))

    analyses = sorted(p.parent for p in paths["vbm_work"].glob("*/analysis.json"))
    for work in analyses:
        input_img = work / "stats" / f"GM_mod_merg_s{sigma_name}.nii.gz"
        mask = work / "stats" / "GM_mask.nii.gz"
        if not input_img.exists():
            raise FileNotFoundError(input_img)
        if not mask.exists():
            raise FileNotFoundError(mask)

        cmd = [
            "randomise",
            "-i", str(input_img),
            "-m", str(mask),
            "-o", str(work / "stats" / "vbm"),
            "-d", str(work / "design.mat"),
            "-t", str(work / "design.con"),
            tfce_option,
            "-n", str(n_perm),
        ]
        log = paths["logs"] / f"vbm_randomise_{work.name}.log"
        print(f"randomise: {work.name}")
        run_command(cmd, cwd=work, log_path=log)


if __name__ == "__main__":
    main()
