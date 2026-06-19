"""Beim App-Start: Menü ``main`` anlegen, falls noch nicht vorhanden."""
from __future__ import annotations

from ragtail.menus import create_menu, create_menu_item, get_menu
from ragtail.models import Locale, Page
from ragtail.routing import get_site_for_locale


async def seed_main_menu() -> None:
    locale = await Locale.objects.filter(is_default=True, is_active=True).first()
    if locale is None:
        return
    if await get_menu("main", language_code=locale.language_code) is not None:
        return
    main_menu = await create_menu(name="Hauptmenü", slug="main", locale=locale)
    site = await get_site_for_locale(locale)
    home_page = await Page.objects.get_or_none(id=site.root_page_id) if site and site.root_page_id else None
    if home_page is not None:
        await create_menu_item(menu=main_menu, label=home_page.title or "Home", page=home_page, sort_order=0)
    await create_menu_item(menu=main_menu, label="Simulation", url="/simulation", sort_order=10)
