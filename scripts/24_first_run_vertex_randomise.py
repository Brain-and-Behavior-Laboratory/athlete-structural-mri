from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import analysis_paths, load_config, require_commands, run_command


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = analysis_paths(cfg)
    require_commands(["randomise"])

    n_perm = int(cfg["first"]["permutations"])
    tfce_option = str(cfg["first"].get("tfce_option", "-T"))

    analyses = sorted(paths["first_work"].glob("vertex/*/*/analysis.json"))
    if not analyses:
        raise RuntimeError("No FIRST vertex analyses were prepared.")

    for info_path in analyses:
        work = info_path.parent
        info = json.loads(info_path.read_text(encoding="utf-8"))

        input_img = work / "vertex.nii.gz"
        mask = work / "vertex_mask.nii.gz"
        if not input_img.exists():
            raise FileNotFoundError(input_img)
        if not mask.exists():
            raise FileNotFoundError(mask)

        cmd = [
            "randomise",
            "-i", str(input_img),
            "-m", str(mask),
            "-o", str(work / "rand"),
            "-d", str(work / "design.mat"),
            "-t", str(work / "design.con"),
            "-f", str(work / "design.fts"),
            "-n", str(n_perm),
            "-D",
            tfce_option,
        ]
        log = paths["logs"] / (
            f"first_vertex_randomise_{info['comparison']}_{info['structure']}.log"
        )
        print(f"randomise FIRST: {info['comparison']} / {info['structure']}")
        run_command(cmd, cwd=work, log_path=log)


if __name__ == "__main__":
    main()
