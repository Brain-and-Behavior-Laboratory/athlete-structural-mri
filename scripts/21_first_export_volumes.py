from __future__ import annotations

import argparse
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd

from common import analysis_paths, file_voxel_sizes_mm3, load_config, read_participants


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = analysis_paths(cfg)
    participants = read_participants(paths)
    labels = {str(k): int(v) for k, v in cfg["first"]["structures"].items()}

    seg_root = paths["first_work"] / "segmentation"
    rows = []
    for _, participant in participants.iterrows():
        subject = str(participant["subject"])
        seg = seg_root / f"sub-{subject}_all_fast_firstseg.nii.gz"
        if not seg.exists():
            raise FileNotFoundError(seg)

        img = nib.load(str(seg))
        data = np.asarray(img.dataobj)
        voxel_mm3 = file_voxel_sizes_mm3(img)

        row = {"subject": subject, "group": participant["group"]}
        for structure, label in labels.items():
            row[f"{structure}_mm3"] = float(np.count_nonzero(data == label) * voxel_mm3)
        rows.append(row)

    out = pd.DataFrame(rows)
    out_path = paths["first_csv"] / "first_participant_volumes.csv"
    out.to_csv(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
