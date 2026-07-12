"""Projekteigene StreamField-Blöcke für Ragtail."""
from __future__ import annotations

from ragtail.streamfield import CharBlock, StructBlock, URLBlock

_CTA_BUTTON_CLASSES = (
    "ecu-cta-button inline-flex items-center gap-1.5 my-4 px-4 py-2 text-sm font-medium "
    "text-white bg-report-accent hover:opacity-90 rounded-sm no-underline transition-opacity"
)

_CTA_ARROW = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="ecu-cta-arrow" '
    'aria-hidden="true" focusable="false">'
    '<path d="M10 7l5 5-5 5" fill="none" stroke="currentColor" stroke-width="2.25" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


class CallToActionBlock(StructBlock):
    """Link im Button-Stil — passt zum ECU-Seitenlayout (Header/Simulation)."""

    def __init__(self) -> None:
        super().__init__(
            name="call_to_action",
            label="Call to Action",
            fields={
                "label": CharBlock(name="label", label="Button-Text"),
                "url": URLBlock(name="url", label="Ziel-URL"),
            },
            template=(
                f'<a href="{{url}}" class="{_CTA_BUTTON_CLASSES}">'
                f'<span class="leading-none">{{label}}</span>'
                f"{_CTA_ARROW}"
                f"</a>"
            ),
        )
