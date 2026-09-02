# Scenario 2 — Valid out-of-order delivery

## What we do

Logical order:
```
seq=10 → PENDING
seq=12 → ACTIVE
```

Pipeline update order (reversed):
```
seq=12 → ACTIVE  arrives first
seq=10 → PENDING arrives second
```

Expected business state after AUTO CDC: `status=ACTIVE` (per-key max on `source_sequence`).

We capture both targets after the first update, append the older row, and run an incremental update.

## What the contract says

Documented out-of-order behavior (D1 worked example): "the last UPDATE
operations arrive late and are dropped from the target table." Same mechanism
gives us ACTIVE in this scenario.

## Sources

See `docs/sources.md` D1.

## Measured result

See `article/article.md` §3 and `results/normalized/summary_matrix.md`.
