from datetime import timedelta

from src.generators.dispatch import (
    SOURCE_COLUMNS,
    T0,
    CdcEvent,
    _rows_to_insert_sql,
    _t,
)
from src.scenario_specs import FLOW_SPECS, INITIAL_ROWS_BY_SOURCE, LATE_ROWS_BY_SOURCE, SOURCE_SPECS


def test_t_adds_seconds() -> None:
    assert _t(300) == T0 + timedelta(minutes=5)


def test_late_phase_contains_only_cross_update_events() -> None:
    assert set(LATE_ROWS_BY_SOURCE) == {
        "s01_duplicate_replay_src",
        "s02_out_of_order_src",
        "s06_delete_late_src",
        "s07_replay_src",
    }
    assert LATE_ROWS_BY_SOURCE["s02_out_of_order_src"][0].source_sequence == 10
    assert LATE_ROWS_BY_SOURCE["s06_delete_late_src"][0].source_sequence == 18
    assert len(LATE_ROWS_BY_SOURCE["s07_replay_src"]) == 5


def test_every_source_row_uses_the_typed_schema() -> None:
    for rows_by_source in (INITIAL_ROWS_BY_SOURCE, LATE_ROWS_BY_SOURCE):
        for rows in rows_by_source.values():
            assert all(isinstance(row, CdcEvent) for row in rows)
            assert all(row._fields == SOURCE_COLUMNS for row in rows)


def test_insert_sql_escapes_strings() -> None:
    row = INITIAL_ROWS_BY_SOURCE["s01_duplicate_src"][0]._replace(name="O'Neil")
    sql = _rows_to_insert_sql("`catalog`.`schema`.`source`", [row])
    assert "'O''Neil'" in sql
    assert "(`customer_id`, `name`, `email`" in sql


def test_registry_has_unique_complete_source_and_target_inventory() -> None:
    assert len(SOURCE_SPECS) == 13
    assert len({spec.source for spec in SOURCE_SPECS}) == 13
    assert len(FLOW_SPECS) == 18
    assert len({spec.target for spec in FLOW_SPECS}) == 18
    assert {flow.source for flow in FLOW_SPECS} <= {source.source for source in SOURCE_SPECS}
