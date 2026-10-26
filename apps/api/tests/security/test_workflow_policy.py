"""Static policy checks for GitHub Actions workflows (supply-chain and secret hygiene)."""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[4] / ".github" / "workflows"
FULL_SHA = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def load(name: str) -> dict[Any, Any]:
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def workflow_files() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.yml")) if WORKFLOWS.is_dir() else []


def test_ci_workflow_exists() -> None:
    assert (WORKFLOWS / "ci.yml").is_file()


def test_ci_runs_on_pull_requests_and_main() -> None:
    triggers = load("ci.yml")[True]  # YAML 1.1 parses the key `on` as True
    assert "pull_request" in triggers
    assert triggers["push"]["branches"] == ["main"]


def test_ci_default_permissions_are_read_only() -> None:
    assert load("ci.yml")["permissions"] == {"contents": "read"}


def test_ci_cancels_superseded_runs() -> None:
    assert "concurrency" in load("ci.yml")


@pytest.mark.parametrize("path", workflow_files(), ids=lambda p: p.name)
def test_every_external_action_is_pinned_to_a_full_sha(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*-?\s*uses:\s*(\S+)", line)
        if match and not match.group(1).startswith("./"):
            assert FULL_SHA.match(match.group(1)), f"{path.name}: unpinned action {match.group(1)}"


@pytest.mark.parametrize("path", workflow_files(), ids=lambda p: p.name)
def test_no_pull_request_target(path: Path) -> None:
    assert "pull_request_target" not in path.read_text(encoding="utf-8")


def test_ci_references_no_repository_secrets() -> None:
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert not re.search(r"\$\{\{\s*secrets\.", text)


def test_checkout_never_persists_credentials() -> None:
    for job in load("ci.yml")["jobs"].values():
        for step in job["steps"]:
            if str(step.get("uses", "")).startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] is False


def test_every_job_has_a_timeout() -> None:
    for name, job in load("ci.yml")["jobs"].items():
        assert "timeout-minutes" in job, name
