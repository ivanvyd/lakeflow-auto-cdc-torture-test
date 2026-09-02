"""Validation and quoting for user-supplied Unity Catalog identifiers."""

from __future__ import annotations

import re

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(
            f"invalid {label} {value!r}; use letters, digits, and underscores, "
            "starting with a letter or underscore"
        )
    return f"`{value}`"


def qualified_name(catalog: str, schema: str, table: str) -> str:
    return f"{qualified_schema(catalog, schema)}.{quote_identifier(table, 'table')}"


def qualified_schema(catalog: str, schema: str) -> str:
    return ".".join((quote_identifier(catalog, "catalog"), quote_identifier(schema, "schema")))
