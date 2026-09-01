# Scenario 3 — Sequence collision

## What we do

Two events for the same key have the same `source_sequence` but different
states. The configured order cannot distinguish them.

- **Experiment A** — ambiguous sequence as-is.
- **Experiment B** — a real tie-breaker (`transaction_sequence`) that the
  source actually uses to order these events, plus a composite
  `STRUCT(source_updated_at, transaction_sequence)` flow documented in
  D2/D3.

## What the contract says

- D1, D2, D3 Limitations: "The sequencing column must be a sortable data
  type. `NULL` sequencing values are not supported."
- D1, D2, D3: "The API orders by the first field first, and in the event
  of a tie, considers the second field."

The documentation does not define which payload wins when two different
states share one configured sequence value. We classify both single-column
flows as `AMBIGUOUS_ORDER`; the composite flow has a total order.

## Sources

See `docs/sources.md` D1, D2, D3.

## Measured result

See `article/article.md` §3 and `results/normalized/summary_matrix.md`.
