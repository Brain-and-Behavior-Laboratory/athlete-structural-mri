from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

import pandas as pd

from common import (
    analysis_paths,
    load_config,
    save_json,
    subject_sort_key,
    write_two_group_dummy_design,
)


def place_input(src: Path, dst: Path, mode: str):
    if dst.exists():
        return
    if mode == "hardlink":
        os.link(src, dst)
    elif mode == "symlink":
        dst.symlink_to(src)
    else:
        shutil.copy2(src, dst)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = analysis_paths(cfg)
    copy_mode = str(cfg["vbm"].get("copy_mode", "copy")).lower()

    comparison_files = sorted(
        p for p in paths["vbm_comparisons"].glob("*.csv")
        if p.name != "comparison_summary.csv"
    )
    if not comparison_files:
        raise FileNotFoundError("No VBM comparison manifests were found.")

    for manifest in comparison_files:
        df = pd.read_csv(manifest)
        comparison = str(df["comparison"].iloc[0])
        group_a = str(df["group_a"].iloc[0])
        group_b = str(df["group_b"].iloc[0])
        work = paths["vbm_work"] / comparison

        if args.force and work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True, exist_ok=True)

        # Place files using the same subject-based naming convention that
        # determines FSL-VBM alphabetical concatenation order.
        order_rows = []
        for _, row in df.iterrows():
            subject = str(row["subject"])
            src = Path(row["t1_path"]).resolve()
            dst = work / f"sub-{subject}.nii.gz"
            place_input(src, dst, copy_mode)
            order_rows.append(
                {
                    "subject": subject,
                    "group": row["group"],
                    "filename": dst.name,
                }
            )

        order = pd.DataFrame(order_rows)
        order = order.sort_values("filename").reset_index(drop=True)
        order.to_csv(work / "analysis_order.csv", index=False)

        # Every participant entering a comparison contributes to its balanced
        # comparison-specific template.
        (work / "template_list").write_text(
            "\n".join(order["filename"].tolist()) + "\n",
            encoding="utf-8",
        )

        write_two_group_dummy_design(
            order["group"].tolist(),
            group_a=group_a,
            group_b=group_b,
            out_dir=work,
        )

        save_json(
            {
                "comparison": comparison,
                "group_a": group_a,
                "group_b": group_b,
                "n_a": int((order["group"] == group_a).sum()),
                "n_b": int((order["group"] == group_b).sum()),
                "tstat1": f"{group_a}>{group_b}",
                "tstat2": f"{group_b}>{group_a}",
            },
            work / "analysis.json",
        )
        print(f"Prepared {comparison}: {work}")


if __name__ == "__main__":
    main()
