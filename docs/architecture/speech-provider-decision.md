# Speech Provider Decision

Decision: MVP uses browser `speechSynthesis` (TTS) and `MediaRecorder` capture only, with capability detection and text fallback. Browser `SpeechRecognition` is optional, behind a disclosure that audio may go to the browser vendor.

- Local Whisper on the Pi: deferred until benchmarked on the actual device (CPU-only inference latency and RAM unknown; do not assume).
- Paid OpenAI STT/TTS: Phase 3, behind BudgetGuard, default off. Whisper is STT only; TTS is a separate model.
- No automatic escalation from a free path to a paid path.
- Recordings stay in the browser unless the user explicitly uploads; server storage needs a separate approval.
