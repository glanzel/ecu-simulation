"""Projektseitige Seitentypen für Ragtail."""
from __future__ import annotations

from oxyde import Field

from cms.page_context import cms_page_context
from cms.stream_blocks import CallToActionBlock
from ragtail.models import Page
from ragtail.page_types import register_page_model
from ragtail.routing import RouteMatch
from ragtail.streamfield import HtmlTextBlock, MarkdownTextBlock, StreamField, StreamValue, render_stream_value_html


@register_page_model
class ContentPage(Page):
    """Inhaltsseite — ``body`` ist Markdown/Rich Text (Admin-Widget)."""

    body: str | None = Field(default=None, db_type="TEXT")

    async def get_context(self, request, route: RouteMatch) -> dict:
        return await cms_page_context(request, route)


@register_page_model
class StreamPage(Page):
    """Flexible Inhaltsseite mit StreamField (Markdown, HTML, Call to Action)."""

    content: StreamValue | None = StreamField(
        [
            MarkdownTextBlock(),
            HtmlTextBlock(),
            CallToActionBlock(),
        ],
        default=None,
    )

    async def get_context(self, request, route: RouteMatch) -> dict:
        context = await cms_page_context(request, route)
        context["stream_html"] = await render_stream_value_html(self.content)
        return context
