"""
Cleanup: drop the experiment schema.

The Makefile separately destroys resources managed by the Databricks bundle.
"""

from __future__ import annotations

import argparse

from databricks.sdk import WorkspaceClient

from src.analysis.target_state import SqlExecutor
from src.sql_identifiers import qualified_schema

SAFE_SCHEMA_PREFIX = "auto_cdc_torture"


def validate_cleanup_scope(schema: str, confirmation: str) -> None:
    if schema != confirmation:
        raise ValueError("cleanup confirmation must exactly match --schema")
    if not schema.startswith(SAFE_SCHEMA_PREFIX):
        raise ValueError(
            f"refusing cascading cleanup outside the {SAFE_SCHEMA_PREFIX!r} schema prefix"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", default="auto_cdc_torture_test")
    parser.add_argument("--confirm-schema", required=True)
    args = parser.parse_args()

    validate_cleanup_scope(args.schema, args.confirm_schema)
    w = WorkspaceClient(profile=args.profile)
    SqlExecutor(w).query(
        f"DROP SCHEMA IF EXISTS {qualified_schema(args.catalog, args.schema)} CASCADE"
    )
    print(f"dropped {args.catalog}.{args.schema}")


if __name__ == "__main__":
    main()
