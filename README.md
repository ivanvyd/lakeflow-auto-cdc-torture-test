# I Tried to Break Lakeflow AUTO CDC

[![CI](https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test/actions/workflows/ci.yml/badge.svg)](https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test/actions/workflows/ci.yml)

A reproducible engineering experiment that feeds nine hostile CDC streams into Lakeflow `AUTO CDC` and records what it handles, where configuration matters, where ordering is ambiguous, and which decisions belong to the business domain.

This repository is the experiment. The [Databricks Community article](article/article.md) is the report.

## Scope

This repository tests `AUTO CDC` semantics with a small deterministic dataset. It is an executable report rather than a tutorial or throughput benchmark. The goal is to separate Databricks behavior from the ordering, NULL, and history rules that your domain must define.

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

Each configuration records:

- `ordering_complete`: whether `SEQUENCE BY` orders conflicting business states without ties.
- `business_assertion_passed`: whether the target matches the scenario's domain rule.
- `expected` and `observed`: the intended and measured target states.
- `target_rows` and `history_rows`: the measured target counts.

The [fact-check ledger](article/fact-check.md) maps documentation claims to official Databricks sources and run-derived claims to captured target rows.

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
- A user with permission to use the target catalog and create an isolated schema.
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

## Evidence and reproduction

- [Claim-by-claim evidence ledger](article/fact-check.md)
- [Official source ledger](docs/sources.md)
- [Reproduction guide](docs/reproduction.md)

## Safety

The default run uses a dedicated schema (`auto_cdc_torture_test`) in the `workspace` catalog. Catalog and schema overrides are explicit, so point them only at an isolated experiment namespace. User-supplied identifiers are validated before entering SQL. No PATs, passwords, or workspace identifiers are committed. Authentication is through the Databricks CLI profile.
