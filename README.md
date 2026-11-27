# LA-Traffic-Accident-Hotspots

Predicting weekly traffic accident hotspots in Los Angeles with historical records, spatial models and text-derived features.

The code currently available covers data inspection and event-level cleaning. The results recorded in the existing project README are retained below. Reproducing those model results will also require the team's training and evaluation notebooks.

## Project overview

The project estimates the probability that a 1 km × 1 km grid will record at least one accident in the following week, then ranks grids for a fixed Top-10 attention budget. Planned comparisons include historical frequency, logistic regression, CNN, ConvLSTM and historical incident-text features.

## Data

- Original source is [US Accidents on Hugging Face](https://huggingface.co/datasets/yuvidhepe/us-accidents-updated).
- The downloaded release contains seven Parquet shards, 7,728,394 rows and 46 source columns.
- The completed cleaning run retained 7,728,394 national records and 156,491 records with the source labels `State=CA` and `City=Los Angeles`.
- The source-label subset requires a separately defined study boundary before spatial modeling.
- Data acquisition instructions are in [data/README.md](data/README.md). A shared cleaned-data URL can be added when the group publishes it.
- Data attribution and licensing follow the upstream dataset. The repository LICENSE applies to the project code.

## Recorded model results

The existing project summary reports 563 candidate 1 km cells and a chronological split of 207 training weeks, 69 validation weeks and 70 test weeks.

It reports Top-10 coverage of 14.74% for Raw-History CNN and CNN with an 8–32-week rate feature, and improved Average Precision in 11 of 12 models when using System-1 text features. The text extraction model was recorded as `StartLLM-Decisions-8B-instruct`.

These figures come from the prior repository README. They have not been recalculated by the preprocessing notebooks published here. Model configurations, predictions and evaluation notebooks are needed to reproduce the comparison.

## Repository structure

```text
notebooks/
  01_us_accidents_slice.ipynb       Field inspection and a small reproducible sample
  02_us_accidents_cleaning.ipynb    National cleaning and LA event/environment/text tables
scripts/
  run_us_cleaning.ps1              Execute cleaning with the selected Python environment
  build_us_cleaning_notebook.py    Maintain the self-contained cleaning notebook
data/
  README.md                       Source and download instructions
reports/
  US_Accidents_切片.md              Field interpretation and the weekly example
  GEOG7308_数据清洗代码评审.md       Completed cleaning review
requirements.txt                  Installation entry point
requirements-lock.txt             Snapshot of the original Windows environment
```

## Environment

Use Python 3.11. On the original workstation, the project uses the existing Conda environment `7308-Final-project`. On another machine, create or select your own Python 3.11 Conda environment, then install the requirements there.

```powershell
conda activate 7308-Final-project
python -m pip install -r requirements.txt
python -m pip check
```

The lock file records the original Windows environment, including Windows-specific packages. Use `requirements.txt` as the general installation entry.

## Run the notebooks

Download the seven original Parquet shards into `data/`, then open the project in JupyterLab or an editor with notebook support. Select your installed Python environment as the notebook kernel.

For JupyterLab, register the kernel in the active environment and launch from this repository:

```powershell
python -m ipykernel install --sys-prefix --name 7308-final-project --display-name "Python (7308-Final-project)"
python -m jupyterlab
```

Run notebook 01 for the field overview, or notebook 02 for complete cleaning. Both notebooks locate the project from their working directory. No machine-specific interpreter assertion is required.

On Windows, the cleaning runner creates a project-local kernel specification for the interpreter you select. From an activated environment:

```powershell
./scripts/run_us_cleaning.ps1
```

To select an interpreter explicitly:

```powershell
./scripts/run_us_cleaning.ps1 -PythonExecutable 'C:/path/to/conda/envs/7308-Final-project/python.exe'
```

The runner stores Jupyter/IPython runtime files and temporary files under `outputs/cleaning_runtime/`.

## Cleaning outputs

Each full run creates `cleaned_data/run_.../`. Only runs that pass validation receive a `COMPLETE` marker and become the value in `cleaned_data/LATEST_RUN.txt`.

| Directory | Contents |
| --- | --- |
| 01_national | National master table partitioned by state, retaining source traceability and quality flags |
| 02_los_angeles | Core and environment tables with one row per event |
| 03_text | All LA event texts, nonempty candidates and a unique-text reuse table |
| 04_quality | Quarantine, duplicate checks, missingness, weekly coverage and numerical summaries |
| 05_metadata | Source hashes, field mapping, output inventory and environment versions |

Connect the LA tables one-to-one using `event_id`. Missing optional weather or text values preserve the underlying event. Three zero-pressure values in the original release are set to missing, with raw values and flags retained.

The first and last observed weeks are partial. The completed review also identifies source-label LA/CA weeks starting 2022-10-24 and 2023-03-06 with no records, and cross-ID duplicates that need a common modeling policy. Historical text publication time remains unverified. See the [cleaning review](reports/GEOG7308_数据清洗代码评审.md) before constructing grid-week samples.

Data files, generated outputs, local environments, credentials, IDE settings and administrative documents are excluded by `.gitignore`. Notebook outputs are cleared in the shared source version; running a notebook recreates them.

The builder script regenerates notebook 02 and replaces its saved cells and outputs. For normal cleaning, run the notebook or the PowerShell runner.
