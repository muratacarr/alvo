"""The published schema and sample must match what the code ships and enforces."""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from alvo.imports.parsing import load_sample_document, load_schema, parse_document

DOCS_API = Path(__file__).resolve().parents[4] / "docs" / "api"
PACKAGE_TEMPLATES = Path(__file__).resolve().parents[2] / "src" / "alvo" / "imports" / "templates"


def test_docs_copies_are_byte_identical_to_the_shipped_templates() -> None:
    for name in ("import-schema-v1.json", "import-sample-v1.json"):
        assert (DOCS_API / name).read_bytes() == (PACKAGE_TEMPLATES / name).read_bytes(), name


def test_the_schema_is_itself_a_valid_json_schema() -> None:
    Draft202012Validator.check_schema(load_schema())


def test_the_sample_validates_against_the_schema() -> None:
    Draft202012Validator(load_schema()).validate(load_sample_document())


def invalid_documents() -> list[dict[str, Any]]:
    sample = load_sample_document()

    def mutated(fn: Any) -> dict[str, Any]:
        copy: dict[str, Any] = json.loads(json.dumps(sample))
        fn(copy)
        return copy

    return [
        mutated(lambda d: d.pop("schemaVersion")),
        mutated(lambda d: d.__setitem__("extra", 1)),
        mutated(lambda d: d["program"].pop("modules")),
        mutated(
            lambda d: d["program"]["modules"][0]["topics"][0]["items"][0].__setitem__("id", "1")
        ),
        mutated(
            lambda d: d["program"]["modules"][0]["topics"][0]["items"][0].__setitem__(
                "type", "essay"
            )
        ),
        mutated(
            lambda d: d["program"]["modules"][0]["topics"][0]["items"][0].__setitem__(
                "difficulty", 9
            )
        ),
    ]


def test_schema_and_parser_agree_on_hostile_documents() -> None:
    validator = Draft202012Validator(load_schema())
    for document in invalid_documents():
        assert not validator.is_valid(document)
        parsed_ok_and_clean = False
        try:
            parsed = parse_document(json.dumps(document).encode())
            parsed_ok_and_clean = not parsed.invalid
        except Exception:
            parsed_ok_and_clean = False
        assert not parsed_ok_and_clean
