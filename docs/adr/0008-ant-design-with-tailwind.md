# ADR 0008: Ant Design components with Tailwind layout, and a relaxed `style-src`

Status: Accepted by the owner, 2026-10-26 (slice 1E-2). Partly supersedes ADR 0007 (UI libraries and the Content-Security-Policy).

## Context
ADR 0007 chose hand-written Tailwind components and a strict CSP. The owner prefers Ant Design for the interface, mainly for the components the next screens need (tree, table, upload, modal, steps).

## Facts checked before deciding (2026-10-26)
- `antd` 6.6.6 (14 days old when chosen), `@ant-design/cssinjs` 2.1.2 pinned to the same version antd uses so only one copy exists.
- `npm audit`: 0 vulnerabilities. Packages: 548 to 615 (+67).
- JavaScript gzip: 96 kB to 276 kB (about 2.9 times) with the components used so far.
- Ant Design generates its styles at run time (CSS-in-JS): it creates `<style>` elements and inline `style` attributes.
- A CSP nonce is supported by the library, but it cannot work here: the nonce must change on every response, while the service worker precaches a fixed `index.html`.

## Decision
1. **Ant Design provides the components; Tailwind provides page layout and spacing.** Imports always come from the `antd` package root so unused components are dropped.
2. **Cascade layers decide the winner.** `index.css` declares `@layer theme, base, antd, components, utilities;` and the app wraps everything in `<StyleProvider layer>`. A test checks that Ant Design's component rules are inside `@layer antd` (only `--ant-*` custom properties and keyframes may sit outside), and fails if the layer option is removed.
3. **CSP:** `script-src 'self'` stays strict (no inline, no eval, no other host). `style-src` becomes `'self' 'unsafe-inline'`, the only relaxation, and only for styles. A policy test enforces exactly that.
4. **Theme:** colours are set explicitly for WCAG AA contrast (the library's defaults, for example its blue primary, are below 4.5:1 on white). Motion is disabled when the user prefers reduced motion.
5. Interface text stays English; Ant Design's default locale is used.

## Consequences
- **Security:** a successful style injection is easier than before (CSS can hide or rearrange parts of the page, and in rare cases leak data through selectors). It cannot run code. The strict script policy, the lint ban on `dangerouslySetInnerHTML` and text-only rendering remain the main defences.
- **Cost:** +67 packages to keep updated (Dependabot is configured), +180 kB gzip on first load. Route-level code splitting and a vendor chunk are the planned remedies once measured in a real browser.
- **Accessibility:** `Alert` always has `role="alert"`, so it is used only for real alerts (static notes are plain paragraphs). `List.Item actions` creates nested list items, so buttons are placed in the item content instead. Contrast of the chosen colours still has to be confirmed with axe in a real browser.
- **Reversal:** if the style relaxation becomes unacceptable, the options are removing the PWA shell cache and using per-response nonces, or replacing Ant Design with unstyled primitives.
