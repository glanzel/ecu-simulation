"""CMS-Routen (Teil der gemeinsamen FastAPI-App)."""
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from ecu.cms.content import render_page_content
from ecu.cms.menu import menu_links
from ecu.cms.models import Page, slugify
from ecu.cms.views import cms_page

router = APIRouter(tags=["cms"])
MEDIA_DIR = Path(__file__).resolve().parent / "media"


@router.get("/seite/{slug}", response_class=HTMLResponse)
async def page_detail(slug: str) -> HTMLResponse:
    rows = await Page.objects.filter(slug=slug).all()
    if not rows:
        raise HTTPException(status_code=404, detail="Seite nicht gefunden")
    page = rows[0]
    nav = await menu_links()
    view = cms_page(page.title, render_page_content(page.content), page.header_image, nav)
    return HTMLResponse(str(view))


@router.post("/api/cms/upload-header")
async def upload_header_image(file: UploadFile):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Nur Bilddateien erlaubt")
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "bild.jpg").suffix or ".jpg"
    safe_name = slugify(Path(file.filename or "bild").stem) + suffix
    target = MEDIA_DIR / safe_name
    counter = 1
    while target.exists():
        target = MEDIA_DIR / f"{slugify(Path(file.filename or 'bild').stem)}-{counter}{suffix}"
        counter += 1
    target.write_bytes(await file.read())
    return {"path": f"/cms-media/{target.name}"}
