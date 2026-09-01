from types import SimpleNamespace

import pytest
from databricks.sdk.service.sql import StatementState

from src.analysis.target_state import SqlExecutor


class _Warehouses:
    def list(self):
        return [SimpleNamespace(id="warehouse-id")]


class _StatementExecution:
    def __init__(self, state: StatementState) -> None:
        self._state = state

    def execute_statement(self, **_kwargs):
        return SimpleNamespace(
            status=SimpleNamespace(
                state=self._state,
                error=(
                    SimpleNamespace(message="permission denied")
                    if self._state == StatementState.FAILED
                    else None
                ),
            ),
            manifest=None,
            result=None,
        )


def test_sql_executor_rejects_failed_statements() -> None:
    workspace = SimpleNamespace(
        warehouses=_Warehouses(),
        statement_execution=_StatementExecution(StatementState.FAILED),
    )

    with pytest.raises(RuntimeError, match="permission denied"):
        SqlExecutor(workspace).query("DROP SCHEMA example")


def test_sql_executor_accepts_successful_statements_without_result_rows() -> None:
    workspace = SimpleNamespace(
        warehouses=_Warehouses(),
        statement_execution=_StatementExecution(StatementState.SUCCEEDED),
    )

    result = SqlExecutor(workspace).query("DROP SCHEMA example")

    assert result.columns == []
    assert result.rows == []
