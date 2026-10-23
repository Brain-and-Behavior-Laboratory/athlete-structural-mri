from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

from common import (
    analysis_paths,
    load_config,
    read_participants,
    require_commands,
    run_command,
    save_json,
    subject_sort_key,
    write_first_vertex_design,
)


COMPARISONS = [
    ("football_vs_control", "AmericanFootball", "Control"),
    ("runner_vs_control", "CrossCountry", "Control"),
    ("football_vs_runner", "AmericanFootball", "CrossCountry"),
]


def find_bvars(seg_root: Path, subject: str, structure: str) -> Path:
    preferred = seg_root / f"sub-{subject}-{structure}_first.bvars"
    if preferred.exists():
        return preferred
    matches = sorted(seg_root.glob(f"sub-{subject}*{structure}*first.bvars"))
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FileNotFoundError(
            f"No FIRST .bvars found for subject={subject}, structure={structure}"
        )
    raise RuntimeError(
        f"Multiple FIRST .bvars candidates for subject={subject}, structure={structure}: "
        + ", ".join(str(p) for p in matches)
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = analysis_paths(cfg)
    participants = read_participants(paths)
    require_commands(["concat_bvars", "first_utils"])

    seg_root = paths["first_work"] / "segmentation"
    vertex_root = paths["first_work"] / "vertex"
    structures = list(cfg["first"]["structures"].keys())

    for comp_name, group_a, group_b in COMPARISONS:
        a = participants.loc[participants["group"] == group_a].copy()
        b = participants.loc[participants["group"] == group_b].copy()
        a = a.sort_values("subject", key=lambda s: s.map(subject_sort_key))
        b = b.sort_values("subject", key=lambda s: s.map(subject_sort_key))
        order = pd.concat([a, b], ignore_index=True)

        for structure in structures:
            work = vertex_root / comp_name / structure
            if args.force and work.exists():
                shutil.rmtree(work)
            work.mkdir(parents=True, exist_ok=True)

            order[["subject", "group"]].to_csv(work / "analysis_order.csv", index=False)
            write_first_vertex_design(
                len(a), len(b), group_a=group_a, group_b=group_b, out_dir=work
            )
            save_json(
                {
                    "comparison": comp_name,
                    "group_a": group_a,
                    "group_b": group_b,
                    "structure": structure,
                    "n_a": len(a),
                    "n_b": len(b),
                    "tstat1": f"{group_a}>{group_b}",
                    "tstat2": f"{group_b}>{group_a}",
                },
                work / "analysis.json",
            )

            bvars = [find_bvars(seg_root, str(s), structure) for s in order["subject"]]
            combined = work / "combined.bvars"
            if not combined.exists() or args.force:
                run_command(
                    ["concat_bvars", str(combined)] + [str(p) for p in bvars],
                    cwd=seg_root,
                    log_path=paths["logs"] / f"first_vertex_prepare_{comp_name}_{structure}.log",
                )

            output_base = work / "vertex"
            expected = work / "vertex.nii.gz"
            if not expected.exists() or args.force:
                run_command(
                    [
                        "first_utils",
                        "--vertexAnalysis",
                        "--usebvars",
                        "-i", str(combined),
                        "-o", str(output_base),
                        "-d", str(work / "design.mat"),
                        "--useReconMNI",
                        "--saveAverageMesh",
                    ],
                    cwd=seg_root,
                    log_path=paths["logs"] / f"first_vertex_prepare_{comp_name}_{structure}.log",
                )

            if not expected.exists():
                raise FileNotFoundError(
                    f"Expected first_utils output was not found: {expected}"
                )
            print(f"Prepared FIRST vertex analysis: {comp_name} / {structure}")


if __name__ == "__main__":
    main()
