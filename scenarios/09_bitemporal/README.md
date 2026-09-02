# Scenario 9: Bitemporal history

## What we do

Three events carry separate business and ingestion timestamps. The flow uses
`source_updated_at` for `SEQUENCE BY`, `ingested_at` for
`SYSTEM SEQUENCE BY`, and bitemporal storage.

## What the documentation says

Databricks documents bitemporal AUTO CDC as Beta. It adds
`__SYSTEM_START_AT` and `__SYSTEM_END_AT` alongside the SCD2 business-time
columns.

## Measured result

The target contains five rows. The verifier checks the exact valid-time and
system-time boundaries for all five. `results/raw/target_state.json` contains
the measured rows, and `results/figures/bitemporal_timeline.png` renders them.
