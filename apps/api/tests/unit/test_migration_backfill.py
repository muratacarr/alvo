"""Migration 0005 back-fills fingerprints with a frozen copy of the rules. They must agree."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from alvo.content.domain import ItemType, item_fingerprint, loose_key

MIGRATION = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0005_import_support.py"

SAMPLES = [
    "What is dependency injection?",
    "  Tell me   about\tYOURSELF.  ",
    "What's your name?",
    "Café au lait",
    "ｆｕｌｌｗｉｄｔｈ text",
    "Straße and STRASSE",
    "Türkçe karakterler: ığüşöç İĞÜŞÖÇ",
    "emoji 😀 and punctuation !?.,;:",
]


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migration_0005", MIGRATION)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("prompt", SAMPLES)
@pytest.mark.parametrize("item_type", list(ItemType))
def test_backfilled_fingerprints_match_the_domain_rules(prompt: str, item_type: ItemType) -> None:
    migration = load_migration()
    assert migration._fingerprint(item_type.value, prompt) == item_fingerprint(item_type, prompt)


@pytest.mark.parametrize("prompt", SAMPLES)
def test_backfilled_loose_keys_match_the_domain_rules(prompt: str) -> None:
    assert load_migration()._loose_key(prompt) == loose_key(prompt)
