"""User-supplied text rules shared by every module.

Content is stored as plain text exactly as entered (no HTML sanitising); clients must
render it as text, never as markup. We only normalise and reject characters that are
invisible or can disguise text.
"""

import unicodedata
from typing import Any

from pydantic import BeforeValidator

_ALLOWED_CONTROLS = {"\n", "\t"}
# Bidirectional override/isolate characters can make text display differently from its bytes.
_BIDI_OVERRIDES = {*map(chr, range(0x202A, 0x202F)), *map(chr, range(0x2066, 0x206A))}


def clean_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).strip()
    for char in normalized:
        if char in _BIDI_OVERRIDES or (
            unicodedata.category(char) == "Cc" and char not in _ALLOWED_CONTROLS
        ):
            raise ValueError("contains control characters")
    return normalized


def _clean_if_text(value: Any) -> Any:
    # Non-strings are passed through so strict type validation reports them.
    return clean_text(value) if isinstance(value, str) else value


# Use as `Annotated[str, CLEAN, StringConstraints(min_length=1, max_length=200)]`:
# the text is cleaned first, then length-checked.
CLEAN = BeforeValidator(_clean_if_text)
