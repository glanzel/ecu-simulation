"""CMS-Datenmodelle."""
import re
import unicodedata
from pathlib import Path

from oxyde import Model, Field

CMS_DIR = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{CMS_DIR / 'data' / 'cms.db'}"


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "seite"


class Page(Model):
    """CMS-Seite mit optionaler Menü-Anzeige."""

    id: int | None = Field(default=None, db_pk=True)
    title: str = Field(max_length=200)
    slug: str = Field(max_length=200, db_unique=True)
    content: str = ""  # Markdown (wird beim Anzeigen zu HTML gerendert)
    header_image: str | None = Field(default=None, max_length=500)
    in_menu: bool = Field(default=False)

    class Meta:
        is_table = True
        table_name = "pages"
