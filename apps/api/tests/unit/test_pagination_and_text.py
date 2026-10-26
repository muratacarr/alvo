from datetime import UTC, datetime
from uuid import uuid4

import pytest

from alvo.shared.errors import ApiError
from alvo.shared.pagination import decode_cursor, encode_cursor
from alvo.shared.text import clean_text

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_cursor_round_trips() -> None:
    row_id = uuid4()
    assert decode_cursor(encode_cursor(NOW, row_id)) == (NOW, row_id)


@pytest.mark.parametrize("bad", ["", "not-base64!!", "e30", "bm9wZQ", "a" * 500])
def test_malformed_cursors_are_rejected_with_a_generic_error(bad: str) -> None:
    with pytest.raises(ApiError) as excinfo:
        decode_cursor(bad)
    assert excinfo.value.status_code == 422
    assert excinfo.value.code == "invalid_cursor"


def test_clean_text_keeps_newlines_and_tabs_and_normalizes_unicode() -> None:
    assert clean_text("a\nb\tc") == "a\nb\tc"
    assert clean_text("é") == "é"  # NFC


@pytest.mark.parametrize("bad", ["a\x00b", "a\x1bb", "a\x7fb", "a‮b"])
def test_clean_text_rejects_control_and_bidi_override_characters(bad: str) -> None:
    with pytest.raises(ValueError, match="control"):
        clean_text(bad)


def test_clean_text_strips_surrounding_whitespace() -> None:
    assert clean_text("  hello  ") == "hello"
