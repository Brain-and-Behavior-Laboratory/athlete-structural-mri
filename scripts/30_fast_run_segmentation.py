from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from common import analysis_paths, load_config, read_participants, require_commands, run_command


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = analysis_paths(cfg)
    participants = read_participants(paths)
    require_commands(["bet", "fast"])

    n_classes = int(cfg["fast"]["number_of_classes"])
    bet_f = cfg["fast"].get("bet_fractional_intensity")

    for _, row in participants.iterrows():
        subject = str(row["subject"])
        work = paths["fast_work"] / f"sub-{subject}"
        work.mkdir(parents=True, exist_ok=True)

        local_t1 = work / "t1.nii.gz"
        if not local_t1.exists():
            shutil.copy2(Path(row["t1_path"]), local_t1)

        brain = work / "t1_brain.nii.gz"
        if not brain.exists() or args.force:
            cmd = ["bet", str(local_t1), str(brain)]
            if bet_f is not None:
                cmd += ["-f", str(float(bet_f))]
            run_command(
                cmd,
                cwd=work,
                log_path=paths["logs"] / f"fast_sub-{subject}.log",
            )

        expected = work / "fast_pve_0.nii.gz"
        if not expected.exists() or args.force:
            # FAST performs bias-field correction as part of segmentation.
            run_command(
                [
                    "fast",
                    "-t", "1",
                    "-n", str(n_classes),
                    "-B",
                    "-o", str(work / "fast"),
                    str(brain),
                ],
                cwd=work,
                log_path=paths["logs"] / f"fast_sub-{subject}.log",
            )

        for idx in range(n_classes):
            pve = work / f"fast_pve_{idx}.nii.gz"
            if not pve.exists():
                raise FileNotFoundError(pve)

    print("FAST segmentation completed.")


if __name__ == "__main__":
    main()
