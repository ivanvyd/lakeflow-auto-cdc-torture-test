# Scenario 5 — Sparse update / NULL semantics

## What we do

Initial state:
```
id=42, name=Ivan, email=x@example.com, city=Antalya, status=ACTIVE
```

A sparse-looking event:
```
id=42, city=Istanbul, email=null
```

Two targets on the same source:
- **Interpretation A** — NULL means `SET email = NULL` (default behavior).
- **Interpretation B** — NULL means "this field wasn't supplied" → use
  `IGNORE NULL UPDATES`.

## Why it matters

Both are documented behaviors. AUTO CDC can implement either contract but
cannot infer which one your source intended. If your source cannot
distinguish "field omitted" from "field explicitly set to null" (e.g.
because the wire format destroys the difference), no downstream
configuration can recover it. The `COLUMNS TO UPDATE` clause (D4) exists
for sources that can carry the column-set in the record itself.

## Sources

See `docs/sources.md` D2, D3, D4.

## Measured result

See `article/article.md` §3 and `results/normalized/summary_matrix.md`.
