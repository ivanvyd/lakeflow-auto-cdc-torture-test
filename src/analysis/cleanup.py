"""
Cleanup: drop the experiment schema.

The Makefile separately destroys resources managed by the Databricks bundle.
"""

from __future__ import annotations

import argparse
import sys

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import DatabricksError

from src.sql_identifiers import qualified_schema


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", default="auto_cdc_torture_test")
    args = parser.parse_args()

    w = WorkspaceClient(profile=args.profile)
    warehouses = list(w.warehouses.list())
    if not warehouses:
        print("no SQL warehouse available", file=sys.stderr)
        raise SystemExit(1)
    warehouse_id = warehouses[0].id

    try:
        w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=f"DROP SCHEMA IF EXISTS {qualified_schema(args.catalog, args.schema)} CASCADE",
            wait_timeout="60s",
        )
        print(f"dropped {args.catalog}.{args.schema}")
    except DatabricksError as e:
        print(f"failed to drop schema: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
