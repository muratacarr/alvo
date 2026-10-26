# ADR 0004: AI providers (DeepSeek, OpenAI speech) and default-deny entitlements

Status: Accepted by the owner, 2026-10-26. Supersedes ADR 0003. Implementation is split: entitlement foundation in slice 1B-2 (no provider calls); provider calls in Phase 3.

## Context
The owner wants AI features without relying on users' ChatGPT subscriptions. The delegated-subscription flow is documented for open-source and locally run tools; remotely hosted or paid apps need a separate OpenAI approval, and the server cannot verify or relay a subscription. See `docs/architecture/identity-feasibility.md`.

## Decision
1. **LLM text generation:** DeepSeek through its OpenAI-compatible API, using the owner's server-side API key.
2. **Speech:** OpenAI API with the owner's server-side key. Whisper is speech-to-text only; text-to-speech uses a separate OpenAI model. Browser speech remains the free default and is never silently replaced by a paid call.
3. **Default deny:** a new user has no access to any paid AI feature. There is no implicit grant from sign-in, role or session.
4. **Admin grants:** only an admin can grant a user access, per feature (`llm`, `stt`, `tts`) and each with its own limits. Grants and changes are audited and require recent re-authentication.
5. **Limits always apply to a granted user** (calls per minute and day, daily and monthly budget, audio seconds, text length, concurrency).
6. **Exempt users:** an admin may mark selected users `exempt`, which removes their *per-user quotas only*. Exempt users are still bound by per-request size limits, the global budget, the global concurrency cap, the provider hard limit and the global kill switch. Nobody is truly unlimited.
7. **Admin bootstrap:** the first admin is created by an operator command run on the host (not by a web endpoint and not by an email-matching setting), so no request can self-promote.
8. **No ChatGPT-subscription path in the MVP.** A local open-source helper that uses the user's own plan may be evaluated later as an optional, separate component.

## Consequences
- Owner pays for DeepSeek and OpenAI usage; cost controls from the spend policy are release blockers for Phase 3.
- Numeric limits are an owner decision (D-5). Until set, every cap is 0, which means no paid call can happen.
- **Privacy:** DeepSeek's own policy (as reported by secondary analyses; the policy text itself was not reviewed in this session) says data is processed and stored in China and covers training on inputs with an opt-out. Learner text sent to DeepSeek is a cross-border transfer to a country without an EU adequacy decision. Before enabling it: review DeepSeek's current terms, show an explicit disclosure and consent, send only the minimum text (no names, emails or unrelated data), and treat KVKK/GDPR applicability as an open legal question (D-8).
- Model names, prices and limits come from official provider pages at implementation time. Observed on 2026-10-26: base URL `https://api.deepseek.com`, models `deepseek-flash` and `deepseek-v4-pro`; prices not recorded here.
