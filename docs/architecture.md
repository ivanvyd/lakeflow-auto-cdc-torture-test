# Architecture

The diagram, the wiring, and the boundaries.

## The picture

```
                         <catalog>.auto_cdc_torture_test
   ┌──────────────────────────────────────────────────────────────┐
   │                                                              │
   │   ┌────────────────┐    readStream    ┌────────────────────┐  │
   │   │ sNN_xxx_src    │ ───────────────► │ @dp.view (sNN_xxx) │  │
   │   │ Delta table    │                  └────────────────────┘  │
   │   │ (materialized  │                              │           │
   │   │  in two phases │                              ▼           │
   │   │  via INSERT)   │                  ┌────────────────────┐  │
   │   │                │                  │ create_auto_cdc_   │  │
   │   └────────────────┘                  │ flow(...)          │  │
   │           ▲                            └────────────────────┘  │
   │           │                                       │           │
   │   ┌───────┴────────┐                              ▼           │
   │   │ dispatch.py    │                  ┌────────────────────┐  │
   │   │ (generator)    │                  │ sNN_xxx_tgt        │  │
   │   │                │                  │ Delta streaming    │  │
   │   │ Generates CDC  │                  │ table (SCD1 / SCD2 │  │
   │   │ rows for one   │                  │  / bitemporal)     │  │
   │   │ scenario at a  │                  └────────────────────┘  │
   │   │ time           │                              │           │
   │   └────────────────┘                              │           │
   │           ▲                                       │           │
   │           │           ┌──────────────────────────┐           │
   │           └────────── │ capture_baseline.py /    │ ◄─────────┤
   │                       │ write_results.py         │           │
   │                       └──────────────────────────┘           │
   │                                       │                       │
   │                                       ▼                       │
   │                       ┌──────────────────────────┐           │
   │                       │ scenario_results          │           │
   │                       │ (one row per scenario,    │           │
   │                       │  per configuration)      │           │
   │                       └──────────────────────────┘           │
   │                                       │                       │
   │                                       ▼                       │
   │   local:  results/raw/{baseline_target_state,target_state}.json│
   │           results/normalized/summary_matrix.{json,md}         │
   │           results/figures/*.png                                │
   │                                                              │
   └──────────────────────────────────────────────────────────────┘
```

## Layers

### 1. Generators (`src/generators/dispatch.py`)

Pure Python. No Spark, no Databricks SDK. Each `scenario_NN_xxx` function returns rows that match the canonical source schema. The generators use fixed timestamps and contain no randomness.

The dispatcher CLI is `python -m src.generators.dispatch --scenario <key> [--output <file>]`. It materializes the generator output to JSON.

### 2. Source materialization (`src/generators/dispatch.py` + `databricks` SDK)

`src/generators/apply_to_workspace.py` sends the generator output through the Databricks SQL Statement Execution API:

1. `DROP TABLE IF EXISTS sNN_xxx_src` on the workspace catalog.
2. `CREATE TABLE sNN_xxx_src (...) USING DELTA` with the canonical CDC schema.
3. `INSERT INTO sNN_xxx_src VALUES (...)` with the generator's rows.

The initial phase withholds four streams. After a full refresh and baseline capture, the late phase appends those rows and an incremental update processes them. This creates a real update boundary for late-arrival and replay claims.

### 3. Streaming view (`src/pipeline/pipeline.py`)

For every source, the pipeline declares a `@dp.view` that obtains the active Spark session and calls `readStream.table(...)`. AUTO CDC consumes this streaming view.

The generator materializes the source as a plain Delta table, and the pipeline sees it as a stream. The pipeline never knows the source was generated rather than streamed.

### 4. AUTO CDC flow (`src/pipeline/pipeline.py`)

One or more `create_auto_cdc_flow` calls per source, depending on the scenario. The flows vary along these axes:

- `keys=["customer_id"]` — always the same, every flow uses customer_id as the key.
- `sequence_by=<col or struct>` — the heart of the experiment. Scenarios differ on this:
  - Most scenarios use a single column (`source_sequence`, `source_updated_at`, `ingested_at`).
  - Scenario 3B-struct uses `F.struct(F.col("source_updated_at"), F.col("transaction_sequence"))` to get a composite tie-breaker.
- `apply_as_deletes=F.expr("operation = 'DELETE'")` — translates `operation = 'DELETE'` rows into tombstones.
- `except_column_list=[...]` — strips metadata columns from the target. The exact list depends on the scenario (e.g. scenario 8 strips every metadata column, scenario 9 keeps `__START_AT` / `__END_AT`).
- `stored_as_scd_type` — `"1"`, `"2"`, or `"bitemporal"`. Scenario 8 only makes sense in SCD2, scenario 9 only in bitemporal.
- `ignore_null_updates=True` — only in scenario 5B. The single column that controls NULL semantics.
- `track_history_except_column_list=[...]` — only in scenarios 2-scd2, 6-scd2, 7-scd2, and 8B. The list always includes `last_synced_at`. Without this, SCD2 history is dominated by the `last_synced_at` operational timestamp.

### 5. Live verification (`src/analysis/write_results.py`)

`make test` runs a full refresh and an incremental update. The verification path:

1. Requires both referenced updates to have terminal state `COMPLETED`.
2. Captures all 18 targets after the full refresh and after the late phase.
3. Requires the two late-event SCD2 targets to change and the other 16 targets to remain equal.
4. Checks each final row count and scenario-specific state predicate.
5. Replaces `scenario_results` only after every phase and state check passes.

Human-readable observation strings remain curated, but they cannot be published unless the corresponding live predicate matches.

### 6. Analysis (`src/analysis/`)

Four scripts participate:

- `capture_baseline.py` — saves every target row after the full refresh.
- `write_results.py` — compares phases, validates final targets, and writes the canonical evidence.
- `normalize.py` — reads `scenario_results` from the workspace, computes the classification, writes `results/normalized/summary_matrix.{json,md}`. Pure SDK; no Spark.
- `figures.py` — produces four PNG figures. The bitemporal chart reads measured rows from `target_state.json`; the other charts read the normalized matrix.

The `OBSERVED` list is the source of the human-readable summary, while `LIVE_ASSERTIONS` is the publication gate. If platform behavior changes, the verifier fails before replacing the evidence artifacts.

## Why this split?

- **Generators are pure Python.** They can be unit-tested with `pytest`. They run in milliseconds. They are the test fixtures.
- **The pipeline is a serverless Lakeflow pipeline.** It does not depend on the local verifier process. It is the system under test.
- **The Makefile drives both phases.** It resolves the deployed pipeline id and passes both completed updates into the evidence chain.
- **Verification is SQL-based.** It reads live Delta targets through a warehouse; no local Spark session is required.
- **Figure generation is decoupled.** Once normalized JSON exists, figures require no Databricks workspace or network.

This layering is what makes the experiment *reproducible* in the strict sense: every result is traceable from a checked-in JSON file to a row in a table to a sentence in the article.

## Boundaries

- The experiment is bounded to the `auto_cdc_torture_test` schema. `make cleanup` is the only way to drop it.
- The bundle is bounded to the `auto_cdc_torture_pipeline` resource. `databricks bundle destroy` removes it.
- Direct Python dependency minimums are declared in `pyproject.toml`.
- The Databricks CLI is the only authentication path. No PATs, no OAuth tokens, no service principals in the repo.

The Databricks workspace you point this at is the only thing that needs to exist outside your laptop. Everything else is in the repo.
