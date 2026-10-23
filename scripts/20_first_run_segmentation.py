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
    require_commands(["run_first_all"])

    seg_root = paths["first_work"] / "segmentation"
    seg_root.mkdir(parents=True, exist_ok=True)

    for _, row in participants.iterrows():
        subject = str(row["subject"])
        src = Path(row["t1_path"]).resolve()
        local_t1 = seg_root / f"sub-{subject}.nii.gz"
        if not local_t1.exists():
            shutil.copy2(src, local_t1)

        output_base = f"sub-{subject}"
        expected = seg_root / f"{output_base}_all_fast_firstseg.nii.gz"
        if expected.exists() and not args.force:
            print(f"skip existing FIRST: {subject}")
            continue

        log = paths["logs"] / f"first_segmentation_sub-{subject}.log"
        print(f"FIRST: {subject}")
        # Run from the common FIRST directory using relative paths so the
        # .bvars files contain portable relative references to the T1 images.
        run_command(
            ["run_first_all", "-i", local_t1.name, "-o", output_base],
            cwd=seg_root,
            log_path=log,
        )

        if not expected.exists():
            raise FileNotFoundError(
                f"FIRST did not produce expected segmentation for {subject}: {expected}"
            )

    print("FIRST segmentation completed. Visually inspect registrations and segmentations before statistics.")


if __name__ == "__main__":
    main()
