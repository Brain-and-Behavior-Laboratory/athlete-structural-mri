from __future__ import annotations

import argparse
from pathlib import Path

from common import analysis_paths, load_config, require_commands, run_command


def analyses(paths):
    return sorted(p.parent for p in paths["vbm_work"].glob("*/analysis.json"))


def run_bet(work: Path, cfg: dict, log: Path):
    option = str(cfg["vbm"].get("bet_option", "-b")).strip()
    cmd = ["fslvbm_1_bet"]
    if option:
        cmd.append(option)
    run_command(cmd, cwd=work, log_path=log)


def run_template(work: Path, cfg: dict, log: Path):
    option = str(cfg["vbm"].get("template_option", "-n")).strip()
    cmd = ["fslvbm_2_template"]
    if option:
        cmd.append(option)
    run_command(cmd, cwd=work, log_path=log)


def run_proc(work: Path, cfg: dict, log: Path):
    run_command(["fslvbm_3_proc"], cwd=work, log_path=log)
    sigma = str(cfg["vbm"].get("smoothing_sigma_mm", 3))
    expected = work / "stats" / f"GM_mod_merg_s{sigma}.nii.gz"
    if not expected.exists():
        # Common integer naming fallback, e.g. config 3.0 -> s3.
        try:
            sigma_float = float(sigma)
            if sigma_float.is_integer():
                expected = work / "stats" / f"GM_mod_merg_s{int(sigma_float)}.nii.gz"
        except ValueError:
            pass
    if not expected.exists():
        raise FileNotFoundError(
            f"Expected smoothed modulated VBM input was not found: {expected}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument(
        "--stage",
        choices=["all", "bet", "template", "proc"],
        default="all",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = analysis_paths(cfg)
    require_commands(["fslvbm_1_bet", "fslvbm_2_template", "fslvbm_3_proc"])

    works = analyses(paths)
    if not works:
        raise RuntimeError("No prepared VBM analyses. Run 10_vbm_prepare_comparisons.py.")

    for work in works:
        log = paths["logs"] / f"vbm_{work.name}.log"
        print(f"VBM {args.stage}: {work.name}")
        if args.stage in ("all", "bet"):
            run_bet(work, cfg, log)
        if args.stage in ("all", "template"):
            run_template(work, cfg, log)
        if args.stage in ("all", "proc"):
            run_proc(work, cfg, log)


if __name__ == "__main__":
    main()
