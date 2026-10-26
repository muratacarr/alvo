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

## Checks before opening a PR

```
cd apps/api && uv run pytest -q && uv run ruff check . && uv run mypy src tests scripts alembic
cd apps/web && npm run lint && npm run typecheck && npm test && npm run build && npm run check:build
```
