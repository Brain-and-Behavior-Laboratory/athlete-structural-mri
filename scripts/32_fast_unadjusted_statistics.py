from __future__ import annotations

import argparse

import pandas as pd
from statsmodels.stats.multitest import multipletests

from common import analysis_paths, effect_sizes, load_config, welch_anova, welch_ttest


OUTCOMES = [
    ("CSF_cm3", "Cerebrospinal fluid volume"),
    ("GM_cm3", "Gray matter volume"),
    ("WM_cm3", "White matter volume"),
    ("Total_segmented_cm3", "Total segmented volume"),
]

GROUPS = ["AmericanFootball", "CrossCountry", "Control"]

PAIRWISE = [
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
    df = pd.read_csv(paths["fast_csv"] / "fast_participant_volumes.csv")
    alpha = float(cfg["statistics"]["fdr_alpha"])

    omnibus_rows = []
    for col, label in OUTCOMES:
        arrays = [df.loc[df["group"] == g, col].to_numpy() for g in GROUPS]
        result = welch_anova(arrays)
        omnibus_rows.append({"measure": label, "column": col, **result})

    omnibus = pd.DataFrame(omnibus_rows)
    omnibus["fdr_q"] = multipletests(
        omnibus["p"], alpha=alpha, method="fdr_bh"
    )[1]
    omnibus["fdr_significant"] = omnibus["fdr_q"] < alpha
    omnibus.to_csv(paths["fast_csv"] / "fast_unadjusted_omnibus.csv", index=False)

    pair_rows = []
    for col, label in OUTCOMES:
        for group_a, group_b in PAIRWISE:
            x = df.loc[df["group"] == group_a, col].to_numpy()
            y = df.loc[df["group"] == group_b, col].to_numpy()
            pair_rows.append(
                {
                    "measure": label,
                    "column": col,
                    "group_a": group_a,
                    "group_b": group_b,
                    "contrast": f"{group_a} - {group_b}",
                    **welch_ttest(x, y),
                    **effect_sizes(x, y),
                }
            )

    pairwise = pd.DataFrame(pair_rows)
    pairwise["fdr_q"] = multipletests(
        pairwise["p"], alpha=alpha, method="fdr_bh"
    )[1]
    pairwise["fdr_significant"] = pairwise["fdr_q"] < alpha
    pairwise.to_csv(paths["fast_csv"] / "fast_unadjusted_pairwise.csv", index=False)

    print("Wrote FAST unadjusted omnibus and pairwise CSV files.")


if __name__ == "__main__":
    main()
