"""Capture target state after the initial full refresh."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from databricks.sdk import WorkspaceClient

from src.analysis.target_state import (
    SqlExecutor,
    capture_targets,
    require_completed_update,
)
from src.scenario_specs import TARGET_NAMES

DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent.parent / "results" / "raw" / "baseline_target_state.json"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", default="auto_cdc_torture_test")
    parser.add_argument("--pipeline-id", required=True)
    parser.add_argument("--update-id", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    workspace = WorkspaceClient(profile=args.profile)
    require_completed_update(
        workspace,
        args.pipeline_id,
        args.update_id,
        expected_full_refresh=True,
    )
    targets = capture_targets(
        SqlExecutor(workspace),
        args.catalog,
        args.schema,
        list(TARGET_NAMES),
    )
    payload = {
        "pipeline_id": args.pipeline_id,
        "update_id": args.update_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "targets": targets,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"captured baseline for {len(targets)} targets in {args.output}")


if __name__ == "__main__":
    main()
