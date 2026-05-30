"""CMS-Menü für die gemeinsame Site-Navigation."""
from ecu.cms.models import Page


async def menu_links() -> list[tuple[str, str]]:
    pages = await Page.objects.filter(in_menu=True).order_by("title").all()
    return [(p.title, f"/seite/{p.slug}") for p in pages]
