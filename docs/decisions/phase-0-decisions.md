# Phase 0 Decisions and Open Questions

## Decisions needed from the owner

- **D-1 Identity (BLOCKING for 1B).** Sign in with ChatGPT is limited-trial, no self-service. Options: (A) submit the interest form, build everything else behind an `IdentityProvider` port with a test-only mock, resume 1B if approved; (B) approve a different provider now (recommended candidate to discuss: Google OIDC, or passkeys); (C) wait. No automatic substitution.
- **D-2 Repository visibility.** Public from day one (spec default) or private until the public-release gate?
- **D-3 Domain and ingress.** Own a domain? Cloudflare Tunnel acceptable?
- **D-4 Backup destination** (second machine, object storage, cloud drive) and who holds the encryption key.
- **D-5 Spend limits.** Is paid speech wanted at all in the near term? If yes, monthly USD ceilings.
- **D-6 Pi facts**: SSD or microSD, current Ubuntu version, CGNAT status.

## Updates 2026-10-26
- **D-1 resolved for now:** development uses the mock identity adapter; the real sign-in method stays open. The goal of using users' ChatGPT subscriptions was dropped (ADR 0003 superseded by ADR 0004).
- **D-5 refined:** paid AI is wanted (DeepSeek LLM, OpenAI STT/TTS). Still needed from the owner: per-feature default limits and the global monthly cap. Until set, every cap is 0.
- **D-7 Admin bootstrap:** proposed as a host-side command run by the operator.
- **D-8 DeepSeek data processing:** the owner must accept sending minimized learner text to a China-hosted provider with explicit user consent, and decide whether legal review (KVKK/GDPR) is required before enabling it.

## Assumptions
Single owner and few users; Turkish/English UI language TBD (default: English UI); no offline mode in MVP.

## ADR index (to be written as files at 1A-1)
0001 modular monolith; 0002 server-side sessions; 0003 no shared contracts package; 0004 import-linter boundaries; 0005 FSRS adapter; 0006 pull-based deploy; 0007 Cloudflare Tunnel (pending D-3); 0008 PostgreSQL rate limiting.

## Not done in this session
No host commands were run on the Pi; the OWASP/NIST reference versions were not re-verified; the OpenAI help-center page returned 403; no code or git repository was created.
