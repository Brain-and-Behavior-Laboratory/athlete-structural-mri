from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

import pandas as pd

from common import analysis_paths, infer_group, load_config, normalize_subject, subject_sort_key


def choose_nifti(object_dir: Path) -> Path:
    preferred = sorted(object_dir.rglob("t1.nii.gz"))
    if len(preferred) == 1:
        return preferred[0].resolve()
    candidates = sorted(object_dir.rglob("*.nii.gz")) + sorted(object_dir.rglob("*.nii"))
    candidates = sorted({p.resolve() for p in candidates})
    if len(candidates) != 1:
        raise RuntimeError(
            f"Expected exactly one native T1 NIfTI inside {object_dir}, found {len(candidates)}."
        )
    return candidates[0]


def discover_raw_t1(paths: dict, cfg: dict) -> pd.DataFrame:
    root = paths["anat_t1w_root"]
    regex = re.compile(cfg["brainlife"]["raw_t1_object_regex"])
    rows = []
    for subject_dir in sorted(root.glob("sub-*")):
        if not subject_dir.is_dir():
            continue
        subject = normalize_subject(subject_dir.name)
        try:
            group = infer_group(subject, cfg)
        except ValueError:
            continue
        raw_objects = [p for p in subject_dir.iterdir() if p.is_dir() and regex.match(p.name)]
        if len(raw_objects) != 1:
            raise RuntimeError(
                f"sub-{subject}: expected one untagged raw anat/t1w object matching "
                f"{regex.pattern!r}, found {len(raw_objects)}. Candidates: "
                + ", ".join(p.name for p in raw_objects)
            )
        t1 = choose_nifti(raw_objects[0])
        rows.append(
            {
                "subject": subject,
                "group": group,
                "raw_object_dir": str(raw_objects[0].resolve()),
                "source_t1_path": str(t1),
            }
        )
    if not rows:
        raise RuntimeError(
            f"No direct sub-* folders with raw anat/t1w objects were found under {root}."
        )
    return pd.DataFrame(rows)


def copy_or_link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    try:
        dst.symlink_to(src)
    except OSError:
        shutil.copy2(src, dst)


def find_aseg(paths: dict, subject: str) -> str:
    root = paths["freesurfer_root"] / f"sub-{subject}"
    if not root.exists():
        return ""
    matches = sorted(root.rglob("aseg.stats"))
    return str(matches[0].resolve()) if matches else ""


def write_vbm_comparisons(participants: pd.DataFrame, paths: dict, cfg: dict) -> None:
    n = int(cfg["vbm"]["first_last_n"])
    direct_n = int(cfg["vbm"]["direct_football_n"])
    by_group = {
        group: sorted(
            participants.loc[participants["group"] == group, "subject"].astype(str).tolist(),
            key=subject_sort_key,
        )
        for group in ["AmericanFootball", "CrossCountry", "Control"]
    }
    football, runners, controls = (
        by_group["AmericanFootball"],
        by_group["CrossCountry"],
        by_group["Control"],
    )
    specs = [
        ("A_football_first9_vs_control", "AmericanFootball", "Control", football[:n], controls),
        ("B_football_last9_vs_control", "AmericanFootball", "Control", football[-n:], controls),
        ("C_runner_first9_vs_control", "CrossCountry", "Control", runners[:n], controls),
        ("D_runner_last9_vs_control", "CrossCountry", "Control", runners[-n:], controls),
        ("E_football16_vs_runner16", "AmericanFootball", "CrossCountry", football[:direct_n], runners),
    ]
    indexed = participants.set_index("subject")
    summary = []
    for name, group_a, group_b, subjects_a, subjects_b in specs:
        records = []
        for analysis_group, subjects in [("A", subjects_a), ("B", subjects_b)]:
            for subject in subjects:
                row = indexed.loc[subject].to_dict()
                row.update(
                    {
                        "subject": subject,
                        "comparison": name,
                        "group_a": group_a,
                        "group_b": group_b,
                        "analysis_group": analysis_group,
                    }
                )
                records.append(row)
        out = pd.DataFrame(records)
        out.to_csv(paths["vbm_comparisons"] / f"{name}.csv", index=False)
        summary.append(
            {
                "comparison": name,
                "group_a": group_a,
                "group_b": group_b,
                "n_a": len(subjects_a),
                "n_b": len(subjects_b),
                "subjects_a": ";".join(subjects_a),
                "subjects_b": ";".join(subjects_b),
            }
        )
    pd.DataFrame(summary).to_csv(paths["vbm_comparisons"] / "comparison_summary.csv", index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()
    cfg = load_config(args.config)
    paths = analysis_paths(cfg)

    participants = discover_raw_t1(paths, cfg)
    participants = participants.sort_values("subject", key=lambda s: s.map(subject_sort_key)).reset_index(drop=True)

    expected = cfg["groups"]["expected_counts"]
    counts = participants["group"].value_counts().to_dict()
    for group, expected_n in expected.items():
        if int(counts.get(group, 0)) != int(expected_n):
            raise RuntimeError(f"Expected {expected_n} {group} participants; found {counts.get(group, 0)}.")

    rows = []
    for _, row in participants.iterrows():
        subject = str(row["subject"])
        selected = paths["selected_t1"] / f"sub-{subject}.nii.gz"
        copy_or_link(Path(row["source_t1_path"]), selected)
        rows.append(
            {
                **row.to_dict(),
                "t1_path": str(selected.resolve()),
                "aseg_stats_path": find_aseg(paths, subject),
            }
        )
    participants = pd.DataFrame(rows)
    participants.to_csv(paths["metadata"] / "participants.csv", index=False)
    write_vbm_comparisons(participants, paths, cfg)
    print(f"Selected {len(participants)} native T1 images from: {paths['anat_t1w_root']}")
    print(f"Participant manifest: {paths['metadata'] / 'participants.csv'}")
    print(f"VBM manifests: {paths['vbm_comparisons']}")


if __name__ == "__main__":
    main()
