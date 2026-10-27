# ADR 0010: Google sign-in (OpenID Connect), invitation only

Status: Accepted by the owner, 2026-10-27 (decision D-1). Implemented in slice 1G-1 (API); the web button, production wiring and the live check are slice 1G-2.

## Context
Production has no way to sign in. The owner chose Google over passkeys and e-mail links (no passwords or recovery flows to build and secure), and chose invitation-only registration so that only people the owner names can ever create an account. Sessions, CSRF, roles and default-deny entitlements already exist and are provider-agnostic: a provider only has to produce a `VerifiedIdentity`.

## Decision
1. **Protocol.** OpenID Connect authorization code flow with PKCE (S256), `state` and `nonce`, scope `openid email` only (no profile, name or photo). The redirect URI is built from `ALVO_PUBLIC_ORIGIN`, never from the request.
2. **Flow state** (state, nonce, PKCE verifier, expiry) lives in a signed, HttpOnly, Secure, `SameSite=Lax` cookie `__Host-alvo_oidc` for 10 minutes. It is signed with a key derived from the session secret and deleted at the callback, so a callback cannot be replayed. `Lax` is required because Google returns by a top-level redirect.
3. **ID token checks:** RS256 only, signature against Google's published keys (cached for an hour, refreshed once if a key id is unknown), issuer, audience (our client id), expiry (30 s leeway), our `nonce`, and `email_verified`. `alg: none`, HMAC tokens and unknown keys are rejected. The code is exchanged server to server and the client secret never reaches the browser.
4. **Identity key.** Users are keyed by Google's stable `sub`, never by email (emails change and can be recycled). The email is used once, to match an invitation.
5. **Invitations.** Table `sign_in_invites (email, role, created_at, expires_at)`. The owner creates one on the host: `python -m alvo.cli invite --email someone@example.com [--admin] [--days 14]` (1 to 90 days); `revoke-invite` removes it. At a first sign-in the invitation is matched by the verified, lower-cased email and **deleted atomically** (`DELETE ... RETURNING`), so two simultaneous sign-ins cannot both use it, and the new user gets the invited role. The email is not stored on the user. Nobody else gets an account or a session. Invite addresses must match Google's address exactly (Gmail dots and `+` tags are not normalised).
6. **First admin.** `invite --email you@gmail.com --admin`, then sign in. This keeps ADR 0004's rule that no web request can create an admin.
7. **Failures are quiet.** Every outcome redirects to `/?signin=ok|failed|not_invited` on our own origin; no provider text, token or exception reaches the user. "Not invited" is distinguishable on purpose: the person has just proved they own that address, so it leaks nothing, and it is the message they need. Logs record the reason, never the email.
8. **Abuse limits.** `start` and `callback` are limited per client address (`auth_attempts_per_minute`, ADR 0009) because the callback makes outbound calls.
9. **Outbound access.** The API contacts exactly three fixed https addresses (Google's authorization, token and key endpoints). The fetcher refuses any other URL, has a 5 s timeout and a 256 KiB response cap. In production the API therefore needs an internet route (slice 1G-2: an `egress` network for the API only; approved by the owner on 2026-10-27).
10. **Configuration.** `ALVO_IDENTITY_PROVIDER=google`, `ALVO_GOOGLE_CLIENT_ID`, and `ALVO_GOOGLE_CLIENT_SECRET` from a secret file. Startup fails if the id does not look like a Google client id or the secret is missing, short or a placeholder. The mock login stays forbidden in production.
11. **Dependency.** `PyJWT[crypto]` (brings `cryptography`, which has ARM64 wheels) for signature verification. HTTP uses the standard library, so no new HTTP client.

## Consequences
- Google learns that the person signs in to Alvo; Alvo learns only a stable id and a verified address (kept only until first sign-in). A Google account is required.
- Losing access to the Google account means losing the Alvo account; there is no password reset to attack, and the owner can re-invite a new address.
- Anyone with an unused, unexpired invitation for an address can claim it by signing in as that address; invitations are short-lived and revocable for that reason.
- Outbound access from the API widens the blast radius of an API compromise (exfiltration). Accepted for now; an allow-listing egress proxy can be added later, and Phase 3 provider calls need the same route anyway.
- Google's OAuth consent screen can stay in "Testing" mode for a handful of invited people; publishing it is only needed to go beyond 100 users or avoid test-mode expiry notices.
