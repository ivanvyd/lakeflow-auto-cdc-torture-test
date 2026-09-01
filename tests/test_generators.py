from datetime import timedelta

from src.generators.dispatch import (
    INITIAL_ROWS_BY_SOURCE,
    LATE_ROWS_BY_SOURCE,
    T0,
    _rows_to_insert_sql,
    _t,
)


def test_t_adds_seconds() -> None:
    assert _t(300) == T0 + timedelta(minutes=5)


def test_late_phase_contains_only_cross_update_events() -> None:
    assert set(LATE_ROWS_BY_SOURCE) == {
        "s01_duplicate_replay_src",
        "s02_out_of_order_src",
        "s06_delete_late_src",
        "s07_replay_src",
    }
    assert LATE_ROWS_BY_SOURCE["s02_out_of_order_src"][0][6] == 10
    assert LATE_ROWS_BY_SOURCE["s06_delete_late_src"][0][6] == 18
    assert len(LATE_ROWS_BY_SOURCE["s07_replay_src"]) == 5


def test_every_source_row_matches_the_canonical_schema_width() -> None:
    for rows_by_source in (INITIAL_ROWS_BY_SOURCE, LATE_ROWS_BY_SOURCE):
        for rows in rows_by_source.values():
            assert all(len(row) == 11 for row in rows)


def test_insert_sql_escapes_strings() -> None:
    row = list(INITIAL_ROWS_BY_SOURCE["s01_duplicate_src"][0])
    row[1] = "O'Neil"
    sql = _rows_to_insert_sql("`catalog`.`schema`.`source`", [row])
    assert "'O''Neil'" in sql
