from __future__ import annotations

import argparse

import nibabel as nib
import numpy as np
import pandas as pd

from common import analysis_paths, file_voxel_sizes_mm3, load_config, read_participants


def volume_mm3(path):
    img = nib.load(str(path))
    data = np.asarray(img.dataobj, dtype=float)
    return float(data.sum() * file_voxel_sizes_mm3(img))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = analysis_paths(cfg)
    participants = read_participants(paths)
    pve = {k: int(v) for k, v in cfg["fast"]["pve_index"].items()}

    rows = []
    for _, participant in participants.iterrows():
        subject = str(participant["subject"])
        work = paths["fast_work"] / f"sub-{subject}"

        vols_mm3 = {}
        for tissue in ["CSF", "GM", "WM"]:
            path = work / f"fast_pve_{pve[tissue]}.nii.gz"
            if not path.exists():
                raise FileNotFoundError(path)
            vols_mm3[tissue] = volume_mm3(path)

        csf = vols_mm3["CSF"] / 1000.0
        gm = vols_mm3["GM"] / 1000.0
        wm = vols_mm3["WM"] / 1000.0
        total = csf + gm + wm

        rows.append(
            {
                "subject": subject,
                "group": participant["group"],
                "CSF_cm3": csf,
                "GM_cm3": gm,
                "WM_cm3": wm,
                "Total_segmented_cm3": total,
                "CSF_fraction": csf / total,
                "GM_fraction": gm / total,
                "WM_fraction": wm / total,
            }
        )

    out = pd.DataFrame(rows)
    out_path = paths["fast_csv"] / "fast_participant_volumes.csv"
    out.to_csv(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
