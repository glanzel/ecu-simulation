# CMS-App (`ecu.cms`)

Django-ähnliche App im gleichen FastAPI-Prozess wie `ecu.ui.web` — kein separater Dienst.

## Einbindung

`ecu.ui.web.app` ruft `setup_cms(app)` auf:

- Admin: `/admin`
- CMS-Seiten: `/seite/{slug}`
- Medien: `/cms-media/…`
- Menü: Seiten mit `in_menu=True` erscheinen in der Header-Navigation

## Page-Modell

| Feld | Beschreibung |
|------|--------------|
| `title` | Seitentitel |
| `slug` | URL-Segment |
| `content` | **Markdown** (wird auf der Website zu HTML gerendert) |
| `header_image` | optional, z. B. `/cms-media/bild.jpg` |
| `in_menu` | im Site-Menü anzeigen |

## Datenbank

```bash
uv sync --group web
mkdir -p ecu/cms/data
cd ecu/cms && uv run oxyde migrate
```

Im **Docker-/Coolify-Image** führt `scripts/docker-entrypoint.sh` vor dem Start von Uvicorn automatisch `oxyde migrate` aus (Arbeitsverzeichnis: installiertes Paket `ecu/cms`).

## Header-Bild

```bash
curl -F "file=@bild.jpg" http://127.0.0.1:8000/api/cms/upload-header
```

Pfad aus der Antwort im Admin unter **Header-Bild** speichern.
