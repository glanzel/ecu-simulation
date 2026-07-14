"""Beim App-Start: Standardseiten und Menüs anlegen, falls noch nicht vorhanden."""
from __future__ import annotations

from cms.pages import ContentPage
from ragtail.menus import create_menu, create_menu_item, get_menu
from ragtail.models import Locale, Page
from ragtail.pages import create_page
from ragtail.seed import ensure_default_locale
from ragtail.sites import get_site_root_page, get_tree_root


async def seed_default_locale() -> None:
    """Legt die Default-Locale ``de`` an, wenn die Datenbank noch leer ist."""
    if await Locale.objects.first() is not None:
        return
    await ensure_default_locale(language_code="de", display_name="Deutsch")


async def _ensure_default_pages(locale: Locale) -> Page | None:
    """Legt Home und About an, wenn noch keine Startseite existiert."""
    existing_home = await get_site_root_page(locale)
    if existing_home is not None:
        return existing_home
    tree_root = await get_tree_root(locale)
    if tree_root is None:
        return None
    home_page = await create_page(
        title="Home",
        slug="home",
        locale=locale,
        parent=tree_root,
        live=True,
        page_model=ContentPage,
        body="## Willkommen\n\nInhalt bitte im Admin ergänzen.",
    )
    await create_page(
        title="About",
        slug="about",
        locale=locale,
        parent=home_page,
        live=True,
        page_model=ContentPage,
        body="## About\n\nInhalt bitte im Admin ergänzen.",
    )
    return home_page


async def seed_default_pages() -> None:
    locale = await Locale.objects.filter(is_default=True, is_active=True).first()
    if locale is None:
        return
    await _ensure_default_pages(locale)


async def seed_main_menu() -> None:
    locale = await Locale.objects.filter(is_default=True, is_active=True).first()
    if locale is None:
        return
    if await get_menu("main", language_code=locale.language_code) is not None:
        return
    main_menu = await create_menu(name="Hauptmenü", slug="main", locale=locale)
    home_page = await get_site_root_page(locale)
    if home_page is not None:
        await create_menu_item(menu=main_menu, label=home_page.title or "Home", page=home_page, sort_order=0)
        about_page = await Page.objects.filter(path="/about/", locale_id=locale.id).first()
        if about_page is not None:
            await create_menu_item(menu=main_menu, label=about_page.title or "About", page=about_page, sort_order=5)
    await create_menu_item(menu=main_menu, label="Simulation", url="/simulation", sort_order=10)


async def _ensure_impressum_page(locale: Locale, *, parent: Page) -> Page:
    existing = await Page.objects.filter(path="/impressum/", locale_id=locale.id).first()
    if existing is not None:
        return existing
    return await create_page(
        title="Impressum",
        slug="impressum",
        locale=locale,
        parent=parent,
        live=True,
        page_model=ContentPage,
        body="## Impressum\n\nInhalt bitte im Admin ergänzen.",
    )


async def seed_footer_menu() -> None:
    locale = await Locale.objects.filter(is_default=True, is_active=True).first()
    if locale is None:
        return
    if await get_menu("footer", language_code=locale.language_code) is not None:
        return
    home_page = await get_site_root_page(locale)
    if home_page is None:
        return
    impressum_page = await _ensure_impressum_page(locale, parent=home_page)
    footer_menu = await create_menu(name="Footer", slug="footer", locale=locale)
    await create_menu_item(menu=footer_menu, label="Impressum", page=impressum_page, sort_order=0)


async def seed_menus() -> None:
    await seed_default_locale()
    await seed_default_pages()
    await seed_main_menu()
    await seed_footer_menu()
