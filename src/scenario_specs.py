"""Canonical source, flow, and evidence definitions for the experiment."""

from __future__ import annotations

from dataclasses import dataclass

from src.generators.dispatch import (
    CdcEvent,
    scenario_01_duplicate,
    scenario_02_out_of_order,
    scenario_03_seq_collision_a,
    scenario_03_seq_collision_b,
    scenario_04_wrong_clock,
    scenario_05_sparse,
    scenario_06_delete_late,
    scenario_07_replay,
    scenario_08_history,
    scenario_09_bitemporal,
)

DEFAULT_SCHEMA = "auto_cdc_torture_test"
DEFAULT_EXCLUDE = ("operation", "last_synced_at")
HISTORY_EXCLUDE = (
    "operation",
    "source_updated_at",
    "source_sequence",
    "ingested_at",
    "transaction_sequence",
)


@dataclass(frozen=True)
class SourceSpec:
    scenario: str
    source: str
    initial: tuple[CdcEvent, ...]
    late: tuple[CdcEvent, ...] = ()


@dataclass(frozen=True)
class FlowSpec:
    scenario: str
    target: str
    source: str
    stored_as_scd_type: str
    sequence_by: str | tuple[str, ...]
    classification: str
    ordering_complete: bool
    business_passed: bool
    expected: str
    observed: str
    target_rows: int
    history_rows: int
    live_predicate: str
    expected_late_change: bool = False
    delete_condition: str | None = "operation = 'DELETE'"
    ignore_null_updates: bool = False
    track_history_except: tuple[str, ...] = ()
    except_columns: tuple[str, ...] = DEFAULT_EXCLUDE
    system_sequence_by: str | None = None


def _source(
    scenario: str,
    source: str,
    initial: list[CdcEvent],
    late: list[CdcEvent] | None = None,
) -> SourceSpec:
    return SourceSpec(scenario, source, tuple(initial), tuple(late or []))


duplicate = scenario_01_duplicate()
out_of_order = scenario_02_out_of_order()
delete_late = scenario_06_delete_late()
replay = scenario_07_replay()

SOURCE_SPECS = (
    _source("01_duplicate", "s01_duplicate_src", duplicate),
    _source("01_duplicate_replay", "s01_duplicate_replay_src", duplicate, duplicate),
    _source("02_out_of_order", "s02_out_of_order_src", out_of_order[:1], out_of_order[1:]),
    _source("03_seq_collision_a", "s03_seq_collision_a_src", scenario_03_seq_collision_a()),
    _source("03_seq_collision_b", "s03_seq_collision_b_src", scenario_03_seq_collision_b()),
    _source("04_wrong_clock", "s04_wrong_clock_src", scenario_04_wrong_clock()),
    _source("05_sparse", "s05_sparse_a_src", scenario_05_sparse()),
    _source("05_sparse", "s05_sparse_b_src", scenario_05_sparse()),
    _source("06_delete_late", "s06_delete_late_src", delete_late[:2], delete_late[2:]),
    _source("07_replay", "s07_replay_src", replay, replay),
    _source("08_history", "s08_history_a_src", scenario_08_history()),
    _source("08_history", "s08_history_b_src", scenario_08_history()),
    _source("09_bitemporal", "s09_bitemporal_src", scenario_09_bitemporal()),
)


def _derive_scenario_events() -> dict[str, list[CdcEvent]]:
    payloads: dict[str, tuple[CdcEvent, ...]] = {}
    for spec in SOURCE_SPECS:
        payload = spec.initial + spec.late
        existing = payloads.setdefault(spec.scenario, payload)
        if existing != payload:
            raise ValueError(f"sources for {spec.scenario} do not share one logical event payload")
    return {scenario: list(events) for scenario, events in payloads.items()}


SCENARIO_EVENTS = _derive_scenario_events()

INITIAL_ROWS_BY_SOURCE = {spec.source: list(spec.initial) for spec in SOURCE_SPECS}
LATE_ROWS_BY_SOURCE = {spec.source: list(spec.late) for spec in SOURCE_SPECS if spec.late}
SOURCE_TABLE_FOR_SCENARIO: dict[str, list[str]] = {}
for source_spec in SOURCE_SPECS:
    SOURCE_TABLE_FOR_SCENARIO.setdefault(source_spec.scenario, []).append(source_spec.source)


FLOW_SPECS = (
    FlowSpec(
        "01_duplicate",
        "s01_duplicate_tgt",
        "s01_duplicate_src",
        "1",
        "source_sequence",
        "HANDLED",
        True,
        True,
        "Single row, status=ACTIVE; pipeline green",
        "1 row, status=ACTIVE",
        1,
        0,
        "COUNT_IF(status = 'ACTIVE') = 1",
    ),
    FlowSpec(
        "01_duplicate_replay",
        "s01_duplicate_replay_tgt",
        "s01_duplicate_replay_src",
        "1",
        "source_sequence",
        "HANDLED",
        True,
        True,
        "Single row, status=ACTIVE; same as scenario 1 base",
        "1 row, status=ACTIVE (replay dedup'd by per-key max)",
        1,
        0,
        "COUNT_IF(status = 'ACTIVE') = 1",
    ),
    FlowSpec(
        "02_out_of_order",
        "s02_out_of_order_tgt",
        "s02_out_of_order_src",
        "1",
        "source_sequence",
        "HANDLED",
        True,
        True,
        "status=ACTIVE; SCD1 keeps latest by source_sequence",
        "1 row, status=ACTIVE (per-key max on source_sequence=12)",
        1,
        0,
        "COUNT_IF(status = 'ACTIVE') = 1",
    ),
    FlowSpec(
        "02_out_of_order_scd2",
        "s02_out_of_order_scd2_tgt",
        "s02_out_of_order_src",
        "2",
        "source_sequence",
        "HANDLED",
        True,
        True,
        "Two history rows; ACTIVE is the active version",
        "2 history rows: PENDING@10 closed at 12, ACTIVE@12 current",
        2,
        2,
        "COUNT_IF(status = 'PENDING' AND __END_AT = 12) = 1 "
        "AND COUNT_IF(status = 'ACTIVE' AND __END_AT IS NULL) = 1",
        expected_late_change=True,
        track_history_except=("last_synced_at",),
    ),
    FlowSpec(
        "03_seq_collision_a",
        "s03_seq_collision_a_tgt",
        "s03_seq_collision_a_src",
        "1",
        "source_sequence",
        "AMBIGUOUS_ORDER",
        False,
        False,
        "No deterministic business state: two different states share source_sequence=10",
        "1 row, status=SUSPENDED in this run; configured order is ambiguous",
        1,
        0,
        "COUNT_IF(status = 'SUSPENDED') = 1",
    ),
    FlowSpec(
        "03_seq_collision_b",
        "s03_seq_collision_b_tgt",
        "s03_seq_collision_b_src",
        "1",
        "source_sequence",
        "AMBIGUOUS_ORDER",
        False,
        True,
        "status=SUSPENDED, but only if transaction_sequence participates in SEQUENCE BY",
        "1 row, status=SUSPENDED in this run; transaction_sequence is present but not configured",
        1,
        0,
        "COUNT_IF(status = 'SUSPENDED') = 1",
    ),
    FlowSpec(
        "03_seq_collision_b_struct",
        "s03_seq_collision_b_struct_tgt",
        "s03_seq_collision_b_src",
        "1",
        ("source_updated_at", "transaction_sequence"),
        "HANDLED",
        True,
        True,
        "status=SUSPENDED via composite STRUCT(source_updated_at, transaction_sequence)",
        "1 row, status=SUSPENDED (composite SEQUENCE BY orders by (t, txn) = (0,1) vs (0,2))",
        1,
        0,
        "COUNT_IF(status = 'SUSPENDED') = 1",
    ),
    FlowSpec(
        "04_wrong_clock_ingest",
        "s04_wrong_clock_ingest_tgt",
        "s04_wrong_clock_src",
        "1",
        "ingested_at",
        "BUSINESS_SEMANTICS",
        True,
        False,
        "status=ACTIVE; pipeline green; BUSINESS expectation diverges",
        "1 row, status=ACTIVE (ingest-time ordering treats 10:10 as newest, but business intent says 10:05 is newest)",
        1,
        0,
        "COUNT_IF(status = 'ACTIVE') = 1",
    ),
    FlowSpec(
        "04_wrong_clock_source",
        "s04_wrong_clock_source_tgt",
        "s04_wrong_clock_src",
        "1",
        "source_updated_at",
        "CONFIGURATION_DEPENDENT",
        True,
        True,
        "status=SUSPENDED; matches business intent (10:05 is the latest source event)",
        "1 row, status=SUSPENDED (source-time ordering picks 10:05 SUSPENDED)",
        1,
        0,
        "COUNT_IF(status = 'SUSPENDED') = 1",
    ),
    FlowSpec(
        "05_sparse_a",
        "s05_sparse_a_tgt",
        "s05_sparse_a_src",
        "1",
        "source_sequence",
        "BUSINESS_SEMANTICS",
        True,
        False,
        "email NULL after sparse update; default behavior overwrites with NULL",
        "1 row, email=NULL (default: NULL means 'set to null')",
        1,
        0,
        "COUNT_IF(email IS NULL AND city = 'Istanbul') = 1",
    ),
    FlowSpec(
        "05_sparse_b",
        "s05_sparse_b_tgt",
        "s05_sparse_b_src",
        "1",
        "source_sequence",
        "CONFIGURATION_DEPENDENT",
        True,
        True,
        "email='x@example.com' (kept); city='Istanbul' (updated)",
        "1 row, email='x@example.com' (kept), city='Istanbul' (updated)",
        1,
        0,
        "COUNT_IF(email = 'x@example.com' AND city = 'Istanbul') = 1",
        ignore_null_updates=True,
    ),
    FlowSpec(
        "06_delete_late_scd1",
        "s06_delete_late_tgt",
        "s06_delete_late_src",
        "1",
        "source_sequence",
        "HANDLED",
        True,
        True,
        "Row deleted; late seq=18 event is dropped",
        "0 rows (DELETE@20 applied, late seq=18 dropped by per-key max)",
        0,
        0,
        "TRUE",
    ),
    FlowSpec(
        "06_delete_late_scd2",
        "s06_delete_late_scd2_tgt",
        "s06_delete_late_src",
        "2",
        "source_sequence",
        "HANDLED",
        True,
        True,
        "History: ACTIVE@17 → SUSPENDED@18 → DELETE@20",
        "2 history rows: ACTIVE@17 closed at 18, SUSPENDED@18 closed at 20 (DELETE)",
        2,
        2,
        "COUNT_IF(status = 'ACTIVE' AND __START_AT = 17 AND __END_AT = 18) = 1 "
        "AND COUNT_IF(status = 'SUSPENDED' AND __START_AT = 18 AND __END_AT = 20) = 1",
        expected_late_change=True,
        track_history_except=("last_synced_at",),
    ),
    FlowSpec(
        "07_replay_scd1",
        "s07_replay_tgt",
        "s07_replay_src",
        "1",
        "source_sequence",
        "HANDLED",
        True,
        True,
        "Empty target after DELETE at source_sequence=50; pipeline green",
        "0 rows (final DELETE@50 applied; the prior history is overwritten by current state, which is empty)",
        0,
        0,
        "TRUE",
    ),
    FlowSpec(
        "07_replay_scd2",
        "s07_replay_scd2_tgt",
        "s07_replay_src",
        "2",
        "source_sequence",
        "HANDLED",
        True,
        True,
        "Multiple history rows; final state is closed at __END_AT for seq=50",
        "4 history rows: PENDING[10,20)→ACTIVE(Antalya)[20,30)→ACTIVE(Izmir)[30,40)→SUSPENDED(Ankara)[40,50)",
        4,
        4,
        "COUNT_IF(status = 'PENDING' AND __START_AT = 10 AND __END_AT = 20) = 1 "
        "AND COUNT_IF(status = 'ACTIVE' AND city = 'Antalya' AND __START_AT = 20 AND __END_AT = 30) = 1 "
        "AND COUNT_IF(status = 'ACTIVE' AND city = 'Izmir' AND __START_AT = 30 AND __END_AT = 40) = 1 "
        "AND COUNT_IF(status = 'SUSPENDED' AND city = 'Ankara' AND __START_AT = 40 AND __END_AT = 50) = 1",
        track_history_except=("last_synced_at",),
    ),
    FlowSpec(
        "08_history_a",
        "s08_history_a_scd2_tgt",
        "s08_history_a_src",
        "2",
        "source_updated_at",
        "BUSINESS_SEMANTICS",
        True,
        False,
        "One business-significant history row; operational timestamps should not add versions",
        "51 history rows (every event creates a new version because last_synced_at changes)",
        51,
        51,
        "COUNT_IF(status = 'ACTIVE') = 51",
        delete_condition=None,
        except_columns=HISTORY_EXCLUDE,
    ),
    FlowSpec(
        "08_history_b",
        "s08_history_b_scd2_tgt",
        "s08_history_b_src",
        "2",
        "source_updated_at",
        "CONFIGURATION_DEPENDENT",
        True,
        True,
        "A small number of history rows (only business-significant changes)",
        "1 history row (TRACK HISTORY ON * EXCEPT (last_synced_at) suppresses 50 noise-only updates)",
        1,
        1,
        "COUNT_IF(status = 'ACTIVE') = 1",
        delete_condition=None,
        track_history_except=("last_synced_at",),
        except_columns=HISTORY_EXCLUDE,
    ),
    FlowSpec(
        "09_bitemporal",
        "s09_bitemporal_tgt",
        "s09_bitemporal_src",
        "bitemporal",
        "source_updated_at",
        "HANDLED",
        True,
        True,
        "Bitemporal history rows with __SYSTEM_START_AT / __SYSTEM_END_AT",
        "5 history rows with both __START_AT/__END_AT and __SYSTEM_START_AT/__SYSTEM_END_AT",
        5,
        5,
        "COUNT_IF(status = 'PENDING' AND __START_AT = TIMESTAMP '2026-08-30 10:00:00' AND __END_AT IS NULL AND __SYSTEM_START_AT = TIMESTAMP '2026-08-30 10:01:00' AND __SYSTEM_END_AT = TIMESTAMP '2026-08-30 10:03:00') = 1 "
        "AND COUNT_IF(status = 'PENDING' AND __START_AT = TIMESTAMP '2026-08-30 10:00:00' AND __END_AT = TIMESTAMP '2026-08-30 10:02:00' AND __SYSTEM_START_AT = TIMESTAMP '2026-08-30 10:03:00' AND __SYSTEM_END_AT IS NULL) = 1 "
        "AND COUNT_IF(status = 'ACTIVE' AND __START_AT = TIMESTAMP '2026-08-30 10:02:00' AND __END_AT IS NULL AND __SYSTEM_START_AT = TIMESTAMP '2026-08-30 10:03:00' AND __SYSTEM_END_AT = TIMESTAMP '2026-08-30 10:05:00') = 1 "
        "AND COUNT_IF(status = 'ACTIVE' AND __START_AT = TIMESTAMP '2026-08-30 10:02:00' AND __END_AT = TIMESTAMP '2026-08-30 10:04:00' AND __SYSTEM_START_AT = TIMESTAMP '2026-08-30 10:05:00' AND __SYSTEM_END_AT IS NULL) = 1 "
        "AND COUNT_IF(status = 'SUSPENDED' AND __START_AT = TIMESTAMP '2026-08-30 10:04:00' AND __END_AT IS NULL AND __SYSTEM_START_AT = TIMESTAMP '2026-08-30 10:05:00' AND __SYSTEM_END_AT IS NULL) = 1",
        delete_condition=None,
        system_sequence_by="ingested_at",
    ),
)

TARGET_NAMES = tuple(spec.target for spec in FLOW_SPECS)
EXPECTED_LATE_PHASE_CHANGES = frozenset(
    spec.target for spec in FLOW_SPECS if spec.expected_late_change
)
FLOW_BY_TARGET = {spec.target: spec for spec in FLOW_SPECS}
CLASSIFICATION_BY_SCENARIO = {spec.scenario: spec.classification for spec in FLOW_SPECS}
DISPLAY_NAME_BY_SCENARIO = {
    "01_duplicate": "1A Exact duplicate",
    "01_duplicate_replay": "1B Duplicate after baseline",
    "02_out_of_order": "2A Out of order, SCD1",
    "02_out_of_order_scd2": "2B Out of order, SCD2",
    "03_seq_collision_a": "3A Sequence collision",
    "03_seq_collision_b": "3B Tie-breaker not configured",
    "03_seq_collision_b_struct": "3C Composite sequence",
    "04_wrong_clock_ingest": "4A Ingestion-time order",
    "04_wrong_clock_source": "4B Source-time order",
    "05_sparse_a": "5A Default NULL handling",
    "05_sparse_b": "5B Ignore NULL updates",
    "06_delete_late_scd1": "6A Delete then late event, SCD1",
    "06_delete_late_scd2": "6B Delete then late event, SCD2",
    "07_replay_scd1": "7A Full replay, SCD1",
    "07_replay_scd2": "7B Full replay, SCD2",
    "08_history_a": "8A Track every column",
    "08_history_b": "8B Exclude sync timestamp",
    "09_bitemporal": "9 Bitemporal history",
}


def validate_registry() -> None:
    source_names = [spec.source for spec in SOURCE_SPECS]
    target_names = [spec.target for spec in FLOW_SPECS]
    if len(source_names) != len(set(source_names)):
        raise ValueError("source names must be unique")
    if len(target_names) != len(set(target_names)):
        raise ValueError("target names must be unique")
    missing_sources = sorted({spec.source for spec in FLOW_SPECS} - set(source_names))
    if missing_sources:
        raise ValueError(f"flow sources are not registered: {missing_sources}")
    if len(FLOW_SPECS) != 18:
        raise ValueError(f"expected 18 flow configurations, got {len(FLOW_SPECS)}")
    scenarios = {spec.scenario for spec in FLOW_SPECS}
    if set(DISPLAY_NAME_BY_SCENARIO) != scenarios:
        raise ValueError("display names must cover every flow scenario exactly")


validate_registry()
