from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yaml


def load_config(path: str | Path) -> dict:
    path = Path(path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}\n"
            "Copy config/config.example.yaml to config/config.yaml and edit it."
        )
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError("Configuration must contain a YAML mapping.")
    return cfg


def analysis_paths(cfg: dict) -> dict[str, Path]:
    root = Path(cfg["paths"]["analysis_root"]).expanduser().resolve()

    def configured_or_default(key: str, default: Path) -> Path:
        value = str(cfg.get("paths", {}).get(key, "") or "").strip()
        return Path(value).expanduser().resolve() if value else default.resolve()

    paths = {
        "root": root,
        "anat_t1w_root": configured_or_default(
            "anat_t1w_root", root / "downloads" / "anat_t1w"
        ),
        "freesurfer_root": configured_or_default(
            "freesurfer_root", root / "downloads" / "freesurfer"
        ),
        "data": root / "data",
        "selected_t1": root / "data" / "selected_t1",
        "metadata": root / "metadata",
        "vbm_comparisons": root / "metadata" / "vbm_comparisons",
        "work": root / "work",
        "vbm_work": root / "work" / "vbm",
        "first_work": root / "work" / "first",
        "fast_work": root / "work" / "fast",
        "csv": root / "csv",
        "vbm_csv": root / "csv" / "vbm",
        "first_csv": root / "csv" / "first",
        "fast_csv": root / "csv" / "fast",
        "logs": root / "logs",
    }
    root.mkdir(parents=True, exist_ok=True)
    for key, path in paths.items():
        if key == "root":
            continue
        # Download roots may point to an existing external directory. Creating
        # them is harmless and also supports the repository downloader.
        path.mkdir(parents=True, exist_ok=True)
    return paths


def run_command(
    cmd: list[str],
    cwd: str | Path | None = None,
    log_path: str | Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    cmd = [str(x) for x in cmd]
    if log_path is not None:
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write("\n$ " + " ".join(cmd) + "\n")
            result = subprocess.run(
                cmd,
                cwd=None if cwd is None else str(cwd),
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
    else:
        result = subprocess.run(
            cmd,
            cwd=None if cwd is None else str(cwd),
            text=True,
            check=False,
        )
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


def command_output(cmd: list[str], cwd: str | Path | None = None) -> str:
    result = subprocess.run(
        [str(x) for x in cmd],
        cwd=None if cwd is None else str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result.stdout


def require_commands(commands: Iterable[str]) -> None:
    missing = [c for c in commands if shutil.which(c) is None]
    if missing:
        raise RuntimeError(
            "Required command(s) not found on PATH: " + ", ".join(missing)
        )


def infer_group(subject: str, cfg: dict) -> str:
    subject = str(subject)
    for prefix, group in cfg["groups"]["prefixes"].items():
        if subject.startswith(str(prefix)):
            return str(group)
    raise ValueError(f"Could not infer group for subject '{subject}'.")


def subject_sort_key(subject: str):
    text = str(subject)
    parts = text.replace("sub-", "").split("_")
    key = []
    for part in parts:
        try:
            key.append((0, int(part)))
        except ValueError:
            key.append((1, part))
    return tuple(key)


def normalize_subject(subject: str) -> str:
    subject = str(subject).strip()
    if subject.startswith("sub-"):
        subject = subject[4:]
    return subject


def save_json(obj, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def load_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fsl_mat_text(matrix: np.ndarray) -> str:
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix[:, None]
    pp = np.max(np.abs(matrix), axis=0)
    pp[pp == 0] = 1
    lines = [
        f"/NumWaves\t{matrix.shape[1]}",
        f"/NumPoints\t{matrix.shape[0]}",
        "/PPheights\t" + "\t".join(f"{x:g}" for x in pp),
        "/Matrix",
    ]
    lines.extend("\t".join(f"{x:.8g}" for x in row) for row in matrix)
    return "\n".join(lines) + "\n"


def fsl_con_text(
    contrasts: np.ndarray,
    names: list[str] | None = None,
) -> str:
    contrasts = np.asarray(contrasts, dtype=float)
    if contrasts.ndim == 1:
        contrasts = contrasts[None, :]
    pp = np.max(np.abs(contrasts), axis=1)
    pp[pp == 0] = 1
    req = np.ones(contrasts.shape[0], dtype=float)
    lines = []
    if names:
        for i, name in enumerate(names, 1):
            lines.append(f"/ContrastName{i}\t{name}")
    lines.extend(
        [
            f"/NumWaves\t{contrasts.shape[1]}",
            f"/NumContrasts\t{contrasts.shape[0]}",
            "/PPheights\t" + "\t".join(f"{x:g}" for x in pp),
            "/RequiredEffect\t" + "\t".join(f"{x:g}" for x in req),
            "/Matrix",
        ]
    )
    lines.extend("\t".join(f"{x:.8g}" for x in row) for row in contrasts)
    return "\n".join(lines) + "\n"


def fsl_fts_text(matrix: np.ndarray) -> str:
    matrix = np.asarray(matrix, dtype=int)
    if matrix.ndim == 1:
        matrix = matrix[None, :]
    lines = [
        f"/NumWaves\t{matrix.shape[1]}",
        f"/NumContrasts\t{matrix.shape[0]}",
        "/Matrix",
    ]
    lines.extend("\t".join(str(int(x)) for x in row) for row in matrix)
    return "\n".join(lines) + "\n"


def write_two_group_dummy_design(
    groups: list[str],
    group_a: str,
    group_b: str,
    out_dir: str | Path,
) -> None:
    out_dir = Path(out_dir)
    matrix = []
    for group in groups:
        if group == group_a:
            matrix.append([1, 0])
        elif group == group_b:
            matrix.append([0, 1])
        else:
            raise ValueError(f"Unexpected group '{group}' in two-group design.")
    matrix = np.asarray(matrix, dtype=float)
    contrasts = np.asarray([[1, -1], [-1, 1]], dtype=float)
    (out_dir / "design.mat").write_text(fsl_mat_text(matrix), encoding="utf-8")
    (out_dir / "design.con").write_text(
        fsl_con_text(
            contrasts,
            names=[f"{group_a}>{group_b}", f"{group_b}>{group_a}"],
        ),
        encoding="utf-8",
    )


def write_first_vertex_design(
    n_a: int,
    n_b: int,
    group_a: str,
    group_b: str,
    out_dir: str | Path,
) -> None:
    out_dir = Path(out_dir)
    # A = +1, B = -1 so tstat1 is A>B and tstat2 is B>A.
    matrix = np.r_[np.ones(n_a), -np.ones(n_b)][:, None]
    contrasts = np.asarray([[1], [-1]], dtype=float)
    (out_dir / "design.mat").write_text(fsl_mat_text(matrix), encoding="utf-8")
    (out_dir / "design.con").write_text(
        fsl_con_text(
            contrasts,
            names=[f"{group_a}>{group_b}", f"{group_b}>{group_a}"],
        ),
        encoding="utf-8",
    )
    # The two-group omnibus F test is equivalent to t^2.  Select the first
    # directional t contrast to define the F contrast.
    (out_dir / "design.fts").write_text(
        fsl_fts_text(np.asarray([[1, 0]], dtype=int)),
        encoding="utf-8",
    )


def welch_ttest(x, y):
    from scipy import stats

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    nx, ny = len(x), len(y)
    mx, my = x.mean(), y.mean()
    vx, vy = x.var(ddof=1), y.var(ddof=1)
    se2 = vx / nx + vy / ny
    se = math.sqrt(se2)
    t = (mx - my) / se
    df = se2**2 / ((vx / nx) ** 2 / (nx - 1) + (vy / ny) ** 2 / (ny - 1))
    p = 2 * stats.t.sf(abs(t), df)
    crit = stats.t.ppf(0.975, df)
    diff = mx - my
    return {
        "mean_difference": diff,
        "se": se,
        "t": t,
        "df": df,
        "p": p,
        "ci_low": diff - crit * se,
        "ci_high": diff + crit * se,
    }


def welch_anova(groups):
    from scipy import stats

    arrays = [np.asarray(g, dtype=float) for g in groups]
    k = len(arrays)
    n = np.array([len(g) for g in arrays], dtype=float)
    means = np.array([g.mean() for g in arrays], dtype=float)
    variances = np.array([g.var(ddof=1) for g in arrays], dtype=float)
    weights = n / variances
    w_sum = weights.sum()
    weighted_mean = (weights * means).sum() / w_sum
    numerator = (weights * (means - weighted_mean) ** 2).sum() / (k - 1)
    term = (((1 - weights / w_sum) ** 2) / (n - 1)).sum()
    correction = 1 + 2 * (k - 2) / (k**2 - 1) * term
    f = numerator / correction
    df1 = k - 1
    df2 = (k**2 - 1) / (3 * term)
    p = stats.f.sf(f, df1, df2)
    return {"F": float(f), "df1": float(df1), "df2": float(df2), "p": float(p)}


def effect_sizes(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    nx, ny = len(x), len(y)
    vx, vy = x.var(ddof=1), y.var(ddof=1)
    pooled = math.sqrt(((nx - 1) * vx + (ny - 1) * vy) / (nx + ny - 2))
    d = (x.mean() - y.mean()) / pooled
    j = 1 - 3 / (4 * (nx + ny) - 9)
    g = j * d

    # Conventional approximate variance/CI for standardized mean difference.
    var_g = (nx + ny) / (nx * ny) + (g**2) / (2 * (nx + ny - 2))
    se_g = math.sqrt(var_g)
    return {
        "cohen_d": d,
        "hedges_g": g,
        "g_ci_low": g - 1.96 * se_g,
        "g_ci_high": g + 1.96 * se_g,
    }


def read_participants(paths: dict[str, Path]) -> pd.DataFrame:
    path = paths["metadata"] / "participants.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Participant manifest not found: {path}. Run 01_prepare_dataset.py first."
        )
    df = pd.read_csv(path)
    return df


def file_voxel_sizes_mm3(img) -> float:
    zooms = img.header.get_zooms()[:3]
    return float(np.prod(zooms))


def voxel_to_world(affine: np.ndarray, ijk) -> tuple[float, float, float]:
    ijk = np.asarray(ijk, dtype=float)
    xyz = affine @ np.r_[ijk, 1.0]
    return tuple(float(x) for x in xyz[:3])
