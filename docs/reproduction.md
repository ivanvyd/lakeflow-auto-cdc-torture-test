# Reproduction

This document is the exact recipe to run the experiment from a clean checkout.

## Prerequisites

- **Databricks workspace** with a SQL warehouse and Unity Catalog enabled.
- **Databricks CLI** ≥ 0.292.0 (tested with 1.10.0).
- **Python** ≥ 3.10 locally.
- **GNU Make** and **jq** for the convenience targets below. On Windows, GNU Make may be installed as `mingw32-make`; substitute that executable for `make`.
- A user with permission to create catalogs / schemas (or an existing sandbox catalog).
- Serverless pipelines enabled in the workspace.

The experiment does **not** need:
- A PAT or any other secret in the repo. Auth is via the Databricks CLI profile.
- A particular machine size. Serverless compute scales to the dataset.

## One-time setup

```bash
# 1. Authenticate the CLI to your workspace
databricks auth login --host https://<your-workspace>.cloud.databricks.com --profile DEFAULT

# 2. Clone the repo
git clone https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test.git
cd lakeflow-auto-cdc-torture-test

# 3. Create a Python environment
python -m venv .venv
source .venv/bin/activate          # POSIX
# or: .\.venv\Scripts\Activate.ps1  # PowerShell
pip install -e ".[dev]"

# 4. Verify
databricks --version
databricks auth profiles    # should show DEFAULT
```

## End-to-end run

The four commands you actually need:

```bash
make setup      # validates and deploys the bundle
make test       # runs the initial and late/replay phases, then verifies live targets
make results    # <1 min.  regenerates the summary matrix and figures
make cleanup    # ~1 min.  drops schema and destroys the bundle
```

### What `make setup` does

1. `databricks bundle validate -t dev` — static validation of the DAB.
2. `databricks bundle deploy -t dev` — uploads the repository and deploys the pipeline resource. Only `src/pipeline/pipeline.py` is registered as executable pipeline source.

Source tables are populated by `make test`, after the bundle exists.

### What `make test` does

1. `apply_to_workspace --phase initial` creates every source table. It withholds the late rows for scenarios 2 and 6, the duplicate replay for scenario 1, and the lifecycle replay for scenario 7.
2. A full refresh resets checkpoints and targets. `capture_baseline.py` records every column and row from all 18 targets in `baseline_target_state.json`.
3. `apply_to_workspace --phase late` appends the four withheld streams. An incremental pipeline update processes them across a real update boundary.
4. `write_results.py` captures all 18 targets again. It requires the two expected SCD2 histories to change and the other 16 targets to remain equal to baseline. It then checks row counts and scenario-specific state predicates before replacing `scenario_results`.
5. `normalize.py` regenerates the local raw JSON and normalized matrix from the verified result table.

If an update fails, a phase transition differs, or a target predicate fails, verification exits non-zero before publishing replacement evidence.

### What `make results` does

1. `python -m src.analysis.normalize --profile DEFAULT --catalog workspace --schema auto_cdc_torture_test` — reads the verified `scenario_results`, computes the four-way classification, and writes `results/raw/scenario_results.json` plus `results/normalized/summary_matrix.{json,md}`.
2. `python -m src.analysis.figures` — regenerates the four PNG figures from the normalized JSON.

The result-generation step does not mutate source or target tables.

### What `make cleanup` does

- `databricks bundle destroy -t dev` — destroys the pipeline and any other bundle resources.
- `DROP SCHEMA workspace.auto_cdc_torture_test CASCADE` — drops every table the experiment created.

`make cleanup` is bounded to the `auto_cdc_torture_test` schema and the bundle's resources. It does not touch any other schema in the catalog.

## Running a single scenario

Useful when iterating on a generator or pipeline flow.

```bash
# Show the CDC events for scenario 4
python -m src.generators.dispatch --scenario 04_wrong_clock

# Materialize the initial rows for one scenario
python -m src.generators.apply_to_workspace --profile DEFAULT --catalog workspace \
  --schema auto_cdc_torture_test --scenario 04_wrong_clock --phase initial

# Trigger a clean pipeline update
databricks bundle run auto_cdc_torture_pipeline --full-refresh-all \
  --target dev --profile DEFAULT
```

## Verifying the run

After `make test`, the canonical evidence is in five places:

| File | What it is |
|---|---|
| `results/raw/baseline_target_state.json` | Every target row after the initial full refresh. |
| `results/raw/target_state.json` | Baseline and post-late rows plus both pipeline update ids. |
| `results/raw/scenario_results.json` | The 18 result rows emitted after phase and state assertions pass. |
| `results/normalized/summary_matrix.md` | The four-way classification per row, sorted by scenario family. |
| `results/figures/summary_matrix.png` | A bar chart of the 18 rows coloured by classification. |

`summary_matrix.md` is the file the article's summary table traces to. The JSON preserves the verified row counts, booleans, expectations, observations, and capture timestamp.

## Common failure modes

### Pipeline update fails with `DIFFERENT_DELTA_TABLE_READ_BY_STREAMING_SOURCE`

`make generate_all` does `DROP TABLE` + `CREATE TABLE` on the source tables. The Delta table id changes while an incremental pipeline checkpoint references the old id. Run `make test`, which already uses `databricks bundle run ... --full-refresh-all`.

### Pipeline update fails with `pipelines.cdc.tombstoneGCThresholdInSeconds` warning

This is informational. The bundle configures the tombstone retention to 48 hours, which exceeds every scenario's delay.

### `make test` appears stuck during the pipeline update

`databricks bundle run` waits for the serverless update and streams its state. Cold serverless startup can take several minutes. Inspect the pipeline in the workspace UI if the state does not advance.

### `databricks bundle deploy` fails with "catalog not found"

The DAB references `${var.catalog}` (default `workspace`). If your workspace does not have a catalog called `workspace`, override:

```bash
make setup CATALOG=<your-catalog> BUNDLE_TARGET=dev PROFILE=DEFAULT
make test CATALOG=<your-catalog> BUNDLE_TARGET=dev PROFILE=DEFAULT
```

## Time budget

- `make setup`: usually under 1 minute after authentication.
- `make test`: 5-10 minutes, mostly serverless startup for two pipeline updates.
- `make results`: <1 minute.
- Total: about 6-12 minutes for a clean run.

The bottleneck is the pipeline's cluster startup on a cold workspace, not the experiment's data size. The synthetic dataset is intentionally small.
