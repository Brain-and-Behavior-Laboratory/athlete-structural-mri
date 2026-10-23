#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:-config/config.yaml}"
MODE="${2:-existing-data}"

if [[ "${MODE}" == "--download" ]]; then
  python scripts/00_download_brainlife.py --config "${CONFIG}" --what anat
  # FreeSurfer is needed only when eTIV is to be extracted/verified from
  # aseg.stats. If a public participants_tiv.csv is supplied instead, this
  # download can be omitted by running the stages manually.
  python scripts/00_download_brainlife.py --config "${CONFIG}" --what freesurfer
fi

python scripts/01_prepare_dataset.py --config "${CONFIG}"
python scripts/02_check_inputs.py --config "${CONFIG}"

python scripts/10_vbm_prepare_comparisons.py --config "${CONFIG}"
python scripts/11_vbm_run_pipeline.py --config "${CONFIG}"
python scripts/12_vbm_run_randomise.py --config "${CONFIG}"
python scripts/13_vbm_export_clusters.py --config "${CONFIG}"

python scripts/20_first_run_segmentation.py --config "${CONFIG}"
python scripts/21_first_export_volumes.py --config "${CONFIG}"
python scripts/22_first_volume_statistics.py --config "${CONFIG}"
python scripts/23_first_prepare_vertex.py --config "${CONFIG}"
python scripts/24_first_run_vertex_randomise.py --config "${CONFIG}"
python scripts/25_first_export_vertex_results.py --config "${CONFIG}"

python scripts/30_fast_run_segmentation.py --config "${CONFIG}"
python scripts/31_fast_export_volumes.py --config "${CONFIG}"
python scripts/32_fast_unadjusted_statistics.py --config "${CONFIG}"
python scripts/33_extract_etiv.py --config "${CONFIG}"
python scripts/34_fast_etiv_adjusted_statistics.py --config "${CONFIG}"
