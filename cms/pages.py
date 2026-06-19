"""Projektseitige Seitentypen für Ragtail."""
from __future__ import annotations

from oxyde import Field

from cms.locale_switch import cms_locale_switch_links
from ragtail.menus import get_menu_tree
from ragtail.models import Page
from ragtail.page_types import register_page_model
from ragtail.routing import RouteMatch


@register_page_model
class ContentPage(Page):
    """Inhaltsseite — ``body`` ist Markdown/Rich Text (Admin-Widget)."""

    body: str | None = Field(default=None, db_type="TEXT")

    async def get_context(self, request, route: RouteMatch) -> dict:
        _ = request
        menu_items = await get_menu_tree("main", language_code=route.locale.language_code)
        return {
            "menu_items": menu_items,
            "language_code": route.locale.language_code,
            "locale_switch_links": await cms_locale_switch_links(route),
        }
