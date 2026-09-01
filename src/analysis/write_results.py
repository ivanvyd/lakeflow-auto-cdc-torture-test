"""Verify both experiment phases and publish measured evidence."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from databricks.sdk import WorkspaceClient

from src.analysis.target_state import SqlExecutor, capture_targets, require_completed_update
from src.scenario_specs import (
    DEFAULT_SCHEMA,
    EXPECTED_LATE_PHASE_CHANGES,
    FLOW_SPECS,
    TARGET_NAMES,
)
from src.sql_identifiers import qualified_name

CONFIGURATIONS = list(TARGET_NAMES)


def validate_baseline_payload(
    baseline: object,
    pipeline_id: str,
    late_update_id: str,
) -> tuple[str, dict]:
    if not isinstance(baseline, dict):
        raise TypeError("baseline evidence must be a JSON object")
    if baseline.get("pipeline_id") != pipeline_id:
        raise ValueError("baseline pipeline id does not match the verified pipeline")
    baseline_update_id = baseline.get("update_id")
    if not isinstance(baseline_update_id, str) or not baseline_update_id:
        raise ValueError("baseline evidence has no valid update id")
    if baseline_update_id == late_update_id:
        raise ValueError("baseline and late-phase update ids must differ")
    baseline_targets = baseline.get("targets")
    if not isinstance(baseline_targets, dict):
        raise TypeError("baseline evidence has no target map")
    missing = sorted(set(TARGET_NAMES) - set(baseline_targets))
    unexpected = sorted(set(baseline_targets) - set(TARGET_NAMES))
    if missing or unexpected:
        raise ValueError(
            "baseline target set does not match configured targets: "
            f"missing={missing}, unexpected={unexpected}"
        )
    return baseline_update_id, baseline_targets


def _escape_sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--pipeline-id", required=True)
    parser.add_argument("--update-id", required=True)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("results/raw/baseline_target_state.json"),
    )
    args = parser.parse_args()

    workspace = WorkspaceClient(profile=args.profile)
    executor = SqlExecutor(workspace)

    def exec_write(sql: str) -> None:
        executor.query(sql)
        time.sleep(0.3)

    try:
        require_completed_update(
            workspace,
            args.pipeline_id,
            args.update_id,
            expected_full_refresh=False,
        )
    except RuntimeError as error:
        raise SystemExit(f"refusing to publish results: {error}") from error

    if not args.baseline.is_file():
        raise SystemExit(f"missing baseline evidence: {args.baseline}")
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    try:
        baseline_update_id, baseline_targets = validate_baseline_payload(
            baseline,
            args.pipeline_id,
            args.update_id,
        )
        require_completed_update(
            workspace,
            args.pipeline_id,
            baseline_update_id,
            expected_full_refresh=True,
        )
    except (TypeError, ValueError, RuntimeError) as error:
        raise SystemExit(f"refusing to publish results: invalid baseline: {error}") from error

    current_targets = capture_targets(
        executor,
        args.catalog,
        args.schema,
        CONFIGURATIONS,
    )
    for configuration in CONFIGURATIONS:
        changed = baseline_targets[configuration] != current_targets[configuration]
        expected_change = configuration in EXPECTED_LATE_PHASE_CHANGES
        if changed != expected_change:
            expectation = "change" if expected_change else "remain unchanged"
            raise SystemExit(
                f"late-phase assertion failed for {configuration}: expected target to {expectation}"
            )
        print(f"phase verified {configuration}: {'changed' if changed else 'unchanged'}")

    for flow in FLOW_SPECS:
        live = executor.query(f"""
            SELECT
              CAST(COUNT(*) AS STRING) AS target_rows,
              CAST(({flow.live_predicate}) AS STRING) AS state_matches
            FROM {qualified_name(args.catalog, args.schema, flow.target)}
        """).rows
        if len(live) != 1:
            raise SystemExit(f"unexpected verification result for {flow.target}: {live!r}")
        actual_target_rows = int(live[0][0])
        state_matches = str(live[0][1]).lower() == "true"
        if actual_target_rows != flow.target_rows or not state_matches:
            raise SystemExit(
                f"live assertion failed for {flow.target}: "
                f"expected rows={flow.target_rows}, actual rows={actual_target_rows}, "
                f"state_matches={state_matches}"
            )
        print(f"verified {flow.target}: rows={actual_target_rows}")

    result_table = qualified_name(args.catalog, args.schema, "scenario_results")
    exec_write(f"DROP TABLE IF EXISTS {result_table}")
    exec_write(f"""
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

    captured_at = datetime.now(timezone.utc).isoformat()
    for flow in FLOW_SPECS:
        values = (
            _escape_sql_string(flow.scenario),
            _escape_sql_string(flow.target),
            str(flow.ordering_complete).upper(),
            "TRUE",
            str(flow.business_passed).upper(),
            str(flow.target_rows),
            str(flow.history_rows),
            _escape_sql_string(flow.expected),
            _escape_sql_string(flow.observed),
            "''",
            _escape_sql_string(captured_at),
        )
        exec_write(f"INSERT INTO {result_table} VALUES ({', '.join(values)})")
        print(f"wrote {flow.scenario} / {flow.target}")

    raw_dir = Path(__file__).resolve().parent.parent.parent / "results" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    results_out = raw_dir / "scenario_results.json"
    results_out.write_text(
        json.dumps(
            [
                {
                    "scenario": flow.scenario,
                    "configuration": flow.target,
                    "pipeline_completed": True,
                    "ordering_complete": flow.ordering_complete,
                    "business_assertion_passed": flow.business_passed,
                    "target_rows": flow.target_rows,
                    "history_rows": flow.history_rows,
                    "expected": flow.expected,
                    "observed": flow.observed,
                }
                for flow in FLOW_SPECS
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    state_out = raw_dir / "target_state.json"
    state_out.write_text(
        json.dumps(
            {
                "pipeline_id": args.pipeline_id,
                "baseline_update_id": baseline_update_id,
                "late_phase_update_id": args.update_id,
                "baseline": baseline_targets,
                "after_late_phase": current_targets,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote local {results_out}")
    print(f"wrote local {state_out}")


if __name__ == "__main__":
    main()
