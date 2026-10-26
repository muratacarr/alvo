# Identity Feasibility: Sign in with ChatGPT

Status: **BLOCKED for production use (product decision required)**
Checked: 2026-10-26 against official OpenAI pages (listed below). Re-verify before Phase 1B.

## Evidence

| Claim | Source |
|---|---|
| Sign in with ChatGPT "is currently available to selected commercial partners through a limited trial"; waitlist via OpenAI representative. | developers.openai.com/siwc/website |
| Client IDs (`oaiapp_...`) come from "Request a client ID"; access is "offered to a select group of commercial partners"; entry is an interest form (waitlist). No self-service path or requirements are documented. | developers.openai.com/siwc/request-client-id |
| "ChatGPT plan usage is available to all open-source partners and selected private clients." Plus/Pro users can use plan allowance in participating apps. | developers.openai.com/siwc/quickstart |
| Protocol: OAuth 2.0 authorization code + PKCE, OpenID Connect; scopes `openid`, `profile`, `email`; exact registered callback URL per environment; public and confidential clients. | developers.openai.com/siwc/website |
| Plan usage for open-source apps has a *separate* authorization/registration flow from identity sign-in. | developers.openai.com/siwc/website |
| Help-center article (user-facing) describes global availability to ChatGPT users; it could not be fetched (HTTP 403), so its content is only known via search summary. | help.openai.com/en/articles/20001410 |

## Conclusions

1. Identity sign-in is **not self-service**. Alvo (a personal, self-hosted project) is not known to qualify as a "selected commercial partner". Eligibility is unknown until OpenAI responds to the interest form.
2. Identity and plan usage are separate. Login never grants LLM or paid API usage (matches spec section 4).
3. The documented protocol is standard OIDC, so an `IdentityProvider` port is cheap to build and test with a mock adapter.
4. No workaround (cookie extraction, unofficial endpoints, password sign-in) is acceptable.

## Open items for the owner

- Submit the interest form (owner action; do not put the client ID, callback URLs or any response in the public repo).
- Decide the fallback if access is not granted (see Decision D-1 in `docs/decisions/phase-0-decisions.md`).
- Whether Alvo's source is open source matters: an open-source flow with plan usage is documented separately; its eligibility for a personal PWA is unverified.

## Impact

Blocks Phase 1B only. Phase 1A, 1C-1E can proceed behind an `IdentityProvider` port with a non-production mock adapter that is unreachable in production configuration.
