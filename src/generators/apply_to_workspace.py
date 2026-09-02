"""
Local CLI that uses the Databricks SDK to:
  1. Create the catalog / schema if missing.
  2. Drop and create each source Delta table.
  3. INSERT INTO each source the CDC events for the corresponding scenario.

After this runs, the next pipeline update will read the populated tables
through the @dp.view declarations in `src/pipeline/pipeline.py`.

Usage:
  python -m src.generators.apply_to_workspace --profile DEFAULT --catalog workspace
"""

from __future__ import annotations

import argparse
import time

from databricks.sdk import WorkspaceClient

from src.analysis.target_state import SqlExecutor
from src.generators.dispatch import (
    SOURCE_SCHEMA_DDL,
    _rows_to_insert_sql,
)
from src.scenario_specs import (
    INITIAL_ROWS_BY_SOURCE,
    LATE_ROWS_BY_SOURCE,
    SCENARIO_EVENTS,
    SOURCE_TABLE_FOR_SCENARIO,
)
from src.sql_identifiers import qualified_name, quote_identifier


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", default="auto_cdc_torture_test")
    parser.add_argument("--scenario", choices=sorted(SCENARIO_EVENTS), default=None)
    parser.add_argument("--phase", choices=("initial", "late"), default="initial")
    args = parser.parse_args()

    w = WorkspaceClient(profile=args.profile)
    executor = SqlExecutor(w)

    def exec(sql: str) -> None:
        executor.query(sql)
        # Rate-limit between warehouse statements.
        time.sleep(0.3)

    catalog = quote_identifier(args.catalog, "catalog")
    schema = quote_identifier(args.schema, "schema")
    exec(f"CREATE CATALOG IF NOT EXISTS {catalog}")
    exec(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

    rows_by_source = INITIAL_ROWS_BY_SOURCE if args.phase == "initial" else LATE_ROWS_BY_SOURCE
    selected_sources = (
        SOURCE_TABLE_FOR_SCENARIO[args.scenario]
        if args.scenario is not None
        else rows_by_source.keys()
    )
    for source in selected_sources:
        rows = rows_by_source.get(source, [])
        if args.phase == "initial":
            fqn = qualified_name(args.catalog, args.schema, source)
            exec(f"DROP TABLE IF EXISTS {fqn}")
            exec(SOURCE_SCHEMA_DDL.format(fqn=fqn))
        elif not rows:
            continue
        else:
            fqn = qualified_name(args.catalog, args.schema, source)
        if rows:
            exec(_rows_to_insert_sql(fqn, rows))
            print(f"{args.phase}: wrote {len(rows)} rows to {fqn}")


if __name__ == "__main__":
    main()
