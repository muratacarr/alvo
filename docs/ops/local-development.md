# Local development

All commands run from the repository root. No real secrets are involved: the generator below creates random throwaway values in `secrets/` (gitignored).

## First run

```
python apps/api/scripts/make_dev_secrets.py     # once
docker compose up --build -d
docker compose run --rm api alembic upgrade head
```

Open **http://localhost:8080** (use exactly this address: the API checks the `Origin` header against it).

| Address | What |
|---|---|
| `http://localhost:8080/` | The web app (PWA) |
| `http://localhost:8080/docs` | Interactive API docs (development only) |
| `http://localhost:8080/healthz` | Web server health |

The API and the database are **not** published on the host. Everything the browser needs goes through the web container, which serves the app and forwards `/api` to the API, so the browser sees a single origin.

Sign in with any name on the development sign-in form (for example `alice`). Use a private window with another name to check that two users cannot see each other's data.

## What you can do in the web app

1. Sign in (development form), create a project.
2. Click the project title to open it. On the left add **modules** and **topics**; click a topic (mouse, or Tab to the tree, arrow keys and Enter) to see its items. The address keeps the chosen topic (`?topic=...`), so a link or a refresh returns to the same place.
3. **Add item** opens a dialog (type, prompt, optional sample answer, translation, keywords, tags, difficulty). Editing sends only the fields you changed; clearing an optional field removes it. A duplicate (same type and prompt in the project) is explained and the dialog stays open.
4. **Archive** an item; tick **Show archived items** to see archived ones. An archived project is read-only.

5. **Import and export** (link next to the project title): download the sample file or the JSON schema, choose a JSON file (up to 2 MiB), **Preview import** to see what would be added, skipped as duplicates or rejected as invalid, then **Import**. Nothing is written until you confirm. Importing the same file twice adds nothing the second time. **Export this project** downloads everything in the same format.

6. **Manage modules and topics** (button above the tree): rename or archive a module or topic. Archiving asks first; archiving a module hides its topics and items, and there is no restore button yet. Each item has **Move** to put it in another topic (the dialog lists topics as `Module › Topic`; a duplicate in the target topic is explained).

Not in the app yet: restoring archived modules/topics (the API has no restore either), reordering.

## After pulling new code

```
docker compose up --build -d
docker compose run --rm api alembic upgrade head
```

## Looking at the database

Run `psql` inside the container; nothing is opened on your machine:

```
docker compose exec db psql -U alvo_app -d alvo
```

## Stopping

```
docker compose down        # keeps the data
docker compose down -v     # also deletes the database volume
```

## Create an admin (for the admin API)

```
docker compose run --rm api python -m alvo.cli create-admin --provider mock --subject boss
```

## Working on the web app without Docker

```
cd apps/web
npm ci --ignore-scripts
npm run dev          # http://localhost:5173, proxies /api to http://localhost:8000
```

This needs the API on port 8000 with `ALVO_PUBLIC_ORIGIN=http://localhost:5173`. The Docker route above is simpler and is what CI tests.

## Browser tests (Playwright)

They drive the real app in a real browser against the running stack: the full journey (create, export, import, second user cannot see it), no Content-Security-Policy violations, accessibility including color contrast, no sideways scrolling on a phone-sized screen, and a service worker that never stores API responses.

```
docker compose up --build -d
docker compose run --rm api alembic upgrade head
cd apps/web
npm ci --ignore-scripts
# once, if you do not want to use your installed Chrome: npx playwright install chromium
PW_CHANNEL=chrome npm run e2e        # PowerShell: $env:PW_CHANNEL="chrome"; npm run e2e
```

Each run signs in with fresh random user names, so runs never see each other's data. CI runs the same tests (job `e2e`).

## Checks before opening a PR

```
cd apps/api && uv run pytest -q && uv run ruff check . && uv run mypy src tests scripts alembic
cd apps/web && npm run lint && npm run typecheck && npm test && npm run build && npm run check:build
# with the stack running: cd apps/web && npm run e2e
```
