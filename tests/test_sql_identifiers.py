import pytest

from src.sql_identifiers import qualified_name, quote_identifier


def test_qualified_name_quotes_each_identifier() -> None:
    assert qualified_name("workspace", "experiment", "target") == (
        "`workspace`.`experiment`.`target`"
    )


@pytest.mark.parametrize("value", ["bad-name", "two words", "x; DROP SCHEMA y", "1catalog"])
def test_invalid_identifier_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        quote_identifier(value, "catalog")
