"""Tests für Simulations-i18n und lokalisierte Routen."""

from ecu.ragtail.locale_switch import simulation_public_path
from ecu.ui.web.i18n import simulation_i18n


def test_simulation_public_path_default_without_prefix() -> None:
    assert simulation_public_path("de", default_language_code="de") == "/simulation"


def test_simulation_public_path_non_default_with_prefix() -> None:
    assert simulation_public_path("en", default_language_code="de") == "/en/simulation"


def test_simulation_i18n_english_section_titles() -> None:
    i18n = simulation_i18n("en")
    assert i18n.text("sections.charts") == "Charts"
    assert i18n.text("setup.submit") == "Start simulation"


def test_simulation_i18n_table_headers() -> None:
    i18n = simulation_i18n("en")
    headers = i18n.text_list("tables.run_params_hdr")
    assert headers[1] == "Years"


def test_simulation_i18n_boundary_label() -> None:
    i18n = simulation_i18n("en")
    assert "Climate" in i18n.boundary_label("co2", fallback="Klima")


def test_simulation_i18n_fallback_to_german_for_missing_key() -> None:
    i18n = simulation_i18n("en")
    assert i18n.text("page_title") == "ECU — Simulation"


def test_simulation_i18n_chart_labels() -> None:
    i18n = simulation_i18n("de")
    labels = i18n.chart_labels()
    assert labels["x_axis"] == "Monat (Simulation)"
