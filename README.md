# Customer Segmentation using Machine Learning

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)
[![Formatter: black](https://img.shields.io/badge/formatter-black-000000.svg)](https://black.readthedocs.io/)

Collaborative academic research project on **customer segmentation using
unsupervised machine learning**, applied to transactional retail data.

This repository is the shared working environment for the team. It contains
only the **project foundation**: directory structure, configuration, code
placeholders, tests, and documentation. No modeling experiments have been
run yet.

---

## 1. Project Purpose

The goal of this research is to segment customers of an online retailer into
behaviorally meaningful groups using transactional data, and to benchmark
several clustering algorithms on the resulting customer-level feature space.

The work follows a fixed multi-stage pipeline:

```
DS-05 (dataset selection, done)
   -> FE-01 (feature engineering framework, next)
       -> preprocessing
           -> RFM + extended behavioral features
               -> feature transformation
                   -> clustering (K-Means, K-Medoids, Agglomerative, DBSCAN)
                       -> internal evaluation, stability, runtime
                           -> customer profiling
                               -> visualization and reporting
```

The research questions and methodology are documented in
`docs/methodology/` and must not be modified without a recorded decision in
`docs/decisions/`.

---

## 2. Current Research Stage

| Stage  | Status                | Description                                                 |
| ------ | --------------------- | ----------------------------------------------------------- |
| DS-05  | Done                  | Dataset selection: primary and backup datasets chosen.       |
| FE-01  | Next                  | Feature engineering framework definition.                   |
| ...    | Pending               | Preprocessing, clustering, evaluation, profiling, reporting. |

This commit establishes the **repository foundation only**. No feature
engineering, no clustering, and no evaluation results exist yet.

---

## 3. Datasets and Roles

The role of each dataset is fixed by the DS-05 decision and must not be
changed without a recorded decision.

| Role      | Dataset               | Expected location                |
| --------- | --------------------- | -------------------------------- |
| Primary   | UCI Online Retail     | `data/raw/primary/`              |
| Backup    | UCI Online Retail II  | `data/raw/backup/`               |

See `configs/dataset.yaml` for the structured description.

**Data privacy rule**: raw datasets are **never** committed to Git. They
live locally under `data/raw/` and are excluded by `.gitignore`. Only
`.gitkeep` placeholders are tracked.

---

## 4. Repository Structure

```
customer-segmentation-ml/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── requirements.txt
├── pyproject.toml
│
├── configs/                  # YAML configuration (datasets, features, clustering, ...)
├── data/
│   ├── raw/{primary,backup}  # raw datasets (git-ignored)
│   ├── interim/              # intermediate artifacts (git-ignored)
│   ├── processed/            # modeling-ready datasets (git-ignored)
│   └── external/             # any external reference data (git-ignored)
│
├── notebooks/                # numbered exploratory notebooks, one folder per stage
├── src/customer_segmentation/
│   ├── data/                 # loaders, validators, schema
│   ├── preprocessing/        # cleaning, missing values, duplicates, outliers
│   ├── features/             # RFM, extended features, validation
│   ├── transformation/       # skewness correction, scaling, pipelines
│   ├── clustering/           # K-Means, K-Medoids, Agglomerative, DBSCAN
│   ├── evaluation/           # internal metrics, stability, runtime, comparison
│   ├── profiling/            # customer-level segment profiles
│   └── visualization/        # distributions, RFM, clustering, profiling plots
│
├── scripts/                  # CLI entry points for each pipeline stage
├── tests/                    # pytest tests (run without raw data)
├── reports/                  # generated reports and figures (git-ignored)
├── docs/                     # methodology, data dictionary, decisions, experiment logs
└── .github/
    ├── workflows/tests.yml   # CI: install deps and run pytest
    └── PULL_REQUEST_TEMPLATE.md
```

---

## 5. Creating the Python Environment

The project requires **Python 3.11+**. We recommend a project-local virtual
environment.

### Option A: venv (standard library)

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows PowerShell

python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Option B: conda

```bash
conda create -n custseg python=3.11 -y
conda activate custseg
pip install -r requirements.txt
```

### Optional: install the project package in editable mode

```bash
pip install -e .
```

---

## 6. Running Tests

Tests are designed to run **without raw data** so they pass on any
researcher's machine and on CI immediately after cloning.

```bash
# all tests
pytest

# with coverage
pytest --cov=customer_segmentation

# a single test file
pytest tests/test_rfm.py -v
```

Linting and formatting:

```bash
ruff check .
ruff format .
black .
```

---

## 7. Data Privacy and Git Rules

The following rules are **mandatory** for every contributor.

1. **Never** commit raw or processed datasets. `data/raw/`, `data/interim/`,
   `data/processed/`, and `data/external/` are git-ignored. Only `.gitkeep`
   placeholders are tracked.
2. **Never** commit generated reports or figures. `reports/` is git-ignored.
3. **Never** commit local experiment logs, notebook checkpoints, or local
   `.env` files.
4. **Always** use `.env.example` as the template if you need environment
   variables. Document any new variable in `.env.example`.
5. Document every **methodology or engineering decision** in
   `docs/decisions/` using the ADR template.
6. Document every **experiment** in `docs/experiment_logs/` with the
   config hash, seed, and environment.

---

## 8. Contribution Workflow

1. Create a feature branch from `master` (the default branch):
   ```bash
   git checkout -b feat/<task-id>-<short-name>
   ```
2. Implement only the scope of your assigned task (e.g. `FE-01-rfm`).
3. Add or update tests in `tests/`.
4. Update `docs/` if you change methodology, configuration, or the data
   dictionary.
5. Run `ruff check .`, `black .`, and `pytest` locally before pushing.
6. Open a Pull Request using the template in
   `.github/PULL_REQUEST_TEMPLATE.md`. Fill in: task ID, description, files
   changed, validation performed, research impact, and reproducibility
   notes.
7. CI must pass before review. Reviewers must verify that no raw data and
   no generated artifacts are included in the diff.

---

## 9. License

This project is released under the MIT License. See [`LICENSE`](./LICENSE)
for the full text.