# Web-Oberfläche (FastAPI + PyJSX)

## Styling: Tailwind CSS + Typography

Die Seite [`home.px`](home.px) und die Report-Ansicht in [`report.py`](report.py) (PyJSX mit `# coding: jsx`) laden **`/static/app.css`** (gebaut mit [Tailwind](https://tailwindcss.com/) und dem Plugin [`@tailwindcss/typography`](https://github.com/tailwindlabs/tailwindcss-typography)). [`app.py`](app.py) mountet `static/` unter `/static`.

Fließtext und Überschriften liegen in einem Container mit `prose prose-slate`; Raster und `<details>` stehen in `not-prose`, damit die Typography-Defaults die Tabellen nicht verzerren.

### CSS neu bauen

Nach Änderungen an `styles/input.css` oder an verwendeten Klassen in den `.px`-Dateien:

```bash
cd ui/web
npm install
npm run build:css
```

Die Ausgabe ist `static/app.css` (minifiziert); diese Datei sollte mit ins Repository, damit die App ohne Node auslieferbar bleibt.
