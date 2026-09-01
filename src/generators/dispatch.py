"""
Per-scenario CDC event generators and the shared source-table definitions.

Each generator returns a list of rows, where each row is a positional list
matching the column order in `SOURCE_SCHEMA_DDL` below. The dispatcher
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
from typing import Any

# All scenarios focus on customer 42. A handful of other customers provide
# background so the target isn't a single-row table.
PRIMARY_CUSTOMER = 42

T0 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


def _t(seconds: int = 0) -> datetime:
    return T0 + timedelta(seconds=seconds)


# ---------------------------------------------------------------------------
# Scenario 1 — exact duplicate
# ---------------------------------------------------------------------------


def scenario_01_duplicate() -> list[list[Any]]:
    """One logical event delivered twice. The auto-CDC contract says the
    sequence column is used to pick the latest event; equal sequence values
    are outside the explicitly guaranteed behavior.

    We deliver the same (customer_id, source_sequence) twice and rely on
    AUTO CDC's per-key max to keep state stable.
    """
    return [
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Antalya",
            "ACTIVE",
            _t(0),
            10,
            1,
            _t(0),
            "UPDATE",
            _t(0),
        ]
    ]


def scenario_01_duplicate_replay() -> list[list[Any]]:
    """The same logical event delivered twice: once, then replayed."""
    return scenario_01_duplicate() + scenario_01_duplicate()


# ---------------------------------------------------------------------------
# Scenario 2 — valid out-of-order
# ---------------------------------------------------------------------------


def scenario_02_out_of_order() -> list[list[Any]]:
    """
    Logical:  seq=10 PENDING, then seq=12 ACTIVE.
    Physical: seq=12 ACTIVE arrives first, then seq=10 PENDING.
    Documented expectation: final state = ACTIVE (per-key max on source_sequence).
    """
    pending = [
        PRIMARY_CUSTOMER,
        "Ivan",
        "ivan@example.com",
        "Antalya",
        "PENDING",
        _t(0),
        10,
        1,
        _t(10),  # physical arrival order: this one is LATE
        "UPDATE",
        _t(10),
    ]
    active = [
        PRIMARY_CUSTOMER,
        "Ivan",
        "ivan@example.com",
        "Antalya",
        "ACTIVE",
        _t(20),
        12,
        1,
        _t(0),  # physical arrival order: this one is EARLY
        "UPDATE",
        _t(0),
    ]
    # Arrival order: ACTIVE first, then PENDING
    return [active, pending]


# ---------------------------------------------------------------------------
# Scenario 3 — sequence collision
# ---------------------------------------------------------------------------


def scenario_03_seq_collision_a() -> list[list[Any]]:
    """Experiment A: same key, same source_sequence, two different states.
    The configured sequence cannot order these different states. The docs
    recommend a composite STRUCT when one field cannot break ties.
    """
    return [
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Antalya",
            "ACTIVE",
            _t(0),
            10,  # the same source_sequence
            1,
            _t(0),
            "UPDATE",
            _t(0),
        ],
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Antalya",
            "SUSPENDED",  # different state, same sequence
            _t(0),
            10,  # the same source_sequence
            2,
            _t(1),
            "UPDATE",
            _t(1),
        ],
    ]


def scenario_03_seq_collision_b() -> list[list[Any]]:
    """Experiment B: legitimate tie-breaker via a real source-side
    transaction_sequence. The source has a meaningful order — ACTIVE came
    before SUSPENDED in business time, even though they share an
    `source_updated_at` to the second.
    """
    return [
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Antalya",
            "ACTIVE",
            _t(0),
            10,
            1,  # transaction_sequence = 1
            _t(0),
            "UPDATE",
            _t(0),
        ],
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Antalya",
            "SUSPENDED",
            _t(0),
            10,
            2,  # transaction_sequence = 2
            _t(1),
            "UPDATE",
            _t(1),
        ],
    ]


# ---------------------------------------------------------------------------
# Scenario 4 — the wrong clock
# ---------------------------------------------------------------------------


def scenario_04_wrong_clock() -> list[list[Any]]:
    """
    Two logical source events:
      10:00 source time → ACTIVE
      10:05 source time → SUSPENDED
    Recorded ingestion order:
      10:05 has ingested_at 10:06
      10:00 has ingested_at 10:10
    """
    return [
        # The newer business event arrives first
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Antalya",
            "SUSPENDED",
            _t(300),  # source time = 10:05
            20,
            1,
            _t(360),  # ingestion = 10:06
            "UPDATE",
            _t(360),
        ],
        # The older business event arrives second
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Antalya",
            "ACTIVE",
            _t(0),  # source time = 10:00
            10,
            1,
            _t(600),  # ingestion = 10:10
            "UPDATE",
            _t(600),
        ],
    ]


# ---------------------------------------------------------------------------
# Scenario 5 — sparse update / NULL semantics
# ---------------------------------------------------------------------------


def scenario_05_sparse() -> list[list[Any]]:
    """Initial state then a sparse update that nulls out email.

    Two interpretations of the same CDC event:
      A — NULL means "set email = NULL" (default).
      B — NULL means "field absent" (IGNORE NULL UPDATES keeps existing value).
    The same source rows feed both targets; only the target's flow differs.
    """
    initial = [
        PRIMARY_CUSTOMER,
        "Ivan",
        "x@example.com",
        "Antalya",
        "ACTIVE",
        _t(0),
        10,
        1,
        _t(0),
        "UPDATE",
        _t(0),
    ]
    sparse = [
        PRIMARY_CUSTOMER,
        "Ivan",
        None,  # sparse: email removed
        "Istanbul",
        "ACTIVE",
        _t(60),
        20,
        1,
        _t(60),
        "UPDATE",
        _t(60),
    ]
    return [initial, sparse]


# ---------------------------------------------------------------------------
# Scenario 6 — delete then a late older event
# ---------------------------------------------------------------------------


def scenario_06_delete_late() -> list[list[Any]]:
    """
      seq=17 → ACTIVE
      seq=20 → DELETE
    Then late:
      seq=18 → SUSPENDED
    """
    return [
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Antalya",
            "ACTIVE",
            _t(0),
            17,
            1,
            _t(0),
            "UPDATE",
            _t(0),
        ],
        [PRIMARY_CUSTOMER, None, None, None, None, _t(200), 20, 1, _t(200), "DELETE", _t(200)],
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Antalya",
            "SUSPENDED",
            _t(150),
            18,
            1,
            _t(250),
            "UPDATE",
            _t(250),
        ],
    ]


# ---------------------------------------------------------------------------
# Scenario 7 — full replay
# ---------------------------------------------------------------------------


def scenario_07_replay() -> list[list[Any]]:
    """A canonical sequence of events:

    10 INSERT
    20 UPDATE
    30 UPDATE
    40 UPDATE
    50 DELETE
    """
    return [
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Antalya",
            "PENDING",
            _t(0),
            10,
            1,
            _t(0),
            "INSERT",
            _t(0),
        ],
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Antalya",
            "ACTIVE",
            _t(60),
            20,
            1,
            _t(60),
            "UPDATE",
            _t(60),
        ],
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Izmir",
            "ACTIVE",
            _t(120),
            30,
            1,
            _t(120),
            "UPDATE",
            _t(120),
        ],
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Ankara",
            "SUSPENDED",
            _t(180),
            40,
            1,
            _t(180),
            "UPDATE",
            _t(180),
        ],
        [PRIMARY_CUSTOMER, None, None, None, None, _t(240), 50, 1, _t(240), "DELETE", _t(240)],
    ]


# ---------------------------------------------------------------------------
# Scenario 8 — SCD2 history noise
# ---------------------------------------------------------------------------


def scenario_08_history(num_updates: int = 50) -> list[list[Any]]:
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
    rows: list[list[Any]] = [
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Antalya",
            "ACTIVE",
            _t(0),
            10,
            1,
            _t(0),
            "INSERT",
            _t(0),
        ],
    ]
    for i in range(1, num_updates + 1):
        # source_updated_at is the SEQUENCE BY for these flows; we advance
        # it so AUTO CDC treats each row as a distinct event. last_synced_at
        # is the only column in the *target* that varies per event.
        rows.append(
            [
                PRIMARY_CUSTOMER,
                "Ivan",
                "ivan@example.com",
                "Antalya",
                "ACTIVE",
                _t(i),  # source_updated_at advances per event (for SEQUENCE BY)
                10,  # source_sequence held constant
                1,  # transaction_sequence held constant
                _t(0),  # ingested_at held constant
                "UPDATE",
                _t(i * 60),  # last_synced_at changes per event
            ]
        )
    return rows


# ---------------------------------------------------------------------------
# Scenario 9 — bitemporal (Beta)
# ---------------------------------------------------------------------------


def scenario_09_bitemporal() -> list[list[Any]]:
    """Three events with distinct business times and distinct system times.
    Useful to demonstrate that the same CDC event appears differently under
    the bitemporal lens vs. plain SCD2.
    """
    return [
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Antalya",
            "PENDING",
            _t(0),
            10,
            1,
            _t(60),
            "UPDATE",
            _t(60),
        ],
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Antalya",
            "ACTIVE",
            _t(120),
            20,
            1,
            _t(180),
            "UPDATE",
            _t(180),
        ],
        [
            PRIMARY_CUSTOMER,
            "Ivan",
            "ivan@example.com",
            "Antalya",
            "SUSPENDED",
            _t(240),
            30,
            1,
            _t(300),
            "UPDATE",
            _t(300),
        ],
    ]


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, list[list[Any]] | dict[str, Any]] = {
    "01_duplicate": scenario_01_duplicate(),
    "01_duplicate_replay": scenario_01_duplicate_replay(),
    "02_out_of_order": scenario_02_out_of_order(),
    "03_seq_collision_a": scenario_03_seq_collision_a(),
    "03_seq_collision_b": scenario_03_seq_collision_b(),
    "04_wrong_clock": scenario_04_wrong_clock(),
    "05_sparse": scenario_05_sparse(),
    "06_delete_late": scenario_06_delete_late(),
    "07_replay": scenario_07_replay(),
    "08_history": scenario_08_history(),
    "09_bitemporal": scenario_09_bitemporal(),
}


# Map each scenario key to the source table(s) it populates. A scenario that
# has both an A and a B configuration (e.g. `05_sparse` → A and B) lists both
# tables; otherwise a single entry. The pipeline's @dp.view is registered
# once per source-table name.
SOURCE_TABLE_FOR_SCENARIO: dict[str, list[str]] = {
    "01_duplicate": ["s01_duplicate_src"],
    "01_duplicate_replay": ["s01_duplicate_replay_src"],
    "02_out_of_order": ["s02_out_of_order_src"],
    "03_seq_collision_a": ["s03_seq_collision_a_src"],
    "03_seq_collision_b": ["s03_seq_collision_b_src"],
    "04_wrong_clock": ["s04_wrong_clock_src"],
    "05_sparse": ["s05_sparse_a_src", "s05_sparse_b_src"],
    "06_delete_late": ["s06_delete_late_src"],
    "07_replay": ["s07_replay_src"],
    "08_history": ["s08_history_a_src", "s08_history_b_src"],
    "09_bitemporal": ["s09_bitemporal_src"],
}


# The first update establishes each target's baseline. The second update
# appends the rows that are supposed to arrive late or be replayed. Keeping
# these phases explicit prevents a single full refresh from masquerading as
# an arrival-order or replay test.
INITIAL_ROWS_BY_SOURCE: dict[str, list[list[Any]]] = {
    "s01_duplicate_src": scenario_01_duplicate(),
    "s01_duplicate_replay_src": scenario_01_duplicate(),
    "s02_out_of_order_src": scenario_02_out_of_order()[:1],
    "s03_seq_collision_a_src": scenario_03_seq_collision_a(),
    "s03_seq_collision_b_src": scenario_03_seq_collision_b(),
    "s04_wrong_clock_src": scenario_04_wrong_clock(),
    "s05_sparse_a_src": scenario_05_sparse(),
    "s05_sparse_b_src": scenario_05_sparse(),
    "s06_delete_late_src": scenario_06_delete_late()[:2],
    "s07_replay_src": scenario_07_replay(),
    "s08_history_a_src": scenario_08_history(),
    "s08_history_b_src": scenario_08_history(),
    "s09_bitemporal_src": scenario_09_bitemporal(),
}

LATE_ROWS_BY_SOURCE: dict[str, list[list[Any]]] = {
    "s01_duplicate_replay_src": scenario_01_duplicate(),
    "s02_out_of_order_src": scenario_02_out_of_order()[1:],
    "s06_delete_late_src": scenario_06_delete_late()[2:],
    "s07_replay_src": scenario_07_replay(),
}


# Default Unity Catalog schema used by local CLIs and the bundle.
DEFAULT_SCHEMA = "auto_cdc_torture_test"


# The single source-of-truth DDL for the CDC source tables.
SOURCE_SCHEMA_DDL = """
CREATE TABLE {fqn} (
  customer_id INT,
  name STRING,
  email STRING,
  city STRING,
  status STRING,
  source_updated_at TIMESTAMP,
  source_sequence INT,
  transaction_sequence INT,
  ingested_at TIMESTAMP,
  operation STRING,
  last_synced_at TIMESTAMP
) USING DELTA
"""


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


def _rows_to_insert_sql(fqn: str, rows: list[list[Any]]) -> str:
    if not rows:
        return f"SELECT 1 WHERE FALSE -- {fqn}: empty"
    values = ", ".join("(" + ", ".join(_render_value(v) for v in r) + ")" for r in rows)
    return f"INSERT INTO {fqn} VALUES {values}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=str, default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument(
        "--output", type=str, default=None, help="Write JSON to a file instead of stdout."
    )
    args = parser.parse_args()

    if args.all:
        out = {k: v for k, v in SCENARIOS.items()}
    elif args.scenario:
        if args.scenario not in SCENARIOS:
            print(f"unknown scenario: {args.scenario}", file=sys.stderr)
            sys.exit(2)
        out = {args.scenario: SCENARIOS[args.scenario]}
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
