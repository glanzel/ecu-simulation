# Web UI (FastAPI + PyJSX)

## Styling: Tailwind CSS + Typography

The simulation at [`/simulation`](app.py) is rendered in [`simulation_view.px`](simulation_view.px) (imported via [`simulation_page.py`](simulation_page.py), PyJSX with `# coding: jsx`). All pages load **`/static/app.css`** (built with [Tailwind](https://tailwindcss.com/) and the [`@tailwindcss/typography`](https://github.com/tailwindlabs/tailwindcss-typography) plugin). [`app.py`](app.py) mounts `static/` at `/static`; `/` redirects to `/simulation`.

Body text and headings sit in a container with `prose prose-slate`; grids and `<details>` use `not-prose` so typography defaults do not distort tables.

### Rebuild CSS

After changes to `styles/input.css` or to classes used in `.px` files:

```bash
cd ui/web
npm install
npm run build:css
```

Output is `static/app.css` (minified); commit this file so the app can be served without Node.
