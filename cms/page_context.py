"""Gemeinsamer Template-Kontext für öffentliche CMS-Seiten."""
from __future__ import annotations

from cms.locale_switch import cms_locale_switch_links
from ragtail.menus import get_menu_tree
from ragtail.routing import RouteMatch


async def cms_page_context(request, route: RouteMatch) -> dict:
    _ = request
    language_code = route.locale.language_code
    return {
        "menu_items": await get_menu_tree("main", language_code=language_code),
        "footer_items": await get_menu_tree("footer", language_code=language_code),
        "language_code": language_code,
        "locale_switch_links": await cms_locale_switch_links(route),
    }
