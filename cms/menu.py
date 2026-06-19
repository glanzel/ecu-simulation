"""Navigation aus Ragtail-Menüs für die gemeinsame Site-Header-Leiste."""
from ragtail.menus import get_menu_tree
from ragtail.routing import get_default_locale, get_locale, localized_path

from cms.locale_switch import SIMULATION_ROUTE, simulation_public_path


async def menu_links(language_code: str | None = None) -> list[tuple[str, str]]:
    locale = await get_locale(language_code)
    default = await get_default_locale()
    default_code = default.language_code if default else "de"
    resolved_code = locale.language_code if locale else default_code
    items = await get_menu_tree("main", language_code=resolved_code)
    sim_path = simulation_public_path(resolved_code, default_language_code=default_code)
    links: list[tuple[str, str]] = []
    for item in items:
        href = item.href
        if href == SIMULATION_ROUTE or href.startswith(f"/{resolved_code}{SIMULATION_ROUTE}"):
            href = sim_path
        elif href.startswith("/") and not href.startswith(("/locale/", "/static/", "/admin")):
            href = localized_path(href, resolved_code, default_language_code=default_code)
        links.append((item.label, href))
    return links
