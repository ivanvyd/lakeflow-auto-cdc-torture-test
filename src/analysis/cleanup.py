"""
Cleanup: drop the experiment schema.

The Makefile separately destroys resources managed by the Databricks bundle.
"""

from __future__ import annotations

import argparse

from databricks.sdk import WorkspaceClient

from src.analysis.target_state import SqlExecutor
from src.sql_identifiers import qualified_schema


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", default="auto_cdc_torture_test")
    args = parser.parse_args()

    w = WorkspaceClient(profile=args.profile)
    SqlExecutor(w).query(
        f"DROP SCHEMA IF EXISTS {qualified_schema(args.catalog, args.schema)} CASCADE"
    )
    print(f"dropped {args.catalog}.{args.schema}")


if __name__ == "__main__":
    main()
