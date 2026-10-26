# Speech Provider Decision

Decision (updated 2026-10-26, see ADR 0004): the free path stays the default. Paid speech uses the owner's OpenAI API key, only for users an admin has granted.

- **Default (free):** browser `speechSynthesis` for TTS and `MediaRecorder` capture, with capability detection and a text fallback. Browser `SpeechRecognition` is optional behind a disclosure that audio may go to the browser vendor.
- **Paid STT:** OpenAI API (Whisper-family speech-to-text), Phase 3, behind `BudgetGuard`, per-user grant required, default off.
- **Paid TTS:** a separate OpenAI text-to-speech model. Whisper is speech-to-text only and cannot produce speech.
- **No automatic escalation** from a free path to a paid path, ever.
- **Local Whisper on the Pi:** deferred until benchmarked on the actual device (CPU latency and RAM unknown; do not assume).
- Recordings stay in the browser unless the user explicitly uploads; server storage needs a separate approval. Audio sent to OpenAI is a disclosed, consented transfer.
- Prices and model names are read from official pages at implementation time and are not stored in this repository's docs.
