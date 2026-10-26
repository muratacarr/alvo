from alvo.content.domain import ItemType, item_fingerprint, loose_key, title_key


def fp(prompt: str, item_type: ItemType = ItemType.QUESTION) -> str:
    return item_fingerprint(item_type, prompt)


def test_fingerprint_is_a_stable_sha256_hex_digest() -> None:
    value = fp("What is dependency injection?")
    assert len(value) == 64
    assert value == fp("What is dependency injection?")
    assert int(value, 16) >= 0


def test_fingerprint_ignores_case_whitespace_and_unicode_compatibility_forms() -> None:
    assert fp("Tell me  about\tYOURSELF.") == fp("tell me about yourself.")
    assert fp("ｆｕｌｌｗｉｄｔｈ text") == fp("fullwidth text")  # NFKC


def test_fingerprint_distinguishes_punctuation_and_item_type() -> None:
    assert fp("Tell me about yourself?") != fp("Tell me about yourself.")
    assert fp("break the ice") != fp("break the ice", ItemType.PHRASE)


def test_loose_key_ignores_punctuation_accents_and_case() -> None:
    assert loose_key("What's your name?") == loose_key("whats your NAME")
    assert loose_key("Café au lait") == loose_key("cafe au lait")


def test_loose_key_still_separates_different_sentences() -> None:
    assert loose_key("What is your name?") != loose_key("What is your age?")


def test_near_duplicates_have_different_strict_but_equal_loose_identity() -> None:
    a, b = "What's your name?", "Whats your name"
    assert fp(a) != fp(b)
    assert loose_key(a) == loose_key(b)


def test_title_key_matches_titles_that_differ_only_in_case_and_spacing() -> None:
    assert title_key("  Technical   Interview ") == title_key("technical interview")
    assert title_key("Basics") != title_key("Advanced")
