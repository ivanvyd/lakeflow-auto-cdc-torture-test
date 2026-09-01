"""Capture small AUTO CDC targets through the Databricks SQL API."""

from __future__ import annotations

import json
from dataclasses import dataclass

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

from src.sql_identifiers import qualified_name


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[list[str | None]]


class SqlExecutor:
    def __init__(self, workspace: WorkspaceClient) -> None:
        warehouse = next(iter(workspace.warehouses.list()), None)
        if warehouse is None:
            raise RuntimeError("no SQL warehouse available")
        self._workspace = workspace
        self._warehouse_id = warehouse.id

    def query(self, sql: str) -> QueryResult:
        statement = self._workspace.statement_execution.execute_statement(
            warehouse_id=self._warehouse_id,
            statement=sql,
            wait_timeout="50s",
        )
        if statement.status.state != StatementState.SUCCEEDED:
            raise RuntimeError(f"SQL statement failed: {statement.status.error}")
        schema = statement.manifest.schema if statement.manifest is not None else None
        columns = [column.name for column in schema.columns] if schema is not None else []
        rows = statement.result.data_array if statement.result is not None else []
        return QueryResult(columns=columns, rows=rows or [])


def require_completed_update(
    workspace: WorkspaceClient,
    pipeline_id: str,
    update_id: str,
) -> None:
    response = workspace.pipelines.get_update(
        pipeline_id=pipeline_id,
        update_id=update_id,
    )
    update = response.update
    state = update.state.value if update is not None and update.state is not None else None
    if state != "COMPLETED":
        raise RuntimeError(f"update {update_id} has state {state!r}; expected 'COMPLETED'")


def capture_targets(
    executor: SqlExecutor,
    catalog: str,
    schema: str,
    targets: list[str],
) -> dict[str, dict[str, list]]:
    captured: dict[str, dict[str, list]] = {}
    for target in targets:
        result = executor.query(f"SELECT * FROM {qualified_name(catalog, schema, target)}")
        rows = sorted(
            result.rows,
            key=lambda row: json.dumps(row, default=str, sort_keys=True),
        )
        captured[target] = {"columns": result.columns, "rows": rows}
    return captured
