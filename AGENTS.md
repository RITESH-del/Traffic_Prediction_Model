# Repository Guidelines

## Project Overview

`Traffic_Prediction_Model` is a Python-based machine learning project structured according to the DrivenData Cookiecutter Data Science (CCDS v1) architecture. Its purpose is to build, train, evaluate, and deploy traffic forecasting models using tabular/time-series data across a standardized, reproducible pipeline.

---

## Architecture & Data Flow

### High-Level Architecture

The codebase separates concerns across five discrete lifecycle stages:

1. **Raw Ingestion & ETL** (`src/data/`): Downloads and sanitizes raw sensor/traffic data into clean canonical representations.
2. **Feature Engineering** (`src/features/`): Derives time-series, spatial, or lag features from processed datasets.
3. **Model Training & Persistence** (`src/models/train_model.py`): Trains machine learning models and serializes model artifacts into `models/`.
4. **Inference & Scoring** (`src/models/predict_model.py`): Loads serialized model weights and generates predictions on evaluation or production data.
5. **Visualization & Reporting** (`src/visualization/` and `reports/`): Generates diagnostic plots, performance curves, and summary reports into `reports/figures/`.

### Data Flow Diagram

```text
data/raw/
   |
   v  (src/data/make_dataset.py)
data/processed/
   |
   v  (src/features/build_features.py)
Extracted Features / Arrays
   |
   v  (src/models/train_model.py)
models/*.pkl (or weights)
   |
   +--> (src/models/predict_model.py) --> Inference Outputs
   |
   +--> (src/visualization/visualize.py) --> reports/figures/*.png
```

---

## Key Directories

| Directory | Purpose |
| :--- | :--- |
| `src/` | Main Python package source, installed in editable mode when required. |
| `src/data/` | Data download, extraction, and transformation scripts. |
| `src/features/` | Feature extraction and feature engineering transformations. |
| `src/models/` | Model definitions, training routines, and inference scripts. |
| `src/visualization/` | Plotting and visualization generation routines. |
| `data/` | Data store: `raw/` contains immutable inputs, `interim/` contains partially transformed data, and `processed/` contains processed datasets. |
| `models/` | Serialized model checkpoints, trained weights, and summaries. |
| `notebooks/` | Numbered exploratory and prototyping Jupyter notebooks, such as `1.0-eda.ipynb`. |
| `references/` | Data dictionaries, domain documentation, and manual references. |
| `reports/figures/` | Generated analysis graphics and figures used in reports. |
| `docs/` | Sphinx documentation project, including `.rst` source files and the Sphinx Makefile. |
| `.venv/` | Project-local Python virtual environment managed by `uv`; should not be committed to Git. |

---

## Development Commands

Use `uv` for Python environment management and package installation. Existing `Makefile` targets may be used where they are compatible with the project's current `uv` configuration.

### Environment Setup

- Create the project virtual environment:

  ```bash
  uv venv
  ```

  This creates `.venv/` by default.

- Install standard dependencies from `requirements.txt`:

  ```bash
  uv pip install -r requirements.txt
  ```

- Install the project in editable mode when required:

  ```bash
  uv pip install -e .
  ```

- Run a Python script using the project environment:

  ```bash
  uv run python your_script.py
  ```

- Verify the active Python version:

  ```bash
  uv run python --version
  ```

**Environment conventions:**

- Use the project-local `.venv/` rather than creating separate Conda or virtualenv environments.
- Do not assume that `uv venv` installs project dependencies; install them separately.
- Prefer `uv run` for executing Python scripts and tools.
- If the project later adopts `pyproject.toml` and `uv.lock` as its authoritative dependency configuration, use `uv sync` and `uv add` as appropriate.
- Do not maintain conflicting dependency specifications across `requirements.txt`, `pyproject.toml`, and `uv.lock`.

### Dependency Management

- **Installing dependencies:** If `requirements.txt` remains the project's dependency source, install dependencies using:

  ```bash
  uv pip install -r requirements.txt
  ```

- **Adding a dependency:** Add the package name and an appropriate version constraint to `requirements.txt`, then reinstall dependencies:

  ```bash
  uv pip install -r requirements.txt
  ```

- **Removing a dependency:** Remove its entry from `requirements.txt` and reinstall dependencies:

  ```bash
  uv pip install -r requirements.txt
  ```

- **Version pinning:** Prefer reasonable lower bounds, such as `package>=x.y`, unless compatibility requirements justify tighter constraints. Keep dependency specifications clear and consistent.

- **Editable installation:** Install the local project in editable mode when required:

  ```bash
  uv pip install -e .
  ```

If dependency management is migrated to `pyproject.toml` and `uv.lock`, use `uv add package-name` to add dependencies and `uv remove package-name` to remove them. Use `uv sync` to synchronize the environment with the project metadata and lockfile.

### Linting & Environment Verification

- Validate Python runtime compatibility:

  ```bash
  uv run python test_environment.py
  ```

  The script should be used to verify the Python version requirements defined by the project.

- Run Flake8 on source code:

  ```bash
  uv run flake8 src
  ```

  Flake8 uses the rules configured in `tox.ini`.

### Data Pipeline & Sync

- Execute the data transformation pipeline:

  ```bash
  uv run python src/data/make_dataset.py data/raw data/processed
  ```

- Equivalent Makefile command, if the target is configured for the current environment:

  ```bash
  make data
  ```

- Synchronize data to and from AWS S3 using the existing Makefile targets:

  ```bash
  make sync_data_to_s3
  make sync_data_from_s3
  ```

Ensure that AWS credentials are configured securely before using S3 synchronization commands. Do not commit credentials or secrets.

### Build & Documentation

- Build Sphinx HTML documentation:

  ```bash
  cd docs && uv run make html
  ```

- Run Sphinx documentation doctests:

  ```bash
  cd docs && uv run make doctest
  ```

- Remove Python bytecode and `__pycache__/` directories:

  ```bash
  make clean
  ```

  This command assumes the existing `Makefile` target is configured to clean these artifacts.

- View the Makefile target summary:

  ```bash
  make help
  ```

---

## Code Conventions & Common Patterns

### CLI & Script Interface Pattern

Scripts designed to run standalone or through `make` should use **Click** with explicit path validation.

```python
import click
from pathlib import Path


@click.command()
@click.argument("input_filepath", type=click.Path(exists=True))
@click.argument("output_filepath", type=click.Path())
def main(input_filepath, output_filepath):
    """Process input data into output artifacts."""
    ...


if __name__ == "__main__":
    main()
```

Use `pathlib.Path` for path manipulation within scripts. Avoid introducing unnecessary CLI frameworks or changing established script interfaces without a reason.

### Logging

- Use the standard library `logging` module instead of `print()` for application and pipeline logging.
- Obtain loggers using `logging.getLogger(__name__)`.
- Use the following default format where appropriate:

  ```python
  import logging

  log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  logging.basicConfig(level=logging.INFO, format=log_fmt)
  logger = logging.getLogger(__name__)
  ```

### Environment Configuration & Secret Management

- Read the project root `.env` file using `python-dotenv` when required:

  ```python
  from dotenv import find_dotenv, load_dotenv

  load_dotenv(find_dotenv())
  ```

- Never commit `.env` files containing secrets, AWS credentials, access tokens, or other sensitive configuration.
- Use environment variables or approved secret-management mechanisms for credentials.
- Ensure `.venv/`, cache directories, and generated artifacts are excluded from Git where appropriate.

### Path Handling

- Use `pathlib.Path` with paths resolved relative to the file location or project root.

  ```python
  from pathlib import Path

  project_dir = Path(__file__).resolve().parents[2]
  ```

- Verify the correct parent depth for each module instead of assuming the same depth throughout the repository.
- Avoid relying on the current working directory when a path can be resolved reliably from the project structure.

### Code Style & Formatting

- **Linter:** `uv run flake8 src`
- **Line length:** Maximum 79 characters, as configured in `tox.ini`.
- **Cyclomatic complexity:** Maximum complexity of 10, as configured in `tox.ini`.
- **Source encoding:** Use UTF-8 for Python source files.
- **Imports:** Standard library first, third-party packages second, and local project imports third.

### Notebook Naming Conventions

Follow the Cookiecutter convention for exploratory notebooks in `notebooks/`:

- Pattern: `<step>-<author_initials>-<short_description>.ipynb`
- Example: `1.0-jqp-traffic-sensor-eda.ipynb`

Run notebooks using the project's `.venv` environment and ensure the required Jupyter dependencies are installed.

---

## Important Files

- `src/data/make_dataset.py`: CLI entry point for processing raw data into processed data.
- `src/features/build_features.py`: Feature engineering pipeline module.
- `src/models/train_model.py`: Entry point for training traffic prediction models.
- `src/models/predict_model.py`: Entry point for running model inference.
- `src/visualization/visualize.py`: Script for generating exploratory or diagnostic figures.
- `setup.py`: Legacy setuptools configuration, if still used to install the project in editable mode.
- `requirements.txt`: Dependency list used by `uv pip install -r requirements.txt`, if retained as the project's dependency source.
- `pyproject.toml`: Project metadata and dependency configuration, if present.
- `uv.lock`: Lockfile generated by `uv`, if the project uses lockfile-based dependency management.
- `.venv/`: Project-local virtual environment; generated locally and not committed to Git.
- `test_environment.py`: Python runtime compatibility validator.
- `tox.ini`: Static analysis configuration for Flake8.
- `Makefile`: Centralized task runner for development, linting, data generation, and cloud synchronization.
- `docs/conf.py`: Sphinx documentation configuration.

---

## Runtime/Tooling Preferences

- **Language Runtime:** Use the Python version supported by the project. Verify it using `uv run python --version`.
- **Environment Management:** Use `uv` and the project-local `.venv/` directory. Avoid creating separate Conda or virtualenv environments unless explicitly required.
- **Package Management:** If dependencies are maintained in `requirements.txt`, use `uv pip install -r requirements.txt`. If the project uses `pyproject.toml` and `uv.lock`, use `uv sync` and `uv add` as appropriate.
- **Command Execution:** Prefer `uv run` for Python scripts and tools so they execute using the project environment.
- **Editable Installation:** Use `uv pip install -e .` when the project package must be installed in editable mode.
- **Cloud Tooling:** Use AWS CLI for existing S3 dataset synchronization workflows.
- **Documentation Engine:** Use Sphinx for documentation in `docs/`, with reStructuredText `.rst` files.
- **Reproducibility:** Keep dependency declarations and environment setup instructions consistent with the actual repository configuration. Do not silently change Python versions or dependency sources.

---

## Testing & QA

### Environment Verification

Run:

```bash
uv run python test_environment.py
```

Confirm that the Python interpreter satisfies the project's requirements.

### Static Analysis & Linting

Run:

```bash
uv run flake8 src
```

Resolve relevant lint errors before considering the code change complete.

### Documentation Tests

Run:

```bash
cd docs && uv run make doctest
```

### Unit & Integration Tests

- Place unit and integration tests under `tests/`.
- Use `pytest` for the test suite when configured.
- Run tests and coverage using:

  ```bash
  uv run pytest --cov=src tests/
  ```

- Ensure the relevant test dependencies, including `pytest` and `pytest-cov`, are installed before running the command.
- Report which tests were executed and their actual results. Do not claim that tests passed unless they were run.

---

## Agent Guidelines

- Inspect the existing repository files and configuration before changing project setup or dependencies.
- Do not delete any file without asking first, if it is not in .gitignore, it might be used.
- Prefer minimal, targeted changes that preserve the existing CCDS architecture and established workflows.
- Do not assume that a Makefile target is compatible with `uv`; inspect its implementation before relying on it.
- Do not modify data, trained model artifacts, credentials, or unrelated files during environment maintenance.
- Keep documentation aligned with the actual `Makefile`, dependency files, Python version, and environment configuration.
- When changing dependencies, update the authoritative dependency source and associated lockfile if applicable.
- Validate changes using relevant commands and document any checks that could not be run.
