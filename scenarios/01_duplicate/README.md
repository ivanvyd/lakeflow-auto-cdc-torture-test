# Scenario 1 — Exact duplicate / replay

## What we do

- Deliver one logical CDC event for customer 42 (`source_sequence=10`, `status=ACTIVE`).
- Capture the target after one delivery.
- Append the same event to the replay source, run a second pipeline update, and compare the target with its baseline.

## What the contract says

AUTO CDC's out-of-order handling is documented to drop earlier events. With
identical key and identical non-null sequence, the per-key max produces a
stable result, but the documentation does not explicitly promise that
exact-duplicate events are deduplicated.

## Sources

See `docs/sources.md` D1, D2, D3.

## Measured result

See `article/article.md` §3 and `results/normalized/summary_matrix.md`.
