"""Lakeflow Declarative Pipelines entry point for the scenario registry.

Each generated Delta source is exposed as a streaming view, then every
registered flow is translated into one ``create_auto_cdc_flow`` call.
"""

from pyspark import pipelines as dp
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from src.scenario_specs import FLOW_SPECS, SOURCE_SPECS
from src.sql_identifiers import qualified_name

DEFAULT_PIPELINE_SCHEMA = "auto_cdc_torture_test"
DEFAULT_PIPELINE_CATALOG = "workspace"


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


for source in SOURCE_SPECS:

    @dp.view(name=source.source)
    def _source_view(name=source.source):
        return _active_spark().readStream.table(_source_fqn(name))


def _sequence_expression(sequence_by: str | tuple[str, ...]):
    if isinstance(sequence_by, tuple):
        return F.struct(*(F.col(column) for column in sequence_by))
    return sequence_by


for flow in FLOW_SPECS:
    dp.create_streaming_table(name=flow.target)
    kwargs = {
        "target": flow.target,
        "source": flow.source,
        "keys": ["customer_id"],
        "sequence_by": _sequence_expression(flow.sequence_by),
        "stored_as_scd_type": flow.stored_as_scd_type,
        "except_column_list": list(flow.except_columns),
        "ignore_null_updates": flow.ignore_null_updates,
    }
    if flow.delete_condition is not None:
        kwargs["apply_as_deletes"] = F.expr(flow.delete_condition)
    if flow.track_history_except:
        kwargs["track_history_except_column_list"] = list(flow.track_history_except)
    if flow.system_sequence_by is not None:
        kwargs["system_sequence_by"] = flow.system_sequence_by
    dp.create_auto_cdc_flow(**kwargs)
