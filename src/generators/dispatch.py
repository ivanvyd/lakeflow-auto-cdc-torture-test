"""
Per-scenario CDC event generators and the shared source-table definitions.

Each generator returns typed CDC events. The dispatcher
(`python -m src.generators.dispatch --scenario NN_name`) materializes them
as JSON. `src.generators.apply_to_workspace` uses the same rows to populate
workspace Delta tables.

We keep the dataset small on purpose. The article is about semantics, not scale.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple

from src.sql_identifiers import quote_identifier

# All scenarios focus on customer 42. A handful of other customers provide
# background so the target isn't a single-row table.
PRIMARY_CUSTOMER = 42

T0 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


class CdcEvent(NamedTuple):
    customer_id: int
    name: str | None
    email: str | None
    city: str | None
    status: str | None
    source_updated_at: datetime
    source_sequence: int
    transaction_sequence: int
    ingested_at: datetime
    operation: str
    last_synced_at: datetime


SOURCE_SCHEMA: tuple[tuple[str, str], ...] = (
    ("customer_id", "INT"),
    ("name", "STRING"),
    ("email", "STRING"),
    ("city", "STRING"),
    ("status", "STRING"),
    ("source_updated_at", "TIMESTAMP"),
    ("source_sequence", "INT"),
    ("transaction_sequence", "INT"),
    ("ingested_at", "TIMESTAMP"),
    ("operation", "STRING"),
    ("last_synced_at", "TIMESTAMP"),
)

SOURCE_COLUMNS = tuple(name for name, _ in SOURCE_SCHEMA)


def _t(seconds: int = 0) -> datetime:
    return T0 + timedelta(seconds=seconds)


def _event(
    *,
    status: str | None,
    source_seconds: int,
    source_sequence: int,
    ingested_seconds: int,
    transaction_sequence: int = 1,
    operation: str = "UPDATE",
    last_synced_seconds: int | None = None,
    name: str | None = "Ivan",
    email: str | None = "ivan@example.com",
    city: str | None = "Antalya",
) -> CdcEvent:
    return CdcEvent(
        customer_id=PRIMARY_CUSTOMER,
        name=name,
        email=email,
        city=city,
        status=status,
        source_updated_at=_t(source_seconds),
        source_sequence=source_sequence,
        transaction_sequence=transaction_sequence,
        ingested_at=_t(ingested_seconds),
        operation=operation,
        last_synced_at=_t(ingested_seconds if last_synced_seconds is None else last_synced_seconds),
    )


# ---------------------------------------------------------------------------
# Scenario 1 — exact duplicate
# ---------------------------------------------------------------------------


def scenario_01_duplicate() -> list[CdcEvent]:
    """One logical event delivered twice. The auto-CDC contract says the
    sequence column is used to pick the latest event; equal sequence values
    are outside the explicitly guaranteed behavior.

    We deliver the same (customer_id, source_sequence) twice and rely on
    AUTO CDC's per-key max to keep state stable.
    """
    return [_event(status="ACTIVE", source_seconds=0, source_sequence=10, ingested_seconds=0)]


# ---------------------------------------------------------------------------
# Scenario 2 — valid out-of-order
# ---------------------------------------------------------------------------


def scenario_02_out_of_order() -> list[CdcEvent]:
    """
    Logical:  seq=10 PENDING, then seq=12 ACTIVE.
    Physical: seq=12 ACTIVE arrives first, then seq=10 PENDING.
    Documented expectation: final state = ACTIVE (per-key max on source_sequence).
    """
    pending = _event(
        status="PENDING",
        source_seconds=0,
        source_sequence=10,
        ingested_seconds=10,  # physical arrival order: this one is LATE
    )
    active = _event(
        status="ACTIVE",
        source_seconds=20,
        source_sequence=12,
        ingested_seconds=0,  # physical arrival order: this one is EARLY
    )
    # Arrival order: ACTIVE first, then PENDING
    return [active, pending]


# ---------------------------------------------------------------------------
# Scenario 3 — sequence collision
# ---------------------------------------------------------------------------


def scenario_03_seq_collision_a() -> list[CdcEvent]:
    """Experiment A: same key, same source_sequence, two different states.
    The configured sequence cannot order these different states. The docs
    recommend a composite STRUCT when one field cannot break ties.
    """
    return [
        _event(status="ACTIVE", source_seconds=0, source_sequence=10, ingested_seconds=0),
        _event(
            status="SUSPENDED",
            source_seconds=0,
            source_sequence=10,
            transaction_sequence=2,
            ingested_seconds=1,
        ),
    ]


def scenario_03_seq_collision_b() -> list[CdcEvent]:
    """Experiment B: legitimate tie-breaker via a real source-side
    transaction_sequence. The source has a meaningful order — ACTIVE came
    before SUSPENDED in business time, even though they share an
    `source_updated_at` to the second.
    """
    return [
        _event(status="ACTIVE", source_seconds=0, source_sequence=10, ingested_seconds=0),
        _event(
            status="SUSPENDED",
            source_seconds=0,
            source_sequence=10,
            transaction_sequence=2,
            ingested_seconds=1,
        ),
    ]


# ---------------------------------------------------------------------------
# Scenario 4 — the wrong clock
# ---------------------------------------------------------------------------


def scenario_04_wrong_clock() -> list[CdcEvent]:
    """
    Two logical source events:
      10:00 source time → ACTIVE
      10:05 source time → SUSPENDED
    Recorded ingestion order:
      10:05 has ingested_at 10:06
      10:00 has ingested_at 10:10
    """
    return [
        # The newer business event arrives first.
        _event(
            status="SUSPENDED",
            source_seconds=300,
            source_sequence=20,
            ingested_seconds=360,
        ),
        # The older business event arrives second.
        _event(status="ACTIVE", source_seconds=0, source_sequence=10, ingested_seconds=600),
    ]


# ---------------------------------------------------------------------------
# Scenario 5 — sparse update / NULL semantics
# ---------------------------------------------------------------------------


def scenario_05_sparse() -> list[CdcEvent]:
    """Initial state then a sparse update that nulls out email.

    Two interpretations of the same CDC event:
      A — NULL means "set email = NULL" (default).
      B — NULL means "field absent" (IGNORE NULL UPDATES keeps existing value).
    The same source rows feed both targets; only the target's flow differs.
    """
    initial = _event(
        status="ACTIVE",
        source_seconds=0,
        source_sequence=10,
        ingested_seconds=0,
        email="x@example.com",
    )
    sparse = _event(
        status="ACTIVE",
        source_seconds=60,
        source_sequence=20,
        ingested_seconds=60,
        email=None,
        city="Istanbul",
    )
    return [initial, sparse]


# ---------------------------------------------------------------------------
# Scenario 6 — delete then a late older event
# ---------------------------------------------------------------------------


def scenario_06_delete_late() -> list[CdcEvent]:
    """
      seq=17 → ACTIVE
      seq=20 → DELETE
    Then late:
      seq=18 → SUSPENDED
    """
    return [
        _event(status="ACTIVE", source_seconds=0, source_sequence=17, ingested_seconds=0),
        _event(
            status=None,
            source_seconds=200,
            source_sequence=20,
            ingested_seconds=200,
            operation="DELETE",
            name=None,
            email=None,
            city=None,
        ),
        _event(
            status="SUSPENDED",
            source_seconds=150,
            source_sequence=18,
            ingested_seconds=250,
        ),
    ]


# ---------------------------------------------------------------------------
# Scenario 7 — full replay
# ---------------------------------------------------------------------------


def scenario_07_replay() -> list[CdcEvent]:
    """A canonical sequence of events:

    10 INSERT
    20 UPDATE
    30 UPDATE
    40 UPDATE
    50 DELETE
    """
    return [
        _event(
            status="PENDING",
            source_seconds=0,
            source_sequence=10,
            ingested_seconds=0,
            operation="INSERT",
        ),
        _event(status="ACTIVE", source_seconds=60, source_sequence=20, ingested_seconds=60),
        _event(
            status="ACTIVE",
            source_seconds=120,
            source_sequence=30,
            ingested_seconds=120,
            city="Izmir",
        ),
        _event(
            status="SUSPENDED",
            source_seconds=180,
            source_sequence=40,
            ingested_seconds=180,
            city="Ankara",
        ),
        _event(
            status=None,
            source_seconds=240,
            source_sequence=50,
            ingested_seconds=240,
            operation="DELETE",
            name=None,
            email=None,
            city=None,
        ),
    ]


# ---------------------------------------------------------------------------
# Scenario 8 — SCD2 history noise
# ---------------------------------------------------------------------------


def scenario_08_history(num_updates: int = 50) -> list[CdcEvent]:
    """One customer gets `num_updates` updates where *only* `last_synced_at`
    changes. We use `source_updated_at` as the SEQUENCE BY (and increase it
    per event) so AUTO CDC sees every event as a distinct CDC update, but
    `EXCEPT COLUMN LIST` strips `source_updated_at`, `source_sequence`,
    `ingested_at`, `transaction_sequence`, and `operation` from the target
    so they don't trigger new SCD2 history rows.

    Two targets on the same source:
      A — track every column → one history row per event.
      B — TRACK HISTORY ON * EXCEPT (last_synced_at) → only the initial
          INSERT creates a history row; all 50 noise-only updates collapse
          onto it.
    """
    rows = [
        _event(
            status="ACTIVE",
            source_seconds=0,
            source_sequence=10,
            ingested_seconds=0,
            operation="INSERT",
        )
    ]
    for i in range(1, num_updates + 1):
        # source_updated_at is the SEQUENCE BY for these flows; we advance
        # it so AUTO CDC treats each row as a distinct event. last_synced_at
        # is the only column in the *target* that varies per event.
        rows.append(
            _event(
                status="ACTIVE",
                source_seconds=i,
                source_sequence=10,
                ingested_seconds=0,
                last_synced_seconds=i * 60,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Scenario 9 — bitemporal (Beta)
# ---------------------------------------------------------------------------


def scenario_09_bitemporal() -> list[CdcEvent]:
    """Three events with distinct business times and distinct system times.
    Useful to demonstrate that the same CDC event appears differently under
    the bitemporal lens vs. plain SCD2.
    """
    return [
        _event(status="PENDING", source_seconds=0, source_sequence=10, ingested_seconds=60),
        _event(status="ACTIVE", source_seconds=120, source_sequence=20, ingested_seconds=180),
        _event(
            status="SUSPENDED",
            source_seconds=240,
            source_sequence=30,
            ingested_seconds=300,
        ),
    ]


# The DDL and INSERT column order are derived from the typed event contract.
SOURCE_SCHEMA_DDL = (
    "CREATE TABLE {fqn} (\n  "
    + ",\n  ".join(
        f"{quote_identifier(name, 'source column')} {sql_type}" for name, sql_type in SOURCE_SCHEMA
    )
    + "\n) USING DELTA"
)


def _render_value(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, datetime):
        return f"TIMESTAMP '{v.strftime('%Y-%m-%d %H:%M:%S.%f')}'"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    return str(v)


def _rows_to_insert_sql(fqn: str, rows: list[CdcEvent]) -> str:
    if not rows:
        return f"SELECT 1 WHERE FALSE -- {fqn}: empty"
    values = ", ".join("(" + ", ".join(_render_value(v) for v in r) + ")" for r in rows)
    columns = ", ".join(quote_identifier(name, "source column") for name in SOURCE_COLUMNS)
    return f"INSERT INTO {fqn} ({columns}) VALUES {values}"


def main() -> None:
    from src.scenario_specs import SCENARIO_EVENTS

    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=str, default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument(
        "--output", type=str, default=None, help="Write JSON to a file instead of stdout."
    )
    args = parser.parse_args()

    if args.all:
        out = {k: v for k, v in SCENARIO_EVENTS.items()}
    elif args.scenario:
        if args.scenario not in SCENARIO_EVENTS:
            print(f"unknown scenario: {args.scenario}", file=sys.stderr)
            sys.exit(2)
        out = {args.scenario: SCENARIO_EVENTS[args.scenario]}
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)

    payload = json.dumps(out, indent=2, default=str)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(payload)
    else:
        print(payload)


if __name__ == "__main__":
    main()
