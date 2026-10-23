from __future__ import annotations

import argparse
from pathlib import Path

import nibabel as nib
import pandas as pd

from common import (
    analysis_paths,
    load_config,
    read_participants,
    require_commands,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = analysis_paths(cfg)
    participants = read_participants(paths)

    required_columns = {"subject", "group", "t1_path"}
    missing = required_columns - set(participants.columns)
    if missing:
        raise RuntimeError(f"participants.csv is missing columns: {sorted(missing)}")

    expected = cfg["groups"]["expected_counts"]
    counts = participants["group"].value_counts()
    for group, n in expected.items():
        actual = int(counts.get(group, 0))
        if actual != int(n):
            raise RuntimeError(f"{group}: expected {n}, found {actual}")

    seen = set()
    for _, row in participants.iterrows():
        subject = str(row["subject"])
        if subject in seen:
            raise RuntimeError(f"Duplicate participant: {subject}")
        seen.add(subject)

        t1 = Path(row["t1_path"])
        if not t1.exists():
            raise FileNotFoundError(f"Missing T1 for {subject}: {t1}")
        img = nib.load(str(t1))
        if len(img.shape) != 3:
            raise RuntimeError(f"T1 is not 3D for {subject}: shape={img.shape}")

    summary_path = paths["vbm_comparisons"] / "comparison_summary.csv"
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing VBM comparison summary: {summary_path}")
    summary = pd.read_csv(summary_path)

    expected_sizes = {
        "A_football_first9_vs_control": (9, 9),
        "B_football_last9_vs_control": (9, 9),
        "C_runner_first9_vs_control": (9, 9),
        "D_runner_last9_vs_control": (9, 9),
        "E_football16_vs_runner16": (16, 16),
    }
    for _, row in summary.iterrows():
        name = row["comparison"]
        if name in expected_sizes:
            wanted = expected_sizes[name]
            got = (int(row["n_a"]), int(row["n_b"]))
            if got != wanted:
                raise RuntimeError(f"{name}: expected {wanted}, found {got}")

    # Validate the intentional overlap of first/last athlete subsets.
    def subjects_from(name):
        df = pd.read_csv(paths["vbm_comparisons"] / f"{name}.csv")
        return set(df.loc[df["analysis_group"] == "A", "subject"].astype(str))

    football_overlap = len(
        subjects_from("A_football_first9_vs_control")
        & subjects_from("B_football_last9_vs_control")
    )
    runner_overlap = len(
        subjects_from("C_runner_first9_vs_control")
        & subjects_from("D_runner_last9_vs_control")
    )
    if football_overlap != 1:
        raise RuntimeError(f"Expected football subset overlap of 1, found {football_overlap}")
    if runner_overlap != 2:
        raise RuntimeError(f"Expected runner subset overlap of 2, found {runner_overlap}")

    require_commands(
        [
            "fslvbm_1_bet",
            "fslvbm_2_template",
            "fslvbm_3_proc",
            "randomise",
            "run_first_all",
            "concat_bvars",
            "first_utils",
            "bet",
            "fast",
        ]
    )

    n_aseg = 0
    if "aseg_stats_path" in participants:
        for p in participants["aseg_stats_path"].fillna(""):
            if p and Path(p).exists():
                n_aseg += 1

    print("Input validation passed.")
    print(f"Participants: {len(participants)}")
    print("Group counts:")
    for group, count in counts.items():
        print(f"  {group}: {count}")
    print(f"Available aseg.stats files in manifest: {n_aseg}/{len(participants)}")
    print("VBM subset overlap:")
    print(f"  football first/last nine overlap: {football_overlap}")
    print(f"  runner first/last nine overlap: {runner_overlap}")


if __name__ == "__main__":
    main()
