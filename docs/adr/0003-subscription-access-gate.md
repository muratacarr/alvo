# ADR 0003: Application access requires a linked ChatGPT subscription (owner decision)

Status: **Superseded by ADR 0004** on 2026-10-26. Kept for history; do not implement.

## Why it was dropped
The decision required every user to link a ChatGPT subscription before using the app. Checking OpenAI's documentation showed that:
- ChatGPT plan usage is documented for open-source and locally run tools (loopback callback, credentials on the user's own disk); remotely hosted or paid apps need a separate OpenAI approval, and eligibility for this project is unknown.
- Requests made with a user's plan do not pass through our server, so the server could not verify or enforce a subscription gate.

The owner then chose DeepSeek and OpenAI API keys with admin-granted, limited entitlements instead. See ADR 0004.
