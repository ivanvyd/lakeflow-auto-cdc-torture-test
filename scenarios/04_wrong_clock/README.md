# Scenario 4 — The wrong clock

## What we do

Two logical source events:
```
10:00 source time → ACTIVE
10:05 source time → SUSPENDED
```

Recorded with ingestion timestamps in reverse business order:
```
10:05 arrives at Databricks at 10:06
10:00 arrives at Databricks at 10:10
```

Two AUTO CDC interpretations on the same source rows:
- **Target A** — `SEQUENCE BY ingested_at` (uses physical arrival time).
- **Target B** — `SEQUENCE BY source_updated_at` (uses source clock).

## Why it matters

Both targets are documented, both run green, but they produce *different*
business states. AUTO CDC cannot know whether "newer" means newer business
state, newer source transaction, newer extraction, or newer arrival. That
is application semantics. `SEQUENCE BY` defines what "newer" means in your
pipeline.

## Sources

See `docs/sources.md` D1, D2, D3.

## Measured result

See `article/article.md` §3 and §4, plus `results/figures/wrong_clock.png`.
