"""UI-Übersetzungen für die Simulationsseite (JSON-Locale-Dateien)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

LOCALES_DIR = Path(__file__).resolve().parent / "locales"
DEFAULT_LANGUAGE = "de"


@lru_cache(maxsize=8)
def _load_locale_file(language_code: str) -> dict[str, Any]:
    path = LOCALES_DIR / f"{language_code}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


class SimulationI18n:
    """Sprachgebundene UI-Texte für Simulation-Views und Chart-Payload."""

    def __init__(self, language_code: str) -> None:
        self.language_code = language_code.strip().lower() or DEFAULT_LANGUAGE
        self._messages = _load_locale_file(self.language_code)
        self._fallback = _load_locale_file(DEFAULT_LANGUAGE) if self.language_code != DEFAULT_LANGUAGE else {}

    def text(self, key: str) -> str:
        value = self._lookup(key, self._messages)
        if value is None and self._fallback:
            value = self._lookup(key, self._fallback)
        if value is None:
            return key
        if not isinstance(value, str):
            msg = f"Locale key '{key}' is not a string"
            raise TypeError(msg)
        return value

    def text_list(self, key: str) -> list[str]:
        value = self._lookup(key, self._messages)
        if value is None and self._fallback:
            value = self._lookup(key, self._fallback)
        if not isinstance(value, list):
            msg = f"Locale key '{key}' is not a list"
            raise TypeError(msg)
        return [str(item) for item in value]

    def boundary_label(self, boundary_key: str, *, fallback: str) -> str:
        boundaries = self._lookup("boundaries", self._messages) or self._lookup("boundaries", self._fallback) or {}
        if isinstance(boundaries, dict) and boundary_key in boundaries:
            return str(boundaries[boundary_key])
        return fallback

    def chart_labels(self) -> dict[str, str]:
        charts = self._lookup("charts", self._messages) or self._lookup("charts", self._fallback) or {}
        if not isinstance(charts, dict):
            return {}
        return {str(k): str(v) for k, v in charts.items() if isinstance(v, str)}

    @staticmethod
    def _lookup(key: str, root: dict[str, Any]) -> Any:
        node: Any = root
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node


def simulation_i18n(language_code: str) -> SimulationI18n:
    return SimulationI18n(language_code)
