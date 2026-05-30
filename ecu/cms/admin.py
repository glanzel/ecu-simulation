"""Oxyde-Admin für CMS-Inhalte."""
from oxyde_admin import FastAPIAdmin, Preset, PrimaryColor, Surface

from ecu.cms.models import Page

admin = FastAPIAdmin(
    title="ECU CMS",
    preset=Preset.AURA,
    primary_color=PrimaryColor.SKY,
    surface=Surface.SLATE,
)

admin.register(
    Page,
    list_display=["title", "slug", "in_menu", "header_image"],
    search_fields=["title", "content"],
    list_filter=["in_menu"],
    display_field="title",
    ordering=["title"],
    column_labels={
        "content": "Inhalt (Markdown)",
        "header_image": "Header-Bild",
        "in_menu": "Im Menü",
    },
    group="Inhalt",
    icon="pi pi-file",
)
