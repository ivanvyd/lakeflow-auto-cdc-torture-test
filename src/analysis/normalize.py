"""
Normalize the raw `scenario_results` table into a clean summary matrix and
per-scenario CSV/JSON outputs.

Run after `make test`:
  python -m src.analysis.normalize --profile DEFAULT --catalog workspace
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

from src.sql_identifiers import qualified_name

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "results"
RAW_DIR = RESULTS_DIR / "raw"
NORM_DIR = RESULTS_DIR / "normalized"


def _to_bool(v) -> bool:
    """The scenario_results table stores booleans as TRUE/FALSE strings
    (the SDK SQL API doesn't bind Python bools to BOOLEAN columns). Rows
    come back as strings; this normalizer parses them back to Python bools."""
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().upper() in ("TRUE", "1", "T", "YES")


CONFIGURATION_DEPENDENT = {
    "04_wrong_clock_source",
    "05_sparse_b",
    "08_history_b",
}


def classify_result(
    scenario: str,
    ordering_complete: bool,
    business_passed: bool,
) -> str:
    if not ordering_complete:
        return "AMBIGUOUS_ORDER"
    if not business_passed:
        return "BUSINESS_SEMANTICS"
    if scenario in CONFIGURATION_DEPENDENT:
        return "CONFIGURATION_DEPENDENT"
    return "HANDLED"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", default="auto_cdc_torture_test")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    NORM_DIR.mkdir(parents=True, exist_ok=True)

    w = WorkspaceClient(profile=args.profile)
    # Use the SQL warehouse for the result table
    warehouses = list(w.warehouses.list())
    if not warehouses:
        print("no SQL warehouse available", file=sys.stderr)
        sys.exit(1)
    wh_id = warehouses[0].id

    sql = f"SELECT * FROM {qualified_name(args.catalog, args.schema, 'scenario_results')}"
    stmt = w.statement_execution.execute_statement(
        warehouse_id=wh_id,
        statement=sql,
        wait_timeout="50s",
    )
    if stmt.status.state != StatementState.SUCCEEDED:
        print(f"query failed: {stmt.status.error}", file=sys.stderr)
        sys.exit(1)

    columns = [c.name for c in stmt.manifest.schema.columns]
    rows = []
    for chunk in stmt.result.data_array or []:
        rows.append(dict(zip(columns, chunk)))

    out_json = RAW_DIR / "scenario_results.json"
    out_json.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out_json} ({len(rows)} rows)")

    # Per the article's classification scheme, these scenarios are
    # CONFIGURATION_DEPENDENT: the business expectation matches, but only
    # because a non-default configuration was chosen (the right SEQUENCE BY
    # column, IGNORE NULL UPDATES, or TRACK HISTORY ON * EXCEPT).
    classifications: list[dict[str, str]] = []
    for r in rows:
        scenario = r["scenario"]
        configuration = r["configuration"]
        pipeline_completed = _to_bool(r["pipeline_completed"])
        ordering_complete = _to_bool(r["ordering_complete"])
        business_passed = _to_bool(r["business_assertion_passed"])
        target_rows = r["target_rows"]
        history_rows = r["history_rows"]

        classification = classify_result(
            scenario,
            ordering_complete,
            business_passed,
        )

        classifications.append(
            {
                "scenario": scenario,
                "configuration": configuration,
                "pipeline": "GREEN" if pipeline_completed else "RED",
                "correct_state": "YES" if business_passed else "NO",
                "ordering": "COMPLETE" if ordering_complete else "AMBIGUOUS",
                "classification": classification,
                "target_rows": str(target_rows),
                "history_rows": str(history_rows),
            }
        )

    # Sort: 01 → 09 by scenario family, then by configuration within a family.
    classifications.sort(key=lambda c: (c["scenario"][:2], c["scenario"], c["configuration"]))

    out_norm = NORM_DIR / "summary_matrix.json"
    out_norm.write_text(json.dumps(classifications, indent=2), encoding="utf-8")
    print(f"wrote {out_norm}")

    # Markdown table
    md_path = NORM_DIR / "summary_matrix.md"
    lines = [
        "# Summary matrix",
        "",
        "| Scenario | Configuration | Pipeline | Correct state | Ordering | Classification | target rows | history rows |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in classifications:
        lines.append(
            f"| {c['scenario']} | {c['configuration']} | {c['pipeline']} | "
            f"{c['correct_state']} | {c['ordering']} | "
            f"{c['classification']} | {c['target_rows']} | {c['history_rows']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {md_path}")


if __name__ == "__main__":
    main()
