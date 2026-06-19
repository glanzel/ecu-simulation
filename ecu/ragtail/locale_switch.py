"""Sprachumschalter für den Site-Header (CMS-Seiten und feste Routen wie /simulation)."""
from __future__ import annotations

from dataclasses import dataclass

from ragtail.models import Page
from ragtail.routing import RouteMatch, get_active_locales, get_default_locale, get_translation, localized_path

LOCALE_SHORT_LABELS = {"de": "DE", "en": "EN"}
LANGUAGE_COOKIE = "ecu_lang"
SIMULATION_ROUTE = "/simulation"


@dataclass(frozen=True)
class LocaleSwitchOption:
    language_code: str
    label: str
    href: str
    is_current: bool


def locale_short_label(language_code: str) -> str:
    return LOCALE_SHORT_LABELS.get(language_code, language_code.upper())


def simulation_public_path(language_code: str, *, default_language_code: str) -> str:
    if language_code == default_language_code:
        return SIMULATION_ROUTE
    return f"/{language_code}{SIMULATION_ROUTE}"


async def cms_locale_switch_links(route: RouteMatch) -> list[LocaleSwitchOption]:
    """Direkte URLs zur Übersetzung bzw. Fallback-Seite je Locale."""
    locales = await get_active_locales()
    if len(locales) < 2:
        return []
    default = await get_default_locale()
    default_code = default.language_code if default else "de"
    page = route.page
    current_code = route.locale.language_code
    options: list[LocaleSwitchOption] = []
    for locale in locales:
        translated = await get_translation(page, locale.language_code)
        target_path = translated.path if translated is not None else page.path
        href = localized_path(target_path, locale.language_code, default_language_code=default_code)
        options.append(LocaleSwitchOption(
            language_code=locale.language_code,
            label=locale_short_label(locale.language_code),
            href=href,
            is_current=locale.language_code == current_code,
        ))
    return options


async def app_locale_switch_links(*, language_code: str, query: str = "") -> list[LocaleSwitchOption]:
    """Direkte Sprach-URLs für die Simulation (/simulation ↔ /en/simulation)."""
    locales = await get_active_locales()
    if len(locales) < 2:
        return []
    default = await get_default_locale()
    default_code = default.language_code if default else "de"
    query_suffix = f"?{query}" if query else ""
    options: list[LocaleSwitchOption] = []
    for locale in locales:
        path = simulation_public_path(locale.language_code, default_language_code=default_code)
        options.append(LocaleSwitchOption(
            language_code=locale.language_code,
            label=locale_short_label(locale.language_code),
            href=path + query_suffix,
            is_current=locale.language_code == language_code,
        ))
    return options


async def href_for_page_in_locale(page: Page, language_code: str) -> str:
    default = await get_default_locale()
    default_code = default.language_code if default else "de"
    translated = await get_translation(page, language_code)
    target_path = translated.path if translated is not None else page.path
    return localized_path(target_path, language_code, default_language_code=default_code)
