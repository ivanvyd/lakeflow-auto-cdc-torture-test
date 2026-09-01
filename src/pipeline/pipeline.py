"""
Lakeflow Declarative Pipelines entry point.

Architecture:

  Delta table (populated by apply_to_workspace via INSERT INTO)
        │
        ▼
  @dp.view reading from that Delta table
        │
        ▼
  AUTO CDC flow
        │
        ▼
  target streaming table

`apply_to_workspace` populates each source as a plain Delta table. The
pipeline exposes it through a streaming view for AUTO CDC.
"""

from pyspark import pipelines as dp
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from src.generators.dispatch import SOURCE_TABLE_FOR_SCENARIO
from src.sql_identifiers import qualified_name

# The bundle injects the selected catalog and schema. These defaults keep
# direct development evaluation aligned with the dev target.
DEFAULT_PIPELINE_SCHEMA = "auto_cdc_torture_test"
DEFAULT_PIPELINE_CATALOG = "workspace"

# Columns we exclude from target tables. We intentionally keep all the
# sequence / timestamp columns in the target so the experiment is
# self-documenting.
EXCLUDE_FROM_TARGET = ["operation", "last_synced_at"]


SCENARIO_SOURCES: list[str] = [
    table for tables in SOURCE_TABLE_FOR_SCENARIO.values() for table in tables
]


def _active_spark() -> SparkSession:
    """Return the Spark session supplied by the pipeline runtime."""
    session = SparkSession.getActiveSession()
    if session is None:
        raise RuntimeError("Lakeflow pipeline evaluation has no active Spark session")
    return session


def _source_fqn(name: str) -> str:
    session = _active_spark()
    catalog = session.conf.get(
        "auto_cdc_torture.catalog",
        DEFAULT_PIPELINE_CATALOG,
    )
    schema = session.conf.get(
        "auto_cdc_torture.schema",
        DEFAULT_PIPELINE_SCHEMA,
    )
    return qualified_name(catalog, schema, name)


# AUTO CDC requires a streaming source.
for src in SCENARIO_SOURCES:

    @dp.view(name=src)
    def _v(name=src):  # default-arg binds `src` at def-time, avoiding the late-binding closure trap
        return _active_spark().readStream.table(_source_fqn(name))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scd1_flow(
    target: str,
    source: str,
    sequence_by,
    deletes: str | None = None,
    ignore_null_updates: bool = False,
) -> None:
    dp.create_streaming_table(name=target)
    kwargs = {
        "target": target,
        "source": source,
        "keys": ["customer_id"],
        "sequence_by": sequence_by,
        "apply_as_deletes": F.expr(deletes) if deletes else None,
        "except_column_list": EXCLUDE_FROM_TARGET,
        "stored_as_scd_type": "1",
        "ignore_null_updates": ignore_null_updates,
    }
    dp.create_auto_cdc_flow(**{k: v for k, v in kwargs.items() if v is not None})


def _scd2_flow(
    target: str,
    source: str,
    sequence_by,
    track_history_except: list[str] | None = None,
    deletes: str | None = None,
) -> None:
    dp.create_streaming_table(name=target)
    kwargs = {
        "target": target,
        "source": source,
        "keys": ["customer_id"],
        "sequence_by": sequence_by,
        "apply_as_deletes": F.expr(deletes) if deletes else None,
        "except_column_list": EXCLUDE_FROM_TARGET,
        "stored_as_scd_type": "2",
    }
    if track_history_except is not None:
        kwargs["track_history_except_column_list"] = track_history_except
    dp.create_auto_cdc_flow(**{k: v for k, v in kwargs.items() if v is not None})


# ---------------------------------------------------------------------------
# Scenario 1
# ---------------------------------------------------------------------------

_scd1_flow(
    "s01_duplicate_tgt", "s01_duplicate_src", "source_sequence", deletes="operation = 'DELETE'"
)
_scd1_flow(
    "s01_duplicate_replay_tgt",
    "s01_duplicate_replay_src",
    "source_sequence",
    deletes="operation = 'DELETE'",
)


# ---------------------------------------------------------------------------
# Scenario 2
# ---------------------------------------------------------------------------

_scd1_flow(
    "s02_out_of_order_tgt",
    "s02_out_of_order_src",
    "source_sequence",
    deletes="operation = 'DELETE'",
)
_scd2_flow(
    "s02_out_of_order_scd2_tgt",
    "s02_out_of_order_src",
    "source_sequence",
    track_history_except=["last_synced_at"],
    deletes="operation = 'DELETE'",
)


# ---------------------------------------------------------------------------
# Scenario 3
# ---------------------------------------------------------------------------

_scd1_flow(
    "s03_seq_collision_a_tgt",
    "s03_seq_collision_a_src",
    "source_sequence",
    deletes="operation = 'DELETE'",
)
_scd1_flow(
    "s03_seq_collision_b_tgt",
    "s03_seq_collision_b_src",
    "source_sequence",
    deletes="operation = 'DELETE'",
)
dp.create_streaming_table(name="s03_seq_collision_b_struct_tgt")
dp.create_auto_cdc_flow(
    target="s03_seq_collision_b_struct_tgt",
    source="s03_seq_collision_b_src",
    keys=["customer_id"],
    sequence_by=F.struct(F.col("source_updated_at"), F.col("transaction_sequence")),
    apply_as_deletes=F.expr("operation = 'DELETE'"),
    except_column_list=EXCLUDE_FROM_TARGET,
    stored_as_scd_type="1",
)


# ---------------------------------------------------------------------------
# Scenario 4
# ---------------------------------------------------------------------------

_scd1_flow(
    "s04_wrong_clock_ingest_tgt",
    "s04_wrong_clock_src",
    "ingested_at",
    deletes="operation = 'DELETE'",
)
_scd1_flow(
    "s04_wrong_clock_source_tgt",
    "s04_wrong_clock_src",
    "source_updated_at",
    deletes="operation = 'DELETE'",
)


# ---------------------------------------------------------------------------
# Scenario 5
# ---------------------------------------------------------------------------

_scd1_flow(
    "s05_sparse_a_tgt", "s05_sparse_a_src", "source_sequence", deletes="operation = 'DELETE'"
)
_scd1_flow(
    "s05_sparse_b_tgt",
    "s05_sparse_b_src",
    "source_sequence",
    deletes="operation = 'DELETE'",
    ignore_null_updates=True,
)


# ---------------------------------------------------------------------------
# Scenario 6
# ---------------------------------------------------------------------------

_scd1_flow(
    "s06_delete_late_tgt", "s06_delete_late_src", "source_sequence", deletes="operation = 'DELETE'"
)
_scd2_flow(
    "s06_delete_late_scd2_tgt",
    "s06_delete_late_src",
    "source_sequence",
    track_history_except=["last_synced_at"],
    deletes="operation = 'DELETE'",
)


# ---------------------------------------------------------------------------
# Scenario 7
# ---------------------------------------------------------------------------

_scd1_flow("s07_replay_tgt", "s07_replay_src", "source_sequence", deletes="operation = 'DELETE'")
_scd2_flow(
    "s07_replay_scd2_tgt",
    "s07_replay_src",
    "source_sequence",
    track_history_except=["last_synced_at"],
    deletes="operation = 'DELETE'",
)


# ---------------------------------------------------------------------------
# Scenario 8
# ---------------------------------------------------------------------------

# For scenario 8 the *only* thing we want to demonstrate is the impact of
# `TRACK HISTORY ON * EXCEPT (last_synced_at)`. The target therefore keeps
# `last_synced_at` in the schema. A naive SCD2 (A) generates one history
# row per event because `last_synced_at` changes. B suppresses those
# noise-only changes so only business-significant state changes create
# new versions.
#
# We sequence by `source_updated_at` (advanced per event) so AUTO CDC sees
# every event as a distinct CDC update. The other metadata columns are
# held constant in the source and excluded from the target so they don't
# themselves trigger new history rows.

S08_EXCLUDE = [
    "operation",
    "source_updated_at",
    "source_sequence",
    "ingested_at",
    "transaction_sequence",
]

dp.create_streaming_table(name="s08_history_a_scd2_tgt")
dp.create_auto_cdc_flow(
    target="s08_history_a_scd2_tgt",
    source="s08_history_a_src",
    keys=["customer_id"],
    sequence_by="source_updated_at",
    except_column_list=S08_EXCLUDE,
    stored_as_scd_type="2",
)
dp.create_streaming_table(name="s08_history_b_scd2_tgt")
dp.create_auto_cdc_flow(
    target="s08_history_b_scd2_tgt",
    source="s08_history_b_src",
    keys=["customer_id"],
    sequence_by="source_updated_at",
    track_history_except_column_list=["last_synced_at"],
    except_column_list=S08_EXCLUDE,
    stored_as_scd_type="2",
)


# ---------------------------------------------------------------------------
# Scenario 9 (Beta)
# ---------------------------------------------------------------------------

dp.create_streaming_table(name="s09_bitemporal_tgt")
dp.create_auto_cdc_flow(
    target="s09_bitemporal_tgt",
    source="s09_bitemporal_src",
    keys=["customer_id"],
    sequence_by="source_updated_at",
    system_sequence_by="ingested_at",
    stored_as_scd_type="bitemporal",
    except_column_list=EXCLUDE_FROM_TARGET,
)
