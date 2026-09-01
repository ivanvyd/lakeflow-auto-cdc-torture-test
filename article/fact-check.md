# Article evidence ledger

This ledger maps the article's material claims to official documentation,
live target evidence, or both. Generated summaries cannot pass the publication
gate unless both pipeline updates complete and every verifier assertion passes.

## Evidence set

| Evidence | Current value |
|---|---|
| Pipeline | `1ff99f04-078f-4c91-97e3-f06ad7614f7f` |
| Baseline full refresh | `76337b92-46fd-445d-b929-7a85aa038471`, `COMPLETED` |
| Late/replay incremental update | `d14e5ff1-b840-4e14-affd-902ec98f9fdf`, `COMPLETED` |
| Clean-checkout execution source | PR #1 head commit [`01d53b4`](https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test/commit/01d53b4902ab91876b26193a96c0ce193c12237a) |
| Baseline target snapshot | `results/raw/baseline_target_state.json` |
| Before/after target evidence | `results/raw/target_state.json` |
| Verified result rows | `results/raw/scenario_results.json`, 18 rows |
| Generated classification | `results/normalized/summary_matrix.json`, 18 rows |

The generated classification contains 10 `HANDLED`, 3
`CONFIGURATION_DEPENDENT`, 3 `BUSINESS_SEMANTICS`, and 2
`AMBIGUOUS_ORDER` rows.

## Method claims

| Article claim | Evidence | Verdict |
|---|---|---|
| Late arrivals cross a pipeline-update boundary. | `INITIAL_ROWS_BY_SOURCE` withholds scenario 2 sequence 10 and scenario 6 sequence 18. `LATE_ROWS_BY_SOURCE` appends them after baseline capture. The two update ids above differ. | Supported |
| Replays cross a pipeline-update boundary. | The late phase appends one duplicate row for scenario 1 and all five lifecycle rows for scenario 7. | Supported |
| Replay targets remain unchanged. | `target_state.json` contains equal baseline and post-late snapshots for `s01_duplicate_replay_tgt`, `s07_replay_tgt`, and `s07_replay_scd2_tgt`. | Supported |
| Only two visible targets change after the late phase. | `write_results.py` compares all columns and rows. It requires changes only in `s02_out_of_order_scd2_tgt` and `s06_delete_late_scd2_tgt`. The current run passed all 18 phase checks. | Supported |
| Scenario timestamps represent seconds and minutes. | `_t` adds `timedelta(seconds=...)`. The generator unit test checks that `_t(300)` equals five minutes after `T0`. | Supported |
| Five green results needed intervention before production. | All 18 configurations report `GREEN`. Configurations 3A and 3B have incomplete ordering; 4A, 5A, and 8A fail the experiment's business rule. The article names all five and labels the shipping judgment in the author's voice. | Supported editorial conclusion |

## Scenario claims

### 1. Exact duplicate and replay

The base and replay targets each contain one `ACTIVE` row. The replay target
is equal before and after the second delivery. This supports stable visible
state for the identical replay. The article does not claim transactional
deduplication.

### 2. Out-of-order delivery

The baseline contains sequence 12. The second update appends sequence 10.
SCD1 remains one `ACTIVE` row. SCD2 changes from one row to two:
`PENDING[10,12)` and an open `ACTIVE@12` row. Official source D1 documents
the SCD1 late-update example and the SCD2 history model; the checked-in
snapshots prove this run's exact SCD1/SCD2 outputs.

### 3. Sequence collision

Both single-column flows receive different states tied at sequence 10. The
documentation defines `SEQUENCE BY` as logical event order and documents a
`STRUCT` for tie-breaking, but it does not specify a winner for tied payloads.
Both rows therefore use `AMBIGUOUS_ORDER`. The composite flow orders by
`(source_updated_at, transaction_sequence)` and produces `SUSPENDED` with a
complete order.

### 4. Wrong clock

The source generator contains business times 10:00 and 10:05 and ingestion
times 10:10 and 10:06. The ingestion-ordered target contains `ACTIVE`; the
source-time target contains `SUSPENDED`. Both live predicates passed.

### 5. Sparse NULL update

The default target contains `email=NULL` and `city='Istanbul'`. The
`ignore_null_updates=True` target retains `email='x@example.com'` and updates
the city. D2 documents both the default overwrite and retained-value behavior.

### 6. Delete followed by an older event

The baseline processes sequences 17 and 20. Sequence 18 arrives in the second
update. SCD1 remains empty. SCD2 changes from one row to
`ACTIVE[17,18)` plus `SUSPENDED[18,20)`. The delete does not leave an open row.

### 7. Full lifecycle replay

The second update appends the same sequences 10, 20, 30, 40, and 50. SCD1 is
empty in both snapshots. SCD2 contains the same four rows in both snapshots,
with ends at 20, 30, 40, and 50.

### 8. SCD2 history noise

The source contains one initial row and 50 updates where only
`last_synced_at` changes among target columns. Default tracking produces 51
history rows and fails the experiment's business rule. Excluding
`last_synced_at` from history tracking produces one row. D1 through D3 document
the default and exclusion option.

### 9. Bitemporal history

The live predicate checks all five rows, including exact values for
`__START_AT`, `__END_AT`, `__SYSTEM_START_AT`, and `__SYSTEM_END_AT`.
`target_state.json` stores those rows, and `figures.py` renders them directly.
D2 through D4 document the two time dimensions and Beta status.

## Documentation claims

The official sources in `docs/sources.md` support these statements:

- `AUTO CDC` supports SCD1, SCD2, and Beta bitemporal storage.
- `AUTO CDC FROM SNAPSHOT` is Python-only.
- `SEQUENCE BY` defines logical event order and accepts a `STRUCT` for ties.
- `IGNORE NULL UPDATES` retains existing values for incoming NULL fields.
- `TRACK HISTORY ON * EXCEPT` excludes columns from SCD2 history tracking.
- `SYSTEM SEQUENCE BY` applies to bitemporal targets.

The article labels run-derived behavior as observed evidence and does not
promote it to a documented platform guarantee.

## Databricks Technical Blog submission audit

Reviewed on 2026-09-01 against the official [Content Guidelines for the
Databricks Community Technical
Blog](https://community.databricks.com/t5/announcements/content-guidelines-for-the-databricks-community-technical-blog/td-p/162112).
This audit covers the requirements stated on the public page. Its linked
attachment was not available to an unsigned automated reader, so any
attachment-only formatting or submission requirements still need a final
manual check in the Community editor.

| Guideline | Article evidence | Verdict |
|---|---|---|
| Real technical content | Nine source scenarios, 18 flow configurations, runnable code, exact target rows, and two pipeline updates. | Meets |
| Honest reflection | The article identifies five green configurations the author would not ship and separates product behavior from domain choices. | Meets |
| Practical takeaways | Each scenario ends with a production rule; the article also provides a new-stream checklist and a reproduction guide. | Meets |
| Technically accurate | Official documentation supports product claims; captured target rows support run-derived claims. | Meets |
| Genuine expertise | The article explains the experimental design, assertions, unexpected outcomes, and limitations in the author's voice. | Meets |
| No pure promotion | The article evaluates both strengths and boundaries and contains no commercial pitch. | Meets |
| No documentation rehash | The article acknowledges the existing SQL introduction and contributes an adversarial, measured failure matrix instead of another syntax tutorial. | Meets |
| No low-effort AI copy | The prose passed the outward-facing stop-slop review; the repository supplies the code and evidence behind every material result. | Meets |

### Originality search

The Databricks Technical Blog was searched on 2026-09-01 for the exact title
and combinations of `AUTO CDC`, `Lakeflow`, `SEQUENCE BY`, sequence collision,
wrong clock, `IGNORE NULL UPDATES`, `TRACK HISTORY`, and bitemporal.

The closest article was [From 150 Lines of MERGE INTO to 7 Lines of SQL: AUTO
CDC Comes to Databricks
SQL](https://community.databricks.com/t5/technical-blog/from-150-lines-of-merge-into-to-7-lines-of-sql-auto-cdc-comes-to/ba-p/155355),
published on 2026-04-24. It introduces SQL syntax, compares AUTO CDC with a
manual `MERGE INTO`, and demonstrates a conventional SCD2 pipeline. It does
not publish an adversarial scenario matrix, tied-order analysis, conflicting
clock result, cross-update replay evidence, measured SCD2 noise comparison, or
bitemporal correction timeline.

No Technical Blog article with this article's title or experiment design was
found in the search results. This is evidence of a reasonable search, not a
guarantee that no unindexed or unpublished draft exists.

### Publisher eligibility

The guidelines list Databricks employees as individual or team contributors.
Partner and customer organizations can contribute in their organization's
name. The repository does not establish the author's employment or
organizational submission status, so the author must confirm this requirement
before submission.

## Limits

The experiment does not cover throughput, schema evolution, multi-stream
joins, or bitemporal load behavior. It uses one workspace, one SQL warehouse,
one customer key, and a small deterministic dataset. These limits appear in
the article.
