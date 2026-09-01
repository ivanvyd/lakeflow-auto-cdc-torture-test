"""
Write one row per scenario target after comparing both experiment phases and
verifying the current workspace state.

Run after a successful pipeline update:
  python -m src.analysis.write_results --profile DEFAULT --catalog workspace
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from databricks.sdk import WorkspaceClient

from src.analysis.target_state import (
    SqlExecutor,
    capture_targets,
    require_completed_update,
)
from src.generators.dispatch import DEFAULT_SCHEMA
from src.sql_identifiers import qualified_name

SCHEMA = DEFAULT_SCHEMA


# Expected states per scenario target.
OBSERVED = [
    # (scenario, configuration, pipeline_green, ordering_complete, business_passed,
    #  expected_text, observed_text, target_rows, history_rows)
    (
        "01_duplicate",
        "s01_duplicate_tgt",
        True,
        True,
        True,
        "Single row, status=ACTIVE; pipeline green",
        "1 row, status=ACTIVE",
        1,
        0,
    ),
    (
        "01_duplicate_replay",
        "s01_duplicate_replay_tgt",
        True,
        True,
        True,
        "Single row, status=ACTIVE; same as scenario 1 base",
        "1 row, status=ACTIVE (replay dedup'd by per-key max)",
        1,
        0,
    ),
    (
        "02_out_of_order",
        "s02_out_of_order_tgt",
        True,
        True,
        True,
        "status=ACTIVE; SCD1 keeps latest by source_sequence",
        "1 row, status=ACTIVE (per-key max on source_sequence=12)",
        1,
        0,
    ),
    (
        "02_out_of_order_scd2",
        "s02_out_of_order_scd2_tgt",
        True,
        True,
        True,
        "Two history rows; ACTIVE is the active version",
        "2 history rows: PENDING@10 closed at 12, ACTIVE@12 current",
        2,
        2,
    ),
    (
        "03_seq_collision_a",
        "s03_seq_collision_a_tgt",
        True,
        False,
        False,
        "No deterministic business state: two different states share source_sequence=10",
        "1 row, status=SUSPENDED in this run; configured order is ambiguous",
        1,
        0,
    ),
    (
        "03_seq_collision_b",
        "s03_seq_collision_b_tgt",
        True,
        False,
        True,
        "status=SUSPENDED, but only if transaction_sequence participates in SEQUENCE BY",
        "1 row, status=SUSPENDED in this run; transaction_sequence is present but not configured",
        1,
        0,
    ),
    (
        "03_seq_collision_b_struct",
        "s03_seq_collision_b_struct_tgt",
        True,
        True,
        True,
        "status=SUSPENDED via composite STRUCT(source_updated_at, transaction_sequence)",
        "1 row, status=SUSPENDED (composite SEQUENCE BY orders by (t, txn) = (0,1) vs (0,2))",
        1,
        0,
    ),
    (
        "04_wrong_clock_ingest",
        "s04_wrong_clock_ingest_tgt",
        True,
        True,
        False,
        "status=ACTIVE; pipeline green; BUSINESS expectation diverges",
        "1 row, status=ACTIVE (ingest-time ordering treats 10:10 as newest, but business intent says 10:05 is newest)",
        1,
        0,
    ),
    (
        "04_wrong_clock_source",
        "s04_wrong_clock_source_tgt",
        True,
        True,
        True,
        "status=SUSPENDED; matches business intent (10:05 is the latest source event)",
        "1 row, status=SUSPENDED (source-time ordering picks 10:05 SUSPENDED)",
        1,
        0,
    ),
    (
        "05_sparse_a",
        "s05_sparse_a_tgt",
        True,
        True,
        False,
        "email NULL after sparse update; default behavior overwrites with NULL",
        "1 row, email=NULL (default: NULL means 'set to null')",
        1,
        0,
    ),
    (
        "05_sparse_b",
        "s05_sparse_b_tgt",
        True,
        True,
        True,
        "email='x@example.com' (kept); city='Istanbul' (updated)",
        "1 row, email='x@example.com' (kept), city='Istanbul' (updated)",
        1,
        0,
    ),
    (
        "06_delete_late_scd1",
        "s06_delete_late_tgt",
        True,
        True,
        True,
        "Row deleted; late seq=18 event is dropped",
        "0 rows (DELETE@20 applied, late seq=18 dropped by per-key max)",
        0,
        0,
    ),
    (
        "06_delete_late_scd2",
        "s06_delete_late_scd2_tgt",
        True,
        True,
        True,
        "History: ACTIVE@17 → SUSPENDED@18 → DELETE@20",
        "2 history rows: ACTIVE@17 closed at 18, SUSPENDED@18 closed at 20 (DELETE)",
        2,
        2,
    ),
    (
        "07_replay_scd1",
        "s07_replay_tgt",
        True,
        True,
        True,
        "Empty target after DELETE at source_sequence=50; pipeline green",
        "0 rows (final DELETE@50 applied; the prior history is overwritten by current state, which is empty)",
        0,
        0,
    ),
    (
        "07_replay_scd2",
        "s07_replay_scd2_tgt",
        True,
        True,
        True,
        "Multiple history rows; final state is closed at __END_AT for seq=50",
        "4 history rows: PENDING[10,20)→ACTIVE(Antalya)[20,30)→ACTIVE(Izmir)[30,40)→SUSPENDED(Ankara)[40,50)",
        4,
        4,
    ),
    (
        "08_history_a",
        "s08_history_a_scd2_tgt",
        True,
        True,
        False,
        "One business-significant history row; operational timestamps should not add versions",
        "51 history rows (every event creates a new version because last_synced_at changes)",
        51,
        51,
    ),
    (
        "08_history_b",
        "s08_history_b_scd2_tgt",
        True,
        True,
        True,
        "A small number of history rows (only business-significant changes)",
        "1 history row (TRACK HISTORY ON * EXCEPT (last_synced_at) suppresses 50 noise-only updates)",
        1,
        1,
    ),
    (
        "09_bitemporal",
        "s09_bitemporal_tgt",
        True,
        True,
        True,
        "Bitemporal history rows with __SYSTEM_START_AT / __SYSTEM_END_AT",
        "5 history rows with both __START_AT/__END_AT and __SYSTEM_START_AT/__SYSTEM_END_AT",
        5,
        5,
    ),
]

CONFIGURATIONS = [row[1] for row in OBSERVED]

# Only these two visible targets should change when the late phase is appended.
# Other staged cases deliberately prove that a replay or an older event leaves
# the visible target unchanged.
EXPECTED_LATE_PHASE_CHANGES = {
    "s02_out_of_order_scd2_tgt",
    "s06_delete_late_scd2_tgt",
}


# Each published observation must satisfy a live query against its target.
# Counts alone are insufficient: several scenarios deliberately have the
# same row count but different business state.
LIVE_ASSERTIONS = {
    "s01_duplicate_tgt": "COUNT_IF(status = 'ACTIVE') = 1",
    "s01_duplicate_replay_tgt": "COUNT_IF(status = 'ACTIVE') = 1",
    "s02_out_of_order_tgt": "COUNT_IF(status = 'ACTIVE') = 1",
    "s02_out_of_order_scd2_tgt": (
        "COUNT_IF(status = 'PENDING' AND __END_AT = 12) = 1 "
        "AND COUNT_IF(status = 'ACTIVE' AND __END_AT IS NULL) = 1"
    ),
    "s03_seq_collision_a_tgt": "COUNT_IF(status = 'SUSPENDED') = 1",
    "s03_seq_collision_b_tgt": "COUNT_IF(status = 'SUSPENDED') = 1",
    "s03_seq_collision_b_struct_tgt": "COUNT_IF(status = 'SUSPENDED') = 1",
    "s04_wrong_clock_ingest_tgt": "COUNT_IF(status = 'ACTIVE') = 1",
    "s04_wrong_clock_source_tgt": "COUNT_IF(status = 'SUSPENDED') = 1",
    "s05_sparse_a_tgt": "COUNT_IF(email IS NULL AND city = 'Istanbul') = 1",
    "s05_sparse_b_tgt": ("COUNT_IF(email = 'x@example.com' AND city = 'Istanbul') = 1"),
    "s06_delete_late_tgt": "TRUE",
    "s06_delete_late_scd2_tgt": (
        "COUNT_IF(status = 'ACTIVE' AND __START_AT = 17 AND __END_AT = 18) = 1 "
        "AND COUNT_IF(status = 'SUSPENDED' AND __START_AT = 18 AND __END_AT = 20) = 1"
    ),
    "s07_replay_tgt": "TRUE",
    "s07_replay_scd2_tgt": (
        "COUNT_IF(status = 'PENDING' AND __START_AT = 10 AND __END_AT = 20) = 1 "
        "AND COUNT_IF(status = 'ACTIVE' AND city = 'Antalya' "
        "AND __START_AT = 20 AND __END_AT = 30) = 1 "
        "AND COUNT_IF(status = 'ACTIVE' AND city = 'Izmir' "
        "AND __START_AT = 30 AND __END_AT = 40) = 1 "
        "AND COUNT_IF(status = 'SUSPENDED' AND city = 'Ankara' "
        "AND __START_AT = 40 AND __END_AT = 50) = 1"
    ),
    "s08_history_a_scd2_tgt": "COUNT_IF(status = 'ACTIVE') = 51",
    "s08_history_b_scd2_tgt": "COUNT_IF(status = 'ACTIVE') = 1",
    "s09_bitemporal_tgt": (
        "COUNT_IF(status = 'PENDING' "
        "AND __START_AT = TIMESTAMP '2026-08-30 10:00:00' "
        "AND __END_AT IS NULL "
        "AND __SYSTEM_START_AT = TIMESTAMP '2026-08-30 10:01:00' "
        "AND __SYSTEM_END_AT = TIMESTAMP '2026-08-30 10:03:00') = 1 "
        "AND COUNT_IF(status = 'PENDING' "
        "AND __START_AT = TIMESTAMP '2026-08-30 10:00:00' "
        "AND __END_AT = TIMESTAMP '2026-08-30 10:02:00' "
        "AND __SYSTEM_START_AT = TIMESTAMP '2026-08-30 10:03:00' "
        "AND __SYSTEM_END_AT IS NULL) = 1 "
        "AND COUNT_IF(status = 'ACTIVE' "
        "AND __START_AT = TIMESTAMP '2026-08-30 10:02:00' "
        "AND __END_AT IS NULL "
        "AND __SYSTEM_START_AT = TIMESTAMP '2026-08-30 10:03:00' "
        "AND __SYSTEM_END_AT = TIMESTAMP '2026-08-30 10:05:00') = 1 "
        "AND COUNT_IF(status = 'ACTIVE' "
        "AND __START_AT = TIMESTAMP '2026-08-30 10:02:00' "
        "AND __END_AT = TIMESTAMP '2026-08-30 10:04:00' "
        "AND __SYSTEM_START_AT = TIMESTAMP '2026-08-30 10:05:00' "
        "AND __SYSTEM_END_AT IS NULL) = 1 "
        "AND COUNT_IF(status = 'SUSPENDED' "
        "AND __START_AT = TIMESTAMP '2026-08-30 10:04:00' "
        "AND __END_AT IS NULL "
        "AND __SYSTEM_START_AT = TIMESTAMP '2026-08-30 10:05:00' "
        "AND __SYSTEM_END_AT IS NULL) = 1"
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", default=SCHEMA)
    parser.add_argument("--pipeline-id", required=True)
    parser.add_argument("--update-id", required=True)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("results/raw/baseline_target_state.json"),
    )
    args = parser.parse_args()

    w = WorkspaceClient(profile=args.profile)
    executor = SqlExecutor(w)

    def exec(sql: str) -> None:
        executor.query(sql)
        time.sleep(0.3)

    try:
        require_completed_update(w, args.pipeline_id, args.update_id)
    except RuntimeError as error:
        raise SystemExit(f"refusing to publish results: {error}") from error

    if not args.baseline.is_file():
        raise SystemExit(f"missing baseline evidence: {args.baseline}")
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    if baseline.get("pipeline_id") != args.pipeline_id:
        raise SystemExit("baseline pipeline id does not match the verified pipeline")
    if baseline.get("update_id") == args.update_id:
        raise SystemExit("baseline and late-phase update ids must differ")

    current_targets = capture_targets(
        executor,
        args.catalog,
        args.schema,
        CONFIGURATIONS,
    )
    baseline_targets = baseline.get("targets", {})
    for configuration in CONFIGURATIONS:
        before = baseline_targets.get(configuration)
        after = current_targets[configuration]
        changed = before != after
        expected_change = configuration in EXPECTED_LATE_PHASE_CHANGES
        if changed != expected_change:
            expectation = "change" if expected_change else "remain unchanged"
            raise SystemExit(
                f"late-phase assertion failed for {configuration}: expected target to {expectation}"
            )
        print(f"phase verified {configuration}: {'changed' if changed else 'unchanged'}")

    verified_rows: list[tuple] = []
    for row in OBSERVED:
        configuration = row[1]
        expected_target_rows = row[7]
        predicate = LIVE_ASSERTIONS[configuration]
        live = executor.query(f"""
            SELECT
              CAST(COUNT(*) AS STRING) AS target_rows,
              CAST(({predicate}) AS STRING) AS state_matches
            FROM {qualified_name(args.catalog, args.schema, configuration)}
        """).rows
        if len(live) != 1:
            raise SystemExit(f"unexpected verification result for {configuration}: {live!r}")
        actual_target_rows = int(live[0][0])
        state_matches = str(live[0][1]).lower() == "true"
        if actual_target_rows != expected_target_rows or not state_matches:
            raise SystemExit(
                f"live assertion failed for {configuration}: "
                f"expected rows={expected_target_rows}, actual rows={actual_target_rows}, "
                f"state_matches={state_matches}"
            )
        verified_rows.append(row)
        print(f"verified {configuration}: rows={actual_target_rows}")

    # Reset the results table for a clean run
    result_table = qualified_name(args.catalog, args.schema, "scenario_results")
    exec(f"DROP TABLE IF EXISTS {result_table}")
    exec(f"""
        CREATE TABLE {result_table} (
          scenario STRING,
          configuration STRING,
          ordering_complete BOOLEAN,
          pipeline_completed BOOLEAN,
          business_assertion_passed BOOLEAN,
          target_rows BIGINT,
          history_rows BIGINT,
          expected STRING,
          observed STRING,
          notes STRING,
          captured_at STRING
        ) USING DELTA
    """)

    now = datetime.now(timezone.utc).isoformat()
    for (
        scenario,
        configuration,
        pipeline_green,
        contract_valid,
        business_passed,
        expected_text,
        observed_text,
        target_rows,
        history_rows,
    ) in verified_rows:
        # Escape single quotes for SQL
        def esc(s: str) -> str:
            return "'" + s.replace("'", "''") + "'"

        sql = f"""
            INSERT INTO {result_table} VALUES (
              {esc(scenario)}, {esc(configuration)}, {str(contract_valid).upper()},
              {str(pipeline_green).upper()}, {str(business_passed).upper()},
              {target_rows}, {history_rows}, {esc(expected_text)},
              {esc(observed_text)}, '', {esc(now)}
            )
        """
        exec(sql)
        print(f"wrote {scenario} / {configuration}")

    # Also persist to local file
    out = (
        Path(__file__).resolve().parent.parent.parent / "results" / "raw" / "scenario_results.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            [
                {
                    "scenario": s,
                    "configuration": c,
                    "pipeline_completed": pg,
                    "ordering_complete": cv,
                    "business_assertion_passed": bp,
                    "target_rows": tr,
                    "history_rows": hr,
                    "expected": e,
                    "observed": o,
                }
                for (s, c, pg, cv, bp, e, o, tr, hr) in verified_rows
            ],
            indent=2,
        )
    )
    state_out = out.parent / "target_state.json"
    state_out.write_text(
        json.dumps(
            {
                "pipeline_id": args.pipeline_id,
                "baseline_update_id": baseline["update_id"],
                "late_phase_update_id": args.update_id,
                "baseline": baseline_targets,
                "after_late_phase": current_targets,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote local {out}")
    print(f"wrote local {state_out}")


if __name__ == "__main__":
    main()
