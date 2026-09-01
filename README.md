# I Tried to Break Lakeflow AUTO CDC

[![CI](https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test/actions/workflows/ci.yml/badge.svg)](https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test/actions/workflows/ci.yml)

A reproducible engineering experiment that feeds Lakeflow `AUTO CDC` nine hostile CDC streams and records what it handles, where configuration matters, where ordering is ambiguous, and which decisions belong to the business domain.

This repository is the experiment. The [full article](article/article.md) is the report.

## What this is not

- Not a tutorial on `AUTO CDC`.
- Not a benchmark. The dataset is tiny on purpose; the experiment is about semantics.
- Not a critique of `AUTO CDC`. The goal is to delineate the boundary between "Databricks capability" and "what only your domain can decide."

## What this is

Nine scenarios, each a small controlled CDC stream into a Lakeflow pipeline:

1. Exact duplicate / replay
2. Valid out-of-order delivery
3. Sequence collision (same key, same sequence value, different state)
4. The wrong clock (`SEQUENCE BY ingested_at` vs `SEQUENCE BY source_updated_at`)
5. Sparse update / `NULL` semantics
6. Delete followed by an older late event
7. Replay the complete history
8. SCD2 history noise from operational fields
9. Bitemporal history with separate valid and system time

Each scenario ships with a generator, a deterministic assertion, and a measured result that distinguishes:

- `DOCUMENTED_EXPECTATION` — what the official Databricks documentation says
- `BUSINESS_EXPECTATION` — what the scenario's domain logic wants
- `OBSERVED_RESULT` — what the pipeline actually produced

## Repository layout

```
src/
  scenario_specs.py Canonical sources, flows, expected states, and predicates
  pipeline/        Lakeflow Declarative Pipelines definitions
  generators/      Deterministic events and two-phase materialization
  analysis/        Live verification, target snapshots, normalization, figures
scenarios/
  01_duplicate/    Per-scenario explanation and expected result
  02_out_of_order/
  ...
results/           Before/after target rows, normalized results, and figures
article/           Article, results summary, fact-check, limitations
docs/              sources.md, architecture.md, reproduction.md
```

## Quick start

Requires:

- A Databricks workspace with a `DEFAULT` CLI profile (`databricks auth login --host <workspace> --profile DEFAULT`).
- A user with permission to create catalogs / schemas (or use an existing sandbox catalog).
- Databricks CLI ≥ 0.292.0 (tested with 1.10.0).
- A SQL warehouse and serverless compute enabled.
- Python ≥ 3.10, GNU Make, and jq. On Windows, GNU Make may be named `mingw32-make`.

```bash
git clone https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test.git
cd lakeflow-auto-cdc-torture-test
make setup   # validates and deploys the bundle
make test    # captures a baseline, appends late/replay rows, verifies both phases
make results # regenerates the summary matrix and figures
make cleanup CONFIRM_SCHEMA=auto_cdc_torture_test # drops schema and destroys the bundle
```

The default schema is `auto_cdc_torture_test`. Cleanup requires a separately supplied exact confirmation and refuses cascading deletion outside the `auto_cdc_torture` schema prefix. The Makefile does not derive that confirmation from the target schema.

## Read next

- [Full article](article/article.md)
- [Claim-by-claim evidence ledger](article/fact-check.md)
- [Official source ledger](docs/sources.md)
- [Reproduction guide](docs/reproduction.md)

## Safety

The default run uses a dedicated schema (`auto_cdc_torture_test`) in the `workspace` catalog. Catalog and schema overrides are explicit, so point them only at an isolated experiment namespace. User-supplied identifiers are validated before entering SQL. No PATs, passwords, or workspace identifiers are committed. Authentication is through the Databricks CLI profile.
