# Structural MRI analysis of collegiate athletes

This repository provides the Python scripts and FSL-based analysis workflow associated with the following research study:

Arunim Guchait, Chiao-Yun Chen, and Neil G. Muggleton. **Multiscale structural MRI differences among collegiate American football players, cross-country runners, and non-athletes.** *bioRxiv*, 2026. [https://doi.org/10.64898/2026.10.01.756138](https://doi.org/10.64898/2026.10.01.756138).

The workflow examines structural brain differences among collegiate American football players, cross-country runners, and non-athletes using the publicly available brainlife.io dataset. It combines voxel-based morphometry (FSL-VBM), subcortical segmentation and vertex-wise shape analysis (FIRST), tissue segmentation (FAST), and sensitivity analyses adjusting for estimated total intracranial volume (eTIV).

The repository includes scripts for preparing the input data, performing the analyses, and exporting numerical results. The underlying MRI dataset is obtained separately from its public source.

## Source dataset

Caron, B., Stuck, R., McPherson, B., et al. (2021). Collegiate athlete brain data for white matter mapping and network neuroscience. *Scientific Data, 8*, 56. https://doi.org/10.1038/s41597-021-00823-z

Public dataset DOI: https://doi.org/10.25663/brainlife.pub.14

The workflow covers the analysis from public-data acquisition through numerical computation and CSV export:

1. native T1w input selection from the downloaded `anat/t1w` datatype;
2. five balanced FSL-VBM comparisons with comparison-specific templates;
3. FIRST segmentation and total-volume analysis;
4. FIRST structure-specific vertex-wise analysis;
5. FAST three-class tissue segmentation and unadjusted statistics;
6. FreeSurfer eTIV extraction/verification and eTIV-adjusted FAST sensitivity analysis.

## Repository contents

```text
structural-mri-athletes/
├── README.md
├── LICENSE
├── .gitignore
├── environment.yml
├── config/
│   ├── config.example.yaml
│   └── participants_tiv.example.csv
└── scripts/
    ├── common.py
    ├── 00_download_brainlife.py
    ├── 01_prepare_dataset.py
    ├── 02_check_inputs.py
    ├── 10_vbm_prepare_comparisons.py
    ├── 11_vbm_run_pipeline.py
    ├── 12_vbm_run_randomise.py
    ├── 13_vbm_export_clusters.py
    ├── 20_first_run_segmentation.py
    ├── 21_first_export_volumes.py
    ├── 22_first_volume_statistics.py
    ├── 23_first_prepare_vertex.py
    ├── 24_first_run_vertex_randomise.py
    ├── 25_first_export_vertex_results.py
    ├── 30_fast_run_segmentation.py
    ├── 31_fast_export_volumes.py
    ├── 32_fast_unadjusted_statistics.py
    ├── 33_extract_etiv.py
    ├── 34_fast_etiv_adjusted_statistics.py
    └── 90_run_all.sh
```


## Software requirements

The workflow requires:

- FSL with `fslvbm`, `randomise`, FIRST, FAST, BET, and `fsl-cluster`;
- Python 3 with the packages listed in `environment.yml`;
- brainlife CLI only if data are downloaded from the command line.

Official documentation:

- FSL installation: `https://fsl.fmrib.ox.ac.uk/fsl/docs/install/index.html`
- FSL-VBM: `https://fsl.fmrib.ox.ac.uk/fsl/docs/structural/fslvbm.html`
- FIRST: `https://fsl.fmrib.ox.ac.uk/fsl/docs/structural/first.html`
- FAST: `https://fsl.fmrib.ox.ac.uk/fsl/docs/structural/fast.html`
- randomise: `https://fsl.fmrib.ox.ac.uk/fsl/docs/statistics/randomise.html`
- brainlife CLI download: `https://brainlife.io/docs/cli/download/`

On Windows, run the FSL portions from a supported FSL environment such as Windows Subsystem for Linux. Paths in `config/config.yaml` must be paths visible from the environment in which the scripts are executed.

## Reference computational environment

The analyses for this study were executed on a Linux workstation with the following configuration:

```text
Operating system: Ubuntu 24.04.4 LTS
Processor:        11th Gen Intel® Core™ i7-11800H × 16
Memory:           64.0 GiB
```

These specifications document the reference computational environment used for the study. They are not intended as minimum hardware requirements for running the workflow. Execution time and resource requirements may differ on other systems.

## Python environment

Create the Python environment with:

```bash
conda env create -f environment.yml
conda activate athlete-structural-mri
```

FSL is treated as an external dependency and is not installed by `environment.yml`.

## Configuration

Copy the example configuration:

```bash
cp config/config.example.yaml config/config.yaml
```

Edit only the local paths:

```yaml
paths:
  analysis_root: "/path/to/analysis"
  anat_t1w_root: "/path/to/downloaded/anat_t1w"
  freesurfer_root: "/path/to/downloaded/freesurfer"
```

`config/config.yaml` is ignored by Git.

## Input layout: downloaded `anat/t1w`

The scripts are designed for the folder layout produced when the public `anat/t1w` datatype is downloaded from brainlife.io. Only the direct `sub-*` folders are used; the duplicated BIDS derivative folders are ignored.

The expected pattern is:

```text
<ANAT_T1W_ROOT>/
├── bids/
│   └── derivatives/
│       └── ...
├── sub-1_001/
│   ├── dt-neuro-anat-t1w.id-<OBJECT_ID>/
│   ├── dt-neuro-anat-t1w.tag-preprocessed.tag-acpc_aligned.id-<OBJECT_ID>/
│   └── dt-neuro-anat-t1w.tag-preprocessed.tag-standard.id-<OBJECT_ID>/
├── sub-1_002/
│   └── ...
├── sub-2_023/
│   └── ...
└── sub-3_055/
    └── ...
```

The native T1 input for this workflow is selected from the **untagged** object directory:

```text
dt-neuro-anat-t1w.id-<OBJECT_ID>
```

Directories containing `.tag-preprocessed` are not selected as the native input.

`01_prepare_dataset.py` requires exactly one untagged raw anatomical object per participant and exactly one native T1 NIfTI inside that object. 

## Option A: use an existing brainlife download

If the `anat/t1w` folder has already been downloaded, set:

```yaml
paths:
  anat_t1w_root: "/path/to/downloaded/anat_t1w"
```

Then start with:

```bash
python scripts/01_prepare_dataset.py --config config/config.yaml
python scripts/02_check_inputs.py --config config/config.yaml
```

## Option B: download with the brainlife CLI

Install the brainlife CLI and authenticate with `bl login` first.

Inspect the anatomical objects without downloading:

```bash
python scripts/00_download_brainlife.py \
  --config config/config.yaml \
  --what anat \
  --dry-run
```

Download all public anatomical T1w objects:

```bash
python scripts/00_download_brainlife.py \
  --config config/config.yaml \
  --what anat
```

If `paths.anat_t1w_root` is blank, the default destination is:

```text
<ANALYSIS_ROOT>/downloads/anat_t1w/
```

The downloader writes one data-object directory per brainlife object and preserves subject/object separation.

## Participant groups

Group membership is derived from the public participant identifiers:

```text
1_* -> American football players
2_* -> cross-country runners
3_* -> non-athletes
```

The scripts require the released sample to contain:

```text
American football: 17
Cross-country:     16
Non-athlete:       9
Total:             42
```

## Local analysis directory

The scripts create the following structure outside the repository:

```text
<ANALYSIS_ROOT>/
├── data/
│   └── selected_t1/
├── metadata/
│   ├── participants.csv
│   ├── participants_tiv.csv          # optional local public table
│   └── vbm_comparisons/
├── work/
│   ├── vbm/
│   ├── first/
│   └── fast/
├── csv/
│   ├── vbm/
│   ├── first/
│   └── fast/
└── logs/
```

## 1. Prepare and validate the dataset

```bash
python scripts/01_prepare_dataset.py --config config/config.yaml
python scripts/02_check_inputs.py --config config/config.yaml
```

The participant preparation stage selects the native T1 images and creates the exact balanced VBM comparison manifests.

### VBM comparisons

The five comparisons are generated from the ordered public participant identifiers:

```text
A_football_first9_vs_control
B_football_last9_vs_control
C_runner_first9_vs_control
D_runner_last9_vs_control
E_football16_vs_runner16
```

The exact participant selection is:

```text
A: first 9 football + all 9 non-athletes
B: last 9 football  + all 9 non-athletes
C: first 9 runners  + all 9 non-athletes
D: last 9 runners   + all 9 non-athletes
E: first 16 football + all 16 runners
```

Because there are 17 football players, the first-nine and last-nine football subsets overlap by one participant. Because there are 16 runners, the first-nine and last-nine runner subsets overlap by two participants.

Each VBM comparison receives its own balanced `template_list` containing the participants entering that comparison.

## 2. FSL-VBM

Prepare the five VBM working directories:

```bash
python scripts/10_vbm_prepare_comparisons.py --config config/config.yaml
```

Run the FSL-VBM stages:

```bash
python scripts/11_vbm_run_pipeline.py --config config/config.yaml --stage bet
python scripts/11_vbm_run_pipeline.py --config config/config.yaml --stage template
python scripts/11_vbm_run_pipeline.py --config config/config.yaml --stage proc
```

The configured pipeline uses:

```text
fslvbm_1_bet -b
fslvbm_2_template -n
fslvbm_3_proc
```

The final VBM inferential input is:

```text
GM_mod_merg_s3
```

which corresponds to Gaussian smoothing with sigma = 3 mm.

Run permutation inference:

```bash
python scripts/12_vbm_run_randomise.py --config config/config.yaml
```

The default configuration uses 5,000 permutations and TFCE.

Export corrected clusters:

```bash
python scripts/13_vbm_export_clusters.py --config config/config.yaml
```

Output:

```text
<ANALYSIS_ROOT>/csv/vbm/vbm_clusters.csv
```

The cluster exporter uses FSL `fsl-cluster` with 26-voxel connectivity on corrected `1-p` images and includes associated t-statistic maxima and means.

The TFCE/FWE correction is spatial within each directional VBM contrast. 

## 3. FIRST segmentation and total volumes

Run FIRST on the 42 native T1 images:

```bash
python scripts/20_first_run_segmentation.py --config config/config.yaml
```

The scripts use `run_first_all` and retain all 15 structures:

```text
L/R nucleus accumbens
L/R amygdala
L/R caudate
L/R hippocampus
L/R pallidum
L/R putamen
L/R thalamus
brainstem
```

Inspect FIRST registration and segmentation quality before quantitative analysis.

Export participant-level volumes:

```bash
python scripts/21_first_export_volumes.py --config config/config.yaml
```

Run the three pairwise Welch analyses:

```bash
python scripts/22_first_volume_statistics.py --config config/config.yaml
```

FDR correction is applied across the 15 structures separately within each pairwise comparison.

Outputs:

```text
<ANALYSIS_ROOT>/csv/first/first_participant_volumes.csv
<ANALYSIS_ROOT>/csv/first/first_volume_statistics.csv
```

## 4. FIRST vertex-wise shape analysis

Prepare the three group comparisons and the 15 structure-specific vertex analyses:

```bash
python scripts/23_first_prepare_vertex.py --config config/config.yaml
```

This stage uses:

```text
concat_bvars
first_utils --vertexAnalysis --usebvars --useReconMNI --saveAverageMesh
```

Run structure-specific `randomise` inference:

```bash
python scripts/24_first_run_vertex_randomise.py --config config/config.yaml
```

The default configuration uses 10,000 permutations and TFCE.

Export the corrected clusters:

```bash
python scripts/25_first_export_vertex_results.py --config config/config.yaml
```

Output:

```text
<ANALYSIS_ROOT>/csv/first/first_vertex_clusters.csv
```

The FWE correction is spatial within each structure-specific `randomise` analysis. 

Cluster-level Hedges' g values in the exported CSV are descriptive values calculated from the vertex-displacement data within clusters defined by the same corrected vertex-wise analysis.

## 5. FAST tissue segmentation

Run skull stripping and FAST:

```bash
python scripts/30_fast_run_segmentation.py --config config/config.yaml
```

FAST is run as a three-class T1 segmentation and partial-volume maps are retained.

Export participant-level tissue volumes:

```bash
python scripts/31_fast_export_volumes.py --config config/config.yaml
```

Output:

```text
<ANALYSIS_ROOT>/csv/fast/fast_participant_volumes.csv
```

The CSV contains:

```text
CSF_cm3
GM_cm3
WM_cm3
Total_segmented_cm3
CSF_fraction
GM_fraction
WM_fraction
```

`Total_segmented_cm3` is the sum of the three FAST-derived classes.

Run the unadjusted statistics:

```bash
python scripts/32_fast_unadjusted_statistics.py --config config/config.yaml
```

Outputs:

```text
<ANALYSIS_ROOT>/csv/fast/fast_unadjusted_omnibus.csv
<ANALYSIS_ROOT>/csv/fast/fast_unadjusted_pairwise.csv
```

FDR correction is performed across the four omnibus tests and separately across all 12 pairwise tissue-volume tests.

## 6. eTIV input

The eTIV stage supports two reproducible routes.

### Route 1: public participant TIV table

Place a local copy of the public participant TIV table at:

```text
<ANALYSIS_ROOT>/metadata/participants_tiv.csv
```

The expected fields are shown in:

```text
config/participants_tiv.example.csv
```

The table should contain at least:

```text
Subject
Total Intracranial Volume
```

### Route 2: released FreeSurfer `aseg.stats`

Download the 42 public FreeSurfer data objects:

```bash
python scripts/00_download_brainlife.py \
  --config config/config.yaml \
  --what freesurfer
```

If `paths.freesurfer_root` is blank, the default location is:

```text
<ANALYSIS_ROOT>/downloads/freesurfer/
```

`33_extract_etiv.py` recursively locates `aseg.stats` and extracts:

```text
EstimatedTotalIntraCranialVol
```

If both the participant TIV table and FreeSurfer files are available, the script verifies the participant-table values against `aseg.stats` after rounding to three decimal places.

Run:

```bash
python scripts/33_extract_etiv.py --config config/config.yaml
```

Output:

```text
<ANALYSIS_ROOT>/csv/fast/participant_etiv.csv
```

## 7. eTIV-adjusted FAST sensitivity analysis

```bash
python scripts/34_fast_etiv_adjusted_statistics.py --config config/config.yaml
```

The script:

- converts eTIV from mm3 to cm3;
- grand-mean centers eTIV;
- evaluates group-by-eTIV interactions;
- fits common-slope OLS models with group and centered eTIV;
- uses HC3 heteroskedasticity-consistent covariance estimates;
- evaluates the omnibus group effect with a joint robust Wald F test;
- estimates pairwise adjusted group contrasts at the grand mean eTIV;
- provides robust 95% confidence intervals;
- applies FDR correction across the four adjusted omnibus tests;
- applies FDR correction separately across the 12 adjusted pairwise contrasts.

Outputs:

```text
<ANALYSIS_ROOT>/csv/fast/fast_etiv_correlations.csv
<ANALYSIS_ROOT>/csv/fast/fast_etiv_interactions.csv
<ANALYSIS_ROOT>/csv/fast/fast_etiv_omnibus.csv
<ANALYSIS_ROOT>/csv/fast/fast_etiv_adjusted_means.csv
<ANALYSIS_ROOT>/csv/fast/fast_etiv_pairwise.csv
<ANALYSIS_ROOT>/csv/fast/fast_etiv_model_coefficients.csv
```

## Run all analysis stages

If the data have already been downloaded and the configuration points to them:

```bash
bash scripts/90_run_all.sh config/config.yaml
```

To let the wrapper download both anatomical and FreeSurfer data first:

```bash
bash scripts/90_run_all.sh config/config.yaml --download
```

For a first execution on a new computer, running the stages individually is recommended so that brain extraction, VBM registration/template construction, and FIRST segmentation can be visually checked before continuing.

## Portability and paths

No absolute personal path is embedded in the repository. Every local filesystem location is read from `config/config.yaml`.

Use paths appropriate to the environment where FSL is running, for example:

```text
/path/to/downloaded/anat_t1w
/path/to/downloaded/freesurfer
/path/to/analysis
```
