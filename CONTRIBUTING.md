# Contribution Guide

## How to Run the Project

1. **Set up the development environment**
   ```bash
   # Create a Conda environment (if Conda is installed) or fall back to virtualenv
   make create_environment
   ```
   The Makefile automatically detects Conda; otherwise it uses `virtualenvwrapper`.

2. **Install the package and dependencies**
   ```bash
   make requirements
   # Equivalent manual steps:
   # pip install -e .
   # pip install -r requirements.txt
   ```

3. **Execute the data pipeline**
   ```bash
   # Process raw traffic data into a cleaned, processed form
   make data
   # Direct call (same as the Makefile target)
   python -m src.data.make_dataset data/raw data/processed
   ```

4. **Run linting / static checks**
   ```bash
   make lint   # runs flake8 across src/
   ```

5. **Synchronize data with S3 (optional)**
   ```bash
   make sync_data_to_s3   # upload local data/ to the bucket defined in the Makefile
   make sync_data_from_s3 # download bucket content locally
   ```
## Installing Packages

- **Environment setup:** Use `uv` to create and manage the project's virtual environment.
  ```bash
  uv venv
  ```
  By default, this creates a `.venv/` directory in the project root.

- **Editable install (development):** Install the project in editable mode so source changes are reflected without reinstalling.
  ```bash
  uv pip install -e .
  ```

- **Install standard dependencies:** Install the packages listed in `requirements.txt` into the virtual environment.
  ```bash
  uv pip install -r requirements.txt
  ```

- **Adding a new dependency:**
  1. Add the package name and, optionally, a version constraint to `requirements.txt`.
  2. Run the project's dependency installation command:
     ```bash
     uv pip install -r requirements.txt
     ```

## Managing Packages

- **Version pinning:** Prefer loose version constraints such as `package>=x.y` unless a breaking change requires tighter constraints. Keep dependency specifications consistent and maintainable.

- **Removing a dependency:** Remove its entry from `requirements.txt` and reinstall the dependencies:
  ```bash
  uv pip install -r requirements.txt
  ```

- **Virtual environment hygiene:**
  - Use the project's `make clean` target to remove compiled Python artifacts (`*.pyc` and `__pycache__/`), assuming the target is configured accordingly.
  - When changing Python versions, recreate the virtual environment and reinstall dependencies:
    ```bash
    rm -rf .venv
    uv venv --python 3.12
    uv pip install -r requirements.txt
    uv pip install -e .
    ```
    Replace `3.12` with the Python version required by the project.

- **Running commands:** Activate the environment before running Python commands:
  ```bash
  source .venv/bin/activate
  ```
  Alternatively, use `uv run` to execute commands in the project environment without manually activating it:
  ```bash
  uv run python your_script.py
  ```

## Contributing

1. **Fork the repository** and clone your fork locally.
2. **Create a feature branch** following the convention `feature/<short‑description>`.
   ```bash
   git checkout -b feature/add‑new‑model
   ```
3. **Write code** adhering to the project conventions:
   - Use **Click** for any new CLI entry point.
   - Follow the logging pattern shown in existing scripts.
   - Keep line length ≤ 79 characters; maintain `flake8` compliance.
4. **Add tests** (create a `tests/` directory if it does not exist) using `pytest`. Example:
   ```python
   def test_make_dataset(tmp_path):
       # simple sanity check for the CLI
       result = subprocess.run([
           "python", "-m", "src.data.make_dataset",
           "data/raw", str(tmp_path)
       ], capture_output=True)
       assert result.returncode == 0
   ```
5. **Run the full test suite locally**
   ```bash
   pytest --cov=src tests/
   ```
6. **Update documentation** if you add new commands or modules – edit the appropriate `.rst` files under `docs/` and run `make html` to verify.
7. **Commit with a clear message** and push to your fork.
8. **Open a Pull Request** targeting the default branch. The CI will automatically run `make lint` and the test suite.

## Code Review Checklist (for reviewers)
- ✅ Does the change respect the Click‑CLI pattern?
- ✅ Are new modules documented with a docstring and added to Sphinx if public?
- ✅ Does `flake8` pass (`make lint`)?
- ✅ Are unit tests present and covering the new logic?
- ✅ Are dependencies added only when truly required?

---

*Happy hacking!*