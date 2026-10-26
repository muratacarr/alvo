# ADR 0003: Application access requires a linked ChatGPT subscription (owner decision)

Status: Proposed, implementation in slice 1B-2. Recorded 2026-10-26.

## Context
The owner decided that a user first signs in to Alvo with an application account, and must then link a ChatGPT subscription inside the app. A user without a linked subscription cannot use the application at all.

This deviates from the master specification, which says free practice must remain available when AI features are unavailable, and keeps sign-in separate from usage entitlement.

## Facts (checked 2026-10-26 against official OpenAI pages)
- ChatGPT plan usage is available to "all open-source partners and selected private clients"; sign-in is a limited trial for selected commercial partners. Eligibility of this project is unknown and there is no self-service registration.

## Decision
- Access is enforced by one server-side policy, `access_policy`, applied as a dependency to every route except health, authentication and the "link subscription" endpoints.
- Supported policy values: `require_subscription` (owner's choice) and `ai_only` (free practice stays open, only AI features need the link). Switching is a configuration change, not a redesign.
- A user's subscription state can only be set by a server-side verified provider adapter, never from client input.

## Consequences and risk (owner informed)
- Until the subscription-linking flow is officially available and implemented, no real user can pass the gate in production. Development uses a mock adapter that is unreachable in production.
- If OpenAI does not grant eligibility, the product cannot be used as specified; the fallback is to switch to `ai_only` or choose another access model.
