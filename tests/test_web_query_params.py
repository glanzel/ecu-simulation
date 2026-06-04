"""GET-Query-Hilfen für die Web-Route."""

from ecu.simulation.run_params import optional_query_int


def test_optional_query_int_empty_string_is_none() -> None:
    assert optional_query_int("") is None
    assert optional_query_int("   ") is None
    assert optional_query_int(None) is None


def test_optional_query_int_parses_value() -> None:
    assert optional_query_int("42") == 42
    assert optional_query_int(7) == 7
