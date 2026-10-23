from __future__ import annotations

import argparse

import pandas as pd
from statsmodels.stats.multitest import multipletests

from common import analysis_paths, effect_sizes, load_config, welch_ttest


COMPARISONS = [
    ("AmericanFootball", "Control"),
    ("CrossCountry", "Control"),
    ("AmericanFootball", "CrossCountry"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = analysis_paths(cfg)
    input_path = paths["first_csv"] / "first_participant_volumes.csv"
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    df = pd.read_csv(input_path)
    structures = list(cfg["first"]["structures"].keys())
    alpha = float(cfg["statistics"]["fdr_alpha"])

    rows = []
    for group_a, group_b in COMPARISONS:
        family_indices = []
        for structure in structures:
            col = f"{structure}_mm3"
            x = df.loc[df["group"] == group_a, col].to_numpy()
            y = df.loc[df["group"] == group_b, col].to_numpy()
            test = welch_ttest(x, y)
            eff = effect_sizes(x, y)
            row = {
                "group_a": group_a,
                "group_b": group_b,
                "contrast": f"{group_a} - {group_b}",
                "structure": structure,
                "n_a": len(x),
                "mean_a_mm3": x.mean(),
                "sd_a_mm3": x.std(ddof=1),
                "n_b": len(y),
                "mean_b_mm3": y.mean(),
                "sd_b_mm3": y.std(ddof=1),
                **test,
                **eff,
            }
            family_indices.append(len(rows))
            rows.append(row)

        pvals = [rows[i]["p"] for i in family_indices]
        qvals = multipletests(pvals, alpha=alpha, method="fdr_bh")[1]
        for i, q in zip(family_indices, qvals):
            rows[i]["fdr_q"] = float(q)
            rows[i]["fdr_significant"] = bool(q < alpha)

    out = pd.DataFrame(rows)
    out_path = paths["first_csv"] / "first_volume_statistics.csv"
    out.to_csv(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
