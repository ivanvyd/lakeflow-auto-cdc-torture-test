# All 18 Lakeflow AUTO CDC configurations went green. Five failed my ship check

![Eighteen CDC event slips follow one sequence thread; five peel away into business-rule and ordering failures.](https://raw.githubusercontent.com/ivanvyd/lakeflow-auto-cdc-torture-test/main/article/media/lakeflow-auto-cdc-torture-test-hero.png)

Change data capture (CDC) turns source inserts, updates, and deletes into an event stream that keeps a target table current. CDC gets harder when events arrive late, share a sequence value, disagree about time, or omit fields.

I built nine small failure cases around those problems and ran them through 18 Lakeflow Declarative Pipelines `AUTO CDC` configurations. Every pipeline completed green. Five still needed intervention before production: three violated the experiment's business rule, and two had tied sequence values with no documented winner.

The sharpest example is scenario 4. Ordering by ingestion time preserved `ACTIVE`; the business clock required `SUSPENDED`. Both configurations ran successfully.

**[Run the experiment](https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test)** or **[audit every claim](https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test/blob/main/article/fact-check.md)**.

This is an independent engineering experiment, not official Databricks guidance. I am happy to discuss the results and hear suggestions, feedback, or failure cases that this suite does not yet cover.

---

## The failures behind the experiment

I chose these cases because I have debugged CDC streams with conflicting clocks, late replays, and sparse updates that erased values. Each scenario has a small input, an explicit business expectation, and a verifier that captures the resulting target rows.

The goal is to separate what `AUTO CDC` handles from decisions that still belong to the source contract. If a source cannot provide a complete order or clear update semantics, the fix may belong upstream.

Each claim below points to one of two sources:

1. A measured row in `results/normalized/summary_matrix.md` (from `results/raw/scenario_results.json`).
2. A passage in `docs/sources.md` from the official Databricks documentation.

The pipeline lives in [`src/pipeline/pipeline.py`](https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test/blob/main/src/pipeline/pipeline.py), and the event generators live in [`src/generators/dispatch.py`](https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test/blob/main/src/generators/dispatch.py). The [reproduction guide](https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test/blob/main/docs/reproduction.md) and [claim-by-claim evidence ledger](https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test/blob/main/article/fact-check.md) contain the operational detail. To rerun everything, use `make setup && make test && make results`.

---

## Results at a glance

| Outcome | Configurations | What you should do |
|---|---:|---|
| Handled | 10 | Keep the complete sequence rule and test it against your source. |
| Configuration-dependent | 3 | Set the documented option that matches your business rule. |
| Business semantics | 3 | Change the chosen clock, NULL meaning, or history policy. |
| Ambiguous order | 2 | Add a source-side tie-breaker before trusting the result. |

Read scenario 4 first if your source has both business and ingestion timestamps. Scenario 3 covers tied sequence values. Scenarios 5 and 8 cover defaults that can change business state or inflate history.

---

## Five green results I would not ship

| Configuration | Measured risk | Production action |
|---|---|---|
| 3A Sequence collision | Two business states shared one sequence value; the documented contract does not choose a winner. | Reject tied values or expose a stable source-side tie-breaker. |
| 3B Tie-breaker not configured | The source supplied `transaction_sequence`, but the flow ignored it. The measured state matched while the order remained incomplete. | Configure a composite `SEQUENCE BY`. |
| 4A Ingestion-time order | The target kept `ACTIVE`; business time required `SUSPENDED`. | Order by the timestamp that defines business recency. |
| 5A Default NULL handling | A sparse update replaced the existing email with NULL. | Define NULL semantics and enable `IGNORE NULL UPDATES` when NULL means absent. |
| 8A Track every column | Fifty sync-timestamp updates created 51 SCD2 history rows. | Exclude operational metadata from history tracking. |

The other 13 configurations matched the experiment's business rule under a complete order and, where required, a documented option.

---

## How the experiment is wired

### Topology

```
generator (Python)        materializer (Databricks SDK)
    │                              │
    ▼                              ▼
  Delta source table    ──►   @dp.view (readStream)
  (workspace.auto_cdc_torture_test.sNN_xxx_src)
                                 │
                                 ▼
                          AUTO CDC flow
                                 │
                                 ▼
                   workspace.auto_cdc_torture_test.sNN_xxx_tgt
```

- The materializer recreates the source tables for the baseline. It appends the withheld late and replay rows before update 2.
- A `@dp.view` wraps each source and calls `readStream.table(...)`. AUTO CDC requires a streaming source; it rejects `read` (batch).
- Each AUTO CDC flow declares its target schema, keys, `SEQUENCE BY` column, delete rule, and storage type.

### What I assert

The verifier records three fields for each scenario:

| Field | Meaning |
|---|---|
| `ordering_complete` | Does the configured `SEQUENCE BY` order rows with different business states without ties? |
| `business_assertion_passed`   | Did the resulting target match the *domain*'s expectation? |
| `target_rows` / `history_rows` | The measured counts in the target table. |

The classification combines ordering completeness, business correctness, and the need for a non-default option:

- `HANDLED`: ordering is complete and AUTO CDC produces the expected state.
- `CONFIGURATION_DEPENDENT`: business state matches with a non-default configuration.
- `BUSINESS_SEMANTICS`: ordering is complete and the pipeline is green, but the chosen semantics produce the wrong business state.
- `AMBIGUOUS_ORDER`: two different business states share the same configured sequence value. The run records the observed state but does not treat it as portable behavior.

---

## Scenario 1: exact duplicate

The source delivers one CDC event twice with the same key, `source_sequence`, and payload.

```
source_sequence: 10
status: ACTIVE
```

The documentation does not define conflict resolution for equal `SEQUENCE BY` values. Here, the duplicate payloads are identical, so either copy produces the same current state.

The target contains 1 row with `status=ACTIVE`. **HANDLED.**

The replay variant sends the second copy after the baseline update and runs the pipeline again. The target remains byte-for-byte equal to the baseline. This shows stable visible state for an identical replay; it does not prove transactional deduplication.

---

## Scenario 2: out-of-order delivery

A two-event CDC stream crosses two pipeline updates in reverse business order:

```
Logical:   seq=10 PENDING,  then seq=12 ACTIVE.
Update 1:  seq=12 ACTIVE.
Update 2:  seq=10 PENDING arrives late.
```

`SEQUENCE BY` defines logical event order. In the official SCD1 example, Databricks drops a late update whose sequence value is smaller than the value already applied. SCD2 keeps history, so it treats that late row differently.

The SCD1 target contains 1 row with `status=ACTIVE`. **HANDLED.**

The SCD2 target, configured with `TRACK HISTORY ON * EXCEPT (last_synced_at)`, contains 2 history rows: `PENDING@10` closed at `__END_AT=12`, and `ACTIVE@12` current. **HANDLED.**

The saved baseline makes the difference visible. SCD1 remains unchanged after update 2. SCD2 grows from one row to two and inserts the late event as a closed version.

---

## Scenario 3: sequence collision

Two events have the same key and `source_sequence`, but different business states.

### 3A: no tie-breaker

```
seq=10  status=ACTIVE
seq=10  status=SUSPENDED        (same source_sequence, different state)
```

The configured order is incomplete. [Databricks documents `SEQUENCE BY`](https://learn.microsoft.com/en-us/azure/databricks/ldp/developer/ldp-sql-ref-apply-changes-into#parameters) as the logical order of CDC events and recommends a `STRUCT` when one field cannot break ties. It does not document which payload wins when two different states share the same configured value.

This run produced 1 row with `status=SUSPENDED`. Classification: **AMBIGUOUS_ORDER.** The observation does not establish a portable tie-resolution rule.

### 3B: legitimate source-side tie-breaker

```
seq=10  txn=1   status=ACTIVE
seq=10  txn=2   status=SUSPENDED
```

`source_sequence` stays constant, while `transaction_sequence` provides the actual source order. AUTO CDC cannot use that tie-breaker unless the flow includes it.

The target contains 1 row with `status=SUSPENDED`. Because `SEQUENCE BY source_sequence` ignores `transaction_sequence`, the order remains incomplete. Classification: **AMBIGUOUS_ORDER.** The next configuration uses the available tie-breaker.

### 3B-struct: composite `SEQUENCE BY` via `STRUCT`

This configuration uses the same rows as 3B, but sets `SEQUENCE BY` to `F.struct(F.col("source_updated_at"), F.col("transaction_sequence"))`. The composite key gives AUTO CDC the missing tie-breaker.

The target contains 1 row with `status=SUSPENDED`. **HANDLED.**

This is the documented way to encode a source-side tie-breaker. Use a composite when one column lacks the required resolution.

**Production rule:** reject tied sequence values at ingestion or include a stable tie-breaker in `SEQUENCE BY`.

Databricks documents `STRUCT(timestamp_col, id_col)` for composite sequencing: it orders by the first field and uses later fields to break ties.

---

## Scenario 4: the wrong clock

Two source events:

```
10:00 source time   ACTIVE
10:05 source time   SUSPENDED
```

Their recorded ingestion timestamps reverse the business order:

```
10:05 has ingested_at=10:06
10:00 has ingested_at=10:10
```

In this scenario, source-event time defines the newest business state. The `ingested_at` column records arrival order. Using each column in `SEQUENCE BY` produces a different answer.

### 4-ingest (SEQUENCE BY ingested_at)

The flow picks 10:10 because it has the latest `ingested_at`. The final state is `ACTIVE`, which does not match the business expectation. Classification: `BUSINESS_SEMANTICS`.

### 4-source (SEQUENCE BY source_updated_at)

The flow picks the event at 10:05 source time. The final state is `SUSPENDED`, which matches the business expectation. Classification: `CONFIGURATION_DEPENDENT`.

AUTO CDC cannot choose the authoritative clock. If `source_updated_at` defines "newer" for the business, use it in `SEQUENCE BY`. Ingestion time records arrival order, which can diverge during batching, retries, and backfills.

![Two AUTO CDC targets show that ingestion time misses the business expectation while source time matches it.](https://raw.githubusercontent.com/ivanvyd/lakeflow-auto-cdc-torture-test/main/results/figures/wrong_clock.png)

The flow, data, and target schema are identical. Only `SEQUENCE BY` changes, and the resulting state changes with it.

**Production rule:** choose the clock that defines business recency. Keep ingestion time for arrival analysis unless arrival order is the business rule.

---

## Scenario 5: sparse update / NULL semantics

A customer starts with `email='x@example.com'`. The next event changes `city` to `'Istanbul'` and sends `email=NULL`. That NULL can mean either:

1. Set `email` to `NULL`.
2. Keep the existing email because the field was absent from a sparse update.

### 5A: default

The target becomes `email=NULL`, `city='Istanbul'`. The pipeline succeeds, but the scenario expects interpretation 2. Classification: `BUSINESS_SEMANTICS`.

### 5B: `IGNORE NULL UPDATES`

The target keeps `email='x@example.com'` and updates `city` to `'Istanbul'`. **HANDLED.** This option implements interpretation 2.

[Databricks documents that `IGNORE NULL UPDATES`](https://learn.microsoft.com/en-us/azure/databricks/ldp/developer/ldp-python-ref-apply-changes#parameters) retains an existing target value when the corresponding incoming value is `NULL`; without it, the Python API defaults to overwriting the target value with `NULL`.

Use `IGNORE NULL UPDATES` when NULL means "absent." Leave it off when NULL means "set the value to NULL." Scenario 5 measures both outcomes.

**Production rule:** make NULL semantics part of the source contract before you select the AUTO CDC option.

---

## Scenario 6: delete, then a late older event

```
seq=17   ACTIVE
seq=20   DELETE
seq=18   SUSPENDED     (arrives last)
```

Update 1 processes `seq=17` and the delete at `seq=20`. Update 2 appends the older event at `seq=18`.

### 6-scd1 (SCD1)

The DELETE at `seq=20` remains current when the older `seq=18` event arrives. The final SCD1 target is empty. **HANDLED.**

### 6-scd2 (SCD2 with `TRACK HISTORY ON * EXCEPT`)

SCD2 inserts late `seq=18` into its logical position between 17 and 20. The history is `ACTIVE@17` → `SUSPENDED@18` → `DELETE@20`; the DELETE closes the active row at `__END_AT=20`. **HANDLED.**

In both late-event scenarios, the older event leaves SCD1 current state unchanged but enters SCD2 history. Storage type changes what the target retains.

---

## Scenario 7: full replay

The first update processes a complete customer lifecycle:

```
seq=10  PENDING
seq=20  ACTIVE   (Antalya)
seq=30  ACTIVE   (Izmir)
seq=40  SUSPENDED (Ankara)
seq=50  DELETE
```

### 7-scd1

Update 2 appends the same five rows again. The SCD1 target is empty before and after replay. **HANDLED.**

### 7-scd2

Before replay, the SCD2 target contains four rows: `PENDING[10,20) → ACTIVE(Antalya)[20,30) → ACTIVE(Izmir)[30,40) → SUSPENDED(Ankara)[40,50)`. The columns and rows remain identical after replay. **HANDLED.**

For SCD1, the replay check compares current state. For SCD2, it compares the complete visible history.

---

## Scenario 8: SCD2 history noise

A customer receives 50 updates. `last_synced_at` changes on every source read, while all business fields remain constant.

### 8A: track every column

The default SCD2 flow treats each new `last_synced_at` value as a change and creates 51 history rows. The experiment only considers business-field changes meaningful. **BUSINESS_SEMANTICS.**

### 8B: `TRACK HISTORY ON * EXCEPT (last_synced_at)`

Excluding `last_synced_at` from history tracking leaves 1 history row: the initial insert. The 50 operational updates do not create new versions. **CONFIGURATION_DEPENDENT.**

[Databricks documents `TRACK HISTORY ON * EXCEPT`](https://learn.microsoft.com/en-us/azure/databricks/ldp/developer/ldp-sql-ref-apply-changes-into#parameters) for excluding columns from history tracking.

Many CDC sources update operational timestamps on each sync. Default SCD2 tracking records each change as a new version, so choose the columns that represent business history before deploying the flow.

**Production rule:** exclude sync metadata from history tracking unless auditors need each operational change as a business version.

![Tracking every column produces 51 SCD2 rows; excluding last_synced_at produces one.](https://raw.githubusercontent.com/ivanvyd/lakeflow-auto-cdc-torture-test/main/results/figures/scd2_history_noise.png)

---

## Scenario 9: bitemporal (Beta)

This scenario sends three events with different business and system times. The flow uses `system_sequence_by="ingested_at"` and `stored_as_scd_type="bitemporal"`.

The target table carries *two* pairs of timestamps:

- `__START_AT` / `__END_AT`: business time, derived from `SEQUENCE BY` (`source_updated_at`).
- `__SYSTEM_START_AT` / `__SYSTEM_END_AT`: system time, derived from `SYSTEM SEQUENCE BY` (`ingested_at`).

The target contains 5 history rows with both timestamp pairs populated. **HANDLED.**

![Five measured bitemporal rows show original and corrected beliefs across three system times.](https://raw.githubusercontent.com/ivanvyd/lakeflow-auto-cdc-torture-test/main/results/figures/bitemporal_timeline.png)

Later events revise what the system knew about earlier valid-time intervals. Three events arrive at system times 60s, 180s, and 300s:

- Event 1 writes a PENDING belief with an open valid-time interval.
- Event 2 closes that belief in system time, writes a corrected PENDING interval ending at business time 120s, and adds ACTIVE.
- Event 3 closes the original ACTIVE belief in system time, writes a corrected ACTIVE interval ending at business time 240s, and adds SUSPENDED.

The target closes the system-time interval for each original belief and writes the correction as a new open row. `target_state.json` contains all five measured rows, and the figure reads from that capture.

[`SYSTEM SEQUENCE BY` applies to bitemporal storage](https://learn.microsoft.com/en-us/azure/databricks/ldp/developer/ldp-sql-ref-apply-changes-into#parameters), which Databricks documents as Beta. Unlike plain SCD2, it can preserve what the system knew at an earlier time after a correction. Consider bitemporal storage when valid time differs from ingest time and late corrections must remain auditable.

---

## Summary matrix

| Configuration | Pipeline | Business state | Ordering | Outcome |
|---|---|---|---|---|
| 1A Exact duplicate | Green | Yes | Complete | Handled |
| 1B Duplicate after baseline | Green | Yes | Complete | Handled |
| 2A Out of order, SCD1 | Green | Yes | Complete | Handled |
| 2B Out of order, SCD2 | Green | Yes | Complete | Handled |
| 3A Sequence collision | Green | No | Ambiguous | Ambiguous order |
| 3B Tie-breaker not configured | Green | Yes | Ambiguous | Ambiguous order |
| 3C Composite sequence | Green | Yes | Complete | Handled |
| 4A Ingestion-time order | Green | No | Complete | Business semantics |
| 4B Source-time order | Green | Yes | Complete | Configuration-dependent |
| 5A Default NULL handling | Green | No | Complete | Business semantics |
| 5B Ignore NULL updates | Green | Yes | Complete | Configuration-dependent |
| 6A Delete then late event, SCD1 | Green | Yes | Complete | Handled |
| 6B Delete then late event, SCD2 | Green | Yes | Complete | Handled |
| 7A Full replay, SCD1 | Green | Yes | Complete | Handled |
| 7B Full replay, SCD2 | Green | Yes | Complete | Handled |
| 8A Track every column | Green | No | Complete | Business semantics |
| 8B Exclude sync timestamp | Green | Yes | Complete | Configuration-dependent |
| 9 Bitemporal history | Green | Yes | Complete | Handled |

![All 18 measured configurations grouped by handled, configuration-dependent, business-semantics, and ambiguous-order outcomes.](https://raw.githubusercontent.com/ivanvyd/lakeflow-auto-cdc-torture-test/main/results/figures/summary_matrix.png)

The machine-readable matrix is in [`results/normalized/summary_matrix.json`](https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test/blob/main/results/normalized/summary_matrix.json), with the captured target rows in [`results/raw/target_state.json`](https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test/blob/main/results/raw/target_state.json).

---

## AUTO CDC guarantees and boundaries

The results fall into three groups: documented behavior, observations from this run, and business rules the platform cannot choose.

### Documented platform behavior

- `SEQUENCE BY` defines logical event order and can use a `STRUCT` for deterministic tie-breaking.
- AUTO CDC handles out-of-sequence input. The official SCD1 example drops an older late update; SCD2 preserves ordered history.
- `IGNORE NULL UPDATES` keeps existing values when an UPDATE event nulls them out.
- `APPLY AS DELETE WHEN` translates matching events into deletes; SCD2 uses temporary tombstones when handling out-of-order deletes.
- `TRACK HISTORY ON * EXCEPT (col_list)` lets you opt columns out of triggering new SCD2 history rows.
- `SYSTEM SEQUENCE BY` is supported in bitemporal storage (Beta).

### Observed in this two-phase run

The documentation does not promise these exact target snapshots. The checked-in before-and-after evidence records what happened in this run.

- The identical replay in scenario 1 leaves visible SCD1 state unchanged.
- The late rows in scenarios 2 and 6 leave SCD1 unchanged and add closed versions to SCD2.
- Replaying scenario 7's five-event lifecycle leaves both the SCD1 target and the complete SCD2 target unchanged.

### Rules AUTO CDC cannot choose

- Which clock defines "newest." The pipeline follows the `SEQUENCE BY` column, even when that column does not match business time. (Scenario 4.)
- How to order different states with the same configured sequence value. The documentation explains how to add a composite tie-breaker, but does not define a winner for unresolved ties. (Scenario 3.)
- Whether NULL means "set to NULL" or "field absent." The default sets the target value to NULL. (Scenario 5.)
- Which column changes deserve an SCD2 version. By default, every tracked column can create a row. (Scenario 8.)

---

## Where the boundary is

The source contract determines where AUTO CDC fits:

1. **The sequence is complete.** One column or composite orders business states without ties, and NULL has a defined meaning. AUTO CDC can produce the required SCD1 or SCD2 target without custom merge code.

2. **A documented option expresses the missing rule.** Composite `SEQUENCE BY`, `IGNORE NULL UPDATES`, and `TRACK HISTORY ON * EXCEPT` cover the variations tested here.

3. **The source cannot express the required rule.** If multiple writers produce the same sequence value without a tie-breaker, enforce ordering upstream. If the domain needs custom merging for deletes or late updates, use an application-controlled stream processor such as Spark Structured Streaming or Flink.

## What I check first, on a new AUTO CDC stream

Before I deploy a new AUTO CDC stream, I check four things:

1. **Choose `SEQUENCE BY` from the business definition of "newer."** Use source time when it carries that meaning. Ingestion time records arrival and may diverge during batching, retries, or backfills. See scenario 4.
2. **Look for duplicate sequence values per key.** If two events for the same `customer_id` can share a `source_sequence`, fix the order upstream or expose a tie-breaker through a composite `STRUCT`. See scenario 3.
3. **Define NULL.** If a sparse row uses NULL to mean "field absent," enable `IGNORE NULL UPDATES`. The default in scenario 5A overwrote the existing value.
4. **Choose SCD1 or SCD2 before writing the flow.** They retain different state for late events and replays. For SCD2, exclude operational timestamps with `TRACK HISTORY ON * EXCEPT` when those timestamps should not create history. See scenarios 2, 7, and 8.

Use bitemporal storage when source "as-of" time differs from ingest time and you need both histories. Use a streaming job when the domain requires custom merging of deletes and late updates.

---

## What I did not test

- This is a small correctness suite, not a volume test. Backpressure, checkpointing, and large `__END_AT` joins are out of scope.
- The schemas remain stable, so the suite does not cover partial schema evolution.
- The suite does not cover multi-stream joins, such as customer data joined to late-arriving orders. Those semantics depend on the surrounding pipeline.
- The suite does not test `bitemporal` mode under load. Databricks documents the mode as Beta.

The repository issue tracker is the place to request partial schema evolution, multi-stream joins, or large-scale throughput tests.

---

## Reproduction

Run the experiment from a fresh clone:

```bash
databricks auth login --host https://<your-workspace>.cloud.databricks.com --profile DEFAULT
git clone https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test.git
cd lakeflow-auto-cdc-torture-test
make setup      # validate and deploy the bundle
make test       # full refresh, capture baseline, append late rows, incremental update, verify
make results    # regenerate the summary matrix and figures
```

See `docs/reproduction.md` for the full guide, `docs/sources.md` for the documentation sources, and `article/fact-check.md` for the claim-by-claim evidence.

## Verification (last full end-to-end run)

The latest evidence comes from pipeline `1ff99f04-078f-4c91-97e3-f06ad7614f7f`. Full-refresh update `76337b92-46fd-445d-b929-7a85aa038471` established the baseline. Incremental update `d14e5ff1-b840-4e14-affd-902ec98f9fdf` processed the late and replay rows. Both completed.

`capture_baseline.py` saved every target after the full refresh, and `write_results.py` captured them again after the incremental update. Sixteen targets remained identical; the two expected SCD2 histories changed. The verifier checked row counts and scenario-specific state predicates for all 18 targets. Scenario 9 validates all five valid-time and system-time intervals, not only the row count. The final classification is 10 `HANDLED`, 3 `CONFIGURATION_DEPENDENT`, 3 `BUSINESS_SEMANTICS`, and 2 `AMBIGUOUS_ORDER`.

The checked-in evidence includes `baseline_target_state.json`, `target_state.json`, the 18-row summary, and four figures. The bitemporal figure reads the captured rows. For the release run, I used a clean checkout, installed the pinned dependencies in a new virtual environment, and repeated `setup`, `test`, and `results`.

## Test your own failure mode

Clone the repository and replace one generator with events from your source. Encode the expected target state as a predicate, then run the baseline and late phase as separate pipeline updates.

If the suite misses your case, [open an issue](https://github.com/ivanvyd/lakeflow-auto-cdc-torture-test/issues/new) with the source rows, `SEQUENCE BY` expression, storage type, expected target, and observed target. That is enough to add a reproducible regression scenario.
