# Scenario 7 — Replay the complete history

## What we do

A canonical sequence:
```
10 INSERT
20 UPDATE
30 UPDATE
40 UPDATE
50 DELETE
```

Process the complete stream and capture both targets. Append the same five
rows to the source, run an incremental update, and compare every visible
column and row with the baseline.

## What the contract says

The documentation explains sequence-based out-of-order handling. This
scenario measures the stronger replay claim instead of treating it as a
documented guarantee.

## Why it matters

The check proves state equality across an appended replay. A second update
with no new source rows would test checkpointing instead.

## Sources

See `docs/sources.md` D1, D4.

## Measured result

See `article/article.md` §3 and `results/normalized/summary_matrix.md`.
