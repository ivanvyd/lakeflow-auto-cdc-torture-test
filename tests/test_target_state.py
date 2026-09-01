from types import SimpleNamespace

import pytest
from databricks.sdk.service.sql import StatementState

from src.analysis.cleanup import validate_cleanup_scope
from src.analysis.target_state import SqlExecutor, require_completed_update


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


@pytest.mark.parametrize(
    ("actual", "expected"),
    [(False, True), (True, False)],
)
def test_update_validation_rejects_the_wrong_refresh_phase(actual: bool, expected: bool) -> None:
    pipelines = SimpleNamespace(
        get_update=lambda **_kwargs: SimpleNamespace(
            update=SimpleNamespace(
                state=SimpleNamespace(value="COMPLETED"),
                full_refresh=actual,
            )
        )
    )
    workspace = SimpleNamespace(pipelines=pipelines)

    with pytest.raises(RuntimeError, match="full_refresh"):
        require_completed_update(
            workspace,
            "pipeline",
            "update",
            expected_full_refresh=expected,
        )


def test_cleanup_scope_rejects_non_experiment_schema() -> None:
    with pytest.raises(ValueError, match="refusing cascading cleanup"):
        validate_cleanup_scope("default", "default")


def test_cleanup_scope_requires_exact_confirmation() -> None:
    with pytest.raises(ValueError, match="exactly match"):
        validate_cleanup_scope("auto_cdc_torture_test", "auto_cdc_torture_typo")
