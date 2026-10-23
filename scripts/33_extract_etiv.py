from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

from common import analysis_paths, load_config, normalize_subject, read_participants


PATTERN = re.compile(
    r"^# Measure EstimatedTotalIntraCranialVol,\s*eTIV,\s*"
    r"Estimated Total Intracranial Volume,\s*([0-9.eE+-]+),\s*mm\^3\s*$"
)


def parse_etiv(path: Path) -> float:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = PATTERN.match(line.strip())
        if match:
            return float(match.group(1))
    raise ValueError(f"EstimatedTotalIntraCranialVol not found in {path}")


def load_public_table(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    normalized = {str(c).replace("\xa0", "").strip(): c for c in df.columns}
    subject_col = normalized.get("Subject") or normalized.get("subject")
    tiv_col = normalized.get("Total Intracranial Volume") or normalized.get("eTIV_mm3")
    if subject_col is None or tiv_col is None:
        raise RuntimeError(
            "participants_tiv.csv must contain 'Subject' and 'Total Intracranial Volume' "
            "columns (or 'subject' and 'eTIV_mm3')."
        )
    out = pd.DataFrame(
        {
            "subject": df[subject_col].map(normalize_subject).astype(str),
            "table_eTIV_mm3": pd.to_numeric(df[tiv_col], errors="raise"),
        }
    )
    return out


def find_stats_files(root: Path, subject: str) -> list[Path]:
    subject_root = root / f"sub-{subject}"
    if not subject_root.exists():
        return []
    return sorted({p.resolve() for p in subject_root.rglob("aseg.stats")})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument(
        "--table",
        default="",
        help=(
            "Optional public participant TIV CSV. If omitted, the script checks "
            "<analysis_root>/metadata/participants_tiv.csv."
        ),
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    paths = analysis_paths(cfg)
    participants = read_participants(paths)[["subject", "group"]].copy()
    participants["subject"] = participants["subject"].astype(str)

    table_path = Path(args.table).expanduser().resolve() if args.table else paths["metadata"] / "participants_tiv.csv"
    table = load_public_table(table_path) if table_path.exists() else None
    table_map = {} if table is None else dict(zip(table["subject"], table["table_eTIV_mm3"]))

    rows = []
    for _, row in participants.iterrows():
        subject = str(row["subject"])
        table_value = table_map.get(subject, np.nan)

        stats_files = find_stats_files(paths["freesurfer_root"], subject)
        fs_values = [(p, parse_etiv(p)) for p in stats_files]
        unique_fs = sorted({round(v, 6) for _, v in fs_values})
        if len(unique_fs) > 1:
            detail = "; ".join(f"{p}={v}" for p, v in fs_values)
            raise RuntimeError(f"Conflicting FreeSurfer eTIV values for sub-{subject}: {detail}")
        fs_value = fs_values[0][1] if fs_values else np.nan

        if np.isnan(table_value) and np.isnan(fs_value):
            raise RuntimeError(
                f"No eTIV value found for sub-{subject}. Provide metadata/participants_tiv.csv "
                "or download the public FreeSurfer object for this participant."
            )

        if not np.isnan(table_value) and not np.isnan(fs_value):
            # Public participant-table values were rounded to three decimal places.
            verified = bool(np.isclose(round(fs_value, 3), round(table_value, 3), atol=0.001))
            if not verified:
                raise RuntimeError(
                    f"eTIV mismatch for sub-{subject}: table={table_value}, FreeSurfer={fs_value}"
                )
            etiv = fs_value
            source = "FreeSurfer aseg.stats (public table verified)"
        elif not np.isnan(fs_value):
            verified = False
            etiv = fs_value
            source = "FreeSurfer aseg.stats"
        else:
            verified = False
            etiv = float(table_value)
            source = "public participant TIV table"

        rows.append(
            {
                "subject": subject,
                "group": row["group"],
                "eTIV_mm3": float(etiv),
                "eTIV_cm3": float(etiv) / 1000.0,
                "source": source,
                "table_value_available": not np.isnan(table_value),
                "aseg_stats_available": not np.isnan(fs_value),
                "table_matches_aseg_to_3dp": verified,
                "aseg_stats_path": str(fs_values[0][0]) if fs_values else "",
            }
        )

    out = pd.DataFrame(rows)
    out_path = paths["fast_csv"] / "participant_etiv.csv"
    out.to_csv(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
