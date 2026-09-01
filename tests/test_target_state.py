from types import SimpleNamespace

import pytest
from databricks.sdk.service.sql import StatementState

from src.analysis.target_state import SqlExecutor


class _Warehouses:
    def list(self):
        return [SimpleNamespace(id="warehouse-id")]


class _StatementExecution:
    def execute_statement(self, **_kwargs):
        return SimpleNamespace(
            status=SimpleNamespace(
                state=StatementState.FAILED,
                error=SimpleNamespace(message="permission denied"),
            )
        )


def test_sql_executor_rejects_failed_statements() -> None:
    workspace = SimpleNamespace(
        warehouses=_Warehouses(),
        statement_execution=_StatementExecution(),
    )

    with pytest.raises(RuntimeError, match="permission denied"):
        SqlExecutor(workspace).query("DROP SCHEMA example")
