# Sources

Each entry records a title, URL, access date (2026-09-01), and the fact it supports.
All AUTO CDC facts in the article trace back to one of these sources.

## Databricks / Microsoft Learn official documentation (canonical)

| # | Title | URL | Supports |
|---|-------|-----|----------|
| D1 | The AUTO CDC APIs: Simplify change data capture with pipelines | https://learn.microsoft.com/en-us/azure/databricks/ldp/cdc | API name; `AUTO CDC` vs `AUTO CDC FROM SNAPSHOT`; SCD1/SCD2/bitemporal; composite `SEQUENCE BY` via `STRUCT`; out-of-order handling; `NULL` sequence values not supported; `__START_AT` / `__END_AT`; change-data feed from a target. |
| D2 | AUTO CDC INTO (pipelines) — SQL reference | https://learn.microsoft.com/en-us/azure/databricks/ldp/developer/ldp-sql-ref-apply-changes-into | Full `CREATE FLOW ... AS AUTO CDC INTO` SQL syntax; every clause (KEYS, IGNORE NULL UPDATES ON ... / ON * EXCEPT, APPLY AS DELETE WHEN, APPLY AS TRUNCATE WHEN, SEQUENCE BY, SYSTEM SEQUENCE BY, COLUMNS, STORED AS, TRACK HISTORY ON ..., COLUMNS TO UPDATE). `SYSTEM SEQUENCE BY` documented as part of **Beta** bitemporal processing. |
| D3 | create_auto_cdc_flow — Python reference | https://learn.microsoft.com/en-us/azure/databricks/ldp/developer/ldp-python-ref-apply-changes | Full Python `dp.create_auto_cdc_flow()` signature with every parameter: `sequence_by` (string, col(), or struct()), `system_sequence_by` (bitemporal only), `ignore_null_updates`, `ignore_null_updates_column_list`, `ignore_null_updates_except_column_list`, `columns_to_update`, `apply_as_deletes`, `apply_as_truncates`, `column_list` / `except_column_list`, `stored_as_scd_type`, `track_history_column_list` / `track_history_except_column_list`, `name`, `once`. |
| D4 | Advanced AUTO CDC topics | https://learn.microsoft.com/en-us/azure/databricks/ldp/cdc-advanced | Partial update methods (`IGNORE NULL UPDATES ON` vs `COLUMNS TO UPDATE`); bitemporal `__SYSTEM_START_AT` / `__SYSTEM_END_AT`; metrics captured (`num_upserted_rows`, `num_deleted_rows`); internal backing table `__apply_changes_storage_<target>`; Hive metastore view. |
| D5 | Databricks Lakeflow pipelines — AUTO CDC conceptual page (older URL) | https://docs.databricks.com/aws/en/dlt/auto-cdc | Cross-references confirm terminology "Lakeflow pipelines" (current) vs historical "Delta Live Tables" / "DLT". |

## Operational facts from documentation (used directly in the article)

- **Pipeline edition requirement**: AUTO CDC requires serverless Lakeflow pipelines or the Lakeflow pipelines Pro/Advanced edition. Source: D1.
- **AUTO CDC FROM SNAPSHOT** is Python-only. Source: D1.
- **`SEQUENCE BY` constraint**: must be a sortable data type. `NULL` sequencing values are not supported. Source: D1 Limitations section.
- **Composite `SEQUENCE BY`**: `STRUCT(col1, col2, ...)`, ordering by first field, then second field as tie-breaker. Sources: D1, D2, D3.
- **Out-of-order handling** (canonical example): "The last UPDATE operations arrive late and are dropped from the target table." Source: D1 worked example — user 125's UPDATE at `sequenceNum=5` is overridden by `sequenceNum=6` already applied.
- **Tombstone retention**: SCD type 2 retains deleted rows as tombstones under the underlying Delta table and uses a view in the metastore that filters them. Source: D2 (`APPLY AS DELETE WHEN` parameter). The retention interval is two days by default and can be configured via the table property `pipelines.cdc.tombstoneGCThresholdInSeconds`. Source: D3 (`apply_as_deletes` parameter). **This table property is documented in D3 but not advertised in the conceptual AUTO CDC page — we treat it as officially documented but do not depend on it for any of our main experiments.** Out-of-order Auto Loader sources must size the threshold to exceed maximum expected delay.
- **Truncate**: `APPLY AS TRUNCATE WHEN` only works with SCD type 1. Source: D2, D3.
- **`SYSTEM SEQUENCE BY`**: only with `STORED AS BITEMPORAL`, currently Beta. Source: D2, D3, D4. → Optional 9th experiment in the spec is therefore reframed as a small bitemporal demo.
- **`TRACK HISTORY ON * EXCEPT (cols)`**: SCD type 2 only. Source: D2, D3.
- **Default null handling**: by default, `NULL` in an update overwrites the existing value. `IGNORE NULL UPDATES` and its `ON` variants and `COLUMNS TO UPDATE` are the supported ways to treat null as "no change." Source: D2, D3, D4.
- **Internal storage**: For Hive metastore targets, an `__apply_changes_storage_<target>` backing table holds the raw CDC state; query the view to read results. Source: D4. (Not relevant for Unity Catalog — we publish to Unity Catalog so the target is the streaming table itself.)

## Access date

All Microsoft Learn and Databricks URLs above were checked on **2026-09-01**. The main AUTO CDC page reported a last-updated date of 2026-07-15 during this review.

## What we deliberately did **not** depend on

- The exact tombstone GC retention table property — labeled in the article as documented but operational, not part of the core AUTO CDC contract.
- Any Spark / Delta configuration that is not exposed via the documented API surface above.
- `MERGE INTO`-style behavior, since the spec requires AUTO CDC only.
