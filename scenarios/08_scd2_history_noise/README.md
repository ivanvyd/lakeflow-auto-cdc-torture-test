# Scenario 8 — SCD2 history noise

## What we do

A single customer with 50 updates to `last_synced_at` only (no business
state change). Two SCD2 targets on the same source:

- **A — naive**: track every relevant column. Every update creates a new
  history row.
- **B — `TRACK HISTORY ON * EXCEPT (last_synced_at)`**: only business-
  significant changes create new history rows.

## What the contract says

- D2 / D3: `TRACK HISTORY ON * EXCEPT (col_list)` is the documented
  mechanism to suppress operational noise in SCD2 history.
- The default is to track all output columns (equivalent to
  `TRACK HISTORY ON *`).

## Why it matters

Operational metadata should create business-history versions only when the
domain assigns business meaning to those changes.

## Sources

See `docs/sources.md` D2, D3.

## Measured result

See `article/article.md` §3 and `results/figures/scd2_history_noise.png`.
