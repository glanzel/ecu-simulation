"""Markdown-Inhalt von CMS-Seiten nach HTML."""
import markdown


class PageContentRenderer:
    """Wandelt im Admin gepflegtes Markdown in HTML für die Anzeige um."""

    def __init__(self) -> None:
        self._md = markdown.Markdown(extensions=["fenced_code", "tables", "nl2br", "sane_lists"])

    def to_html(self, markdown_source: str) -> str:
        self._md.reset()
        return self._md.convert(markdown_source or "")


_renderer = PageContentRenderer()


def render_page_content(markdown_source: str) -> str:
    return _renderer.to_html(markdown_source)
