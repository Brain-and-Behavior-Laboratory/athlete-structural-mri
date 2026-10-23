from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests

from common import analysis_paths, load_config


OUTCOMES = {
    "CSF_cm3": "Cerebrospinal fluid volume",
    "GM_cm3": "Gray matter volume",
    "WM_cm3": "White matter volume",
    "Total_segmented_cm3": "Total segmented volume",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = analysis_paths(cfg)
    alpha = float(cfg["statistics"]["fdr_alpha"])

    fast = pd.read_csv(paths["fast_csv"] / "fast_participant_volumes.csv")
    etiv = pd.read_csv(paths["fast_csv"] / "participant_etiv.csv")
    df = fast.merge(etiv[["subject", "eTIV_mm3", "eTIV_cm3"]], on="subject", how="inner")
    if len(df) != len(fast):
        raise RuntimeError("FAST and eTIV files did not match one-to-one.")

    df["Group"] = pd.Categorical(
        df["group"],
        categories=["Control", "AmericanFootball", "CrossCountry"],
        ordered=True,
    )
    mean_tiv = float(df["eTIV_cm3"].mean())
    df["eTIV_centered_cm3"] = df["eTIV_cm3"] - mean_tiv

    # Correlations
    corr_rows = []
    for outcome, label in OUTCOMES.items():
        r, p = stats.pearsonr(df["eTIV_cm3"], df[outcome])
        corr_rows.append(
            {"measure": label, "pearson_r_with_eTIV": float(r), "p_value": float(p)}
        )
    pd.DataFrame(corr_rows).to_csv(
        paths["fast_csv"] / "fast_etiv_correlations.csv", index=False
    )

    # Group-by-eTIV interaction diagnostics
    interaction_rows = []
    for outcome, label in OUTCOMES.items():
        model = smf.ols(
            f"{outcome} ~ C(Group, Treatment(reference='Control')) * eTIV_centered_cm3",
            data=df,
        ).fit(cov_type="HC3", use_t=True)

        names = list(model.params.index)
        terms = [name for name in names if ":" in name]
        R = np.zeros((len(terms), len(names)))
        for i, term in enumerate(terms):
            R[i, names.index(term)] = 1.0
        test = model.wald_test(R, use_f=True, scalar=True)

        interaction_rows.append(
            {
                "measure": label,
                "F": float(test.statistic),
                "df_num": float(test.df_num),
                "df_den": float(test.df_denom),
                "p_value": float(test.pvalue),
            }
        )

    interactions = pd.DataFrame(interaction_rows)
    interactions["fdr_q"] = multipletests(
        interactions["p_value"], alpha=alpha, method="fdr_bh"
    )[1]
    interactions.to_csv(
        paths["fast_csv"] / "fast_etiv_interactions.csv", index=False
    )

    omnibus_rows = []
    adjusted_mean_rows = []
    pairwise_rows = []
    coefficient_rows = []

    for outcome, label in OUTCOMES.items():
        model = smf.ols(
            f"{outcome} ~ C(Group, Treatment(reference='Control')) + eTIV_centered_cm3",
            data=df,
        ).fit(cov_type="HC3", use_t=True)

        names = list(model.params.index)
        group_terms = [name for name in names if name.startswith("C(Group")]
        R = np.zeros((len(group_terms), len(names)))
        for i, term in enumerate(group_terms):
            R[i, names.index(term)] = 1.0
        test = model.wald_test(R, use_f=True, scalar=True)

        omnibus_rows.append(
            {
                "measure": label,
                "column": outcome,
                "F": float(test.statistic),
                "df_num": float(test.df_num),
                "df_den": float(test.df_denom),
                "p_value": float(test.pvalue),
            }
        )

        vectors = {}
        for group in ["Control", "AmericanFootball", "CrossCountry"]:
            vector = np.zeros(len(names))
            vector[names.index("Intercept")] = 1.0
            if group != "Control":
                term = f"C(Group, Treatment(reference='Control'))[T.{group}]"
                vector[names.index(term)] = 1.0
            vectors[group] = vector

            estimate = model.t_test(vector)
            ci = np.asarray(estimate.conf_int()).squeeze()
            adjusted_mean_rows.append(
                {
                    "measure": label,
                    "group": group,
                    "reference_eTIV_cm3": mean_tiv,
                    "adjusted_mean_cm3": float(np.asarray(estimate.effect).squeeze()),
                    "robust_SE_HC3": float(np.asarray(estimate.sd).squeeze()),
                    "df": float(model.df_resid),
                    "CI95_low": float(ci[0]),
                    "CI95_high": float(ci[1]),
                }
            )

        for group_a, group_b in [
            ("AmericanFootball", "Control"),
            ("CrossCountry", "Control"),
            ("AmericanFootball", "CrossCountry"),
        ]:
            estimate = model.t_test(vectors[group_a] - vectors[group_b])
            ci = np.asarray(estimate.conf_int()).squeeze()
            pairwise_rows.append(
                {
                    "measure": label,
                    "group_a": group_a,
                    "group_b": group_b,
                    "contrast": f"{group_a} - {group_b}",
                    "reference_eTIV_cm3": mean_tiv,
                    "adjusted_mean_difference_cm3": float(
                        np.asarray(estimate.effect).squeeze()
                    ),
                    "robust_SE_HC3": float(np.asarray(estimate.sd).squeeze()),
                    "t": float(np.asarray(estimate.tvalue).squeeze()),
                    "df": float(model.df_resid),
                    "p_value": float(np.asarray(estimate.pvalue).squeeze()),
                    "CI95_low": float(ci[0]),
                    "CI95_high": float(ci[1]),
                }
            )

        ci = model.conf_int()
        for term in names:
            coefficient_rows.append(
                {
                    "measure": label,
                    "term": term,
                    "estimate": float(model.params[term]),
                    "robust_SE_HC3": float(model.bse[term]),
                    "t": float(model.tvalues[term]),
                    "df": float(model.df_resid),
                    "p_value": float(model.pvalues[term]),
                    "CI95_low": float(ci.loc[term, 0]),
                    "CI95_high": float(ci.loc[term, 1]),
                }
            )

    omnibus = pd.DataFrame(omnibus_rows)
    omnibus["fdr_q"] = multipletests(
        omnibus["p_value"], alpha=alpha, method="fdr_bh"
    )[1]
    omnibus["fdr_significant"] = omnibus["fdr_q"] < alpha
    omnibus.to_csv(paths["fast_csv"] / "fast_etiv_omnibus.csv", index=False)

    pd.DataFrame(adjusted_mean_rows).to_csv(
        paths["fast_csv"] / "fast_etiv_adjusted_means.csv", index=False
    )

    pairwise = pd.DataFrame(pairwise_rows)
    pairwise["fdr_q"] = multipletests(
        pairwise["p_value"], alpha=alpha, method="fdr_bh"
    )[1]
    pairwise["fdr_significant"] = pairwise["fdr_q"] < alpha
    pairwise.to_csv(paths["fast_csv"] / "fast_etiv_pairwise.csv", index=False)

    pd.DataFrame(coefficient_rows).to_csv(
        paths["fast_csv"] / "fast_etiv_model_coefficients.csv", index=False
    )

    print(f"Grand mean eTIV: {mean_tiv:.6f} cm3")
    print("Wrote eTIV-adjusted FAST CSV outputs.")


if __name__ == "__main__":
    main()
