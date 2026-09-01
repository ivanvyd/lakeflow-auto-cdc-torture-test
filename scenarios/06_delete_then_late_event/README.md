# Scenario 6 — Delete followed by an older late event

## What we do

```
seq=17 → ACTIVE
seq=20 → DELETE
```

Then a late event:
```
seq=18 → SUSPENDED
```

The first update processes sequences 17 and 20. The second appends sequence
18. SCD1 remains empty. SCD2 changes from one closed history row to two:
`ACTIVE[17,18)` and `SUSPENDED[18,20)`. The late row does not resurrect the
customer.

## What the contract says

- D1 worked example shows the same "late events are dropped" mechanism.
- D2, D3: For SCD2, the deleted row is retained as a tombstone in the
  underlying Delta table; a view in the metastore filters tombstones.
  Default tombstone retention is two days; configurable via
  `pipelines.cdc.tombstoneGCThresholdInSeconds` (this property is
  documented in D3 but not advertised in the conceptual page — we
  treat it as documented but not as part of the core contract, and do
  not depend on it).

## Why it matters

Resurrection of deleted rows is a real production failure mode. AUTO CDC
prevents it as long as the sequence column correctly represents the
source's view of event order. It cannot prevent it if your source's
sequence column is wrong.

## Sources

See `docs/sources.md` D1, D2, D3.

## Measured result

See `article/article.md` §3 and `results/normalized/summary_matrix.md`.
