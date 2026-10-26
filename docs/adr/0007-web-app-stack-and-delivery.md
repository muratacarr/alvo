# ADR 0007: Web application stack and how it is delivered

Status: Accepted (slice 1E-1)

## Decision
- **Stack:** React 19, TypeScript (strict), Vite, Tailwind CSS 4, React Router, TanStack Query. No global state library. Tests: Vitest, Testing Library and axe-core (accessibility) in jsdom; Playwright end-to-end tests come in a later slice.
- **One origin.** An nginx container serves the built PWA and forwards `/api` to the API. The browser therefore talks to a single origin: the API can check the exact `Origin` header, needs no CORS, and cookies stay `SameSite=Lax`. The API and the database are no longer published on the host; the web container is the only entrypoint (loopback in development, HTTPS edge in production).
- **No browser storage.** The CSRF token lives in memory only; the session is an `HttpOnly` cookie. Application code may not use `localStorage` or `sessionStorage` (ESLint rule, with tests proving nothing is written).
- **Untrusted text is rendered as text.** `dangerouslySetInnerHTML` is forbidden by lint; a test renders an XSS payload and asserts no element is created.
- **Strict Content-Security-Policy** (`script-src 'self'; style-src 'self'`, no inline code, no other origins). The build check fails if `index.html` contains inline script or style, or if a bundle contains something that looks like a credential. Only `/docs` (development) relaxes the policy for Swagger UI.
- **Service worker caches the application shell only.** Navigation fallback is denied for `/api`, `/docs` and `/openapi.json`; runtime caching is disabled so personal data never reaches the cache. Offline learning is not an MVP promise; the UI reports when the server cannot be reached.
- **Dependencies:** exact versions, lockfile, `npm ci --ignore-scripts`, `npm audit` in CI, versions chosen at least 14 days after release, Dependabot with a cooldown. Each new package is a trust decision.
- **Images:** Node build stage and an unprivileged nginx runtime pinned by digest, running as uid 101 on a read-only filesystem with all capabilities dropped. Unused nginx modules and `curl` are removed from the runtime image.
- **Development sign-in** is a build-time switch (`VITE_DEV_LOGIN`); release builds default to hiding it, and the API refuses the mock provider in production anyway.

## Consequences
- The Swagger address moves to `http://localhost:8080/docs` and `ALVO_PUBLIC_ORIGIN` is `http://localhost:8080` in the development Compose file.
- Interface text is English; internationalisation is not part of this slice.
- `eslint` stays on version 9 until `eslint-plugin-jsx-a11y` supports version 10 (accessibility rules matter more than the newest linter).
- TypeScript stays on 6.0.x until `typescript-eslint` supports 7.
