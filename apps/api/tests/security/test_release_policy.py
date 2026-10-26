"""Static policy checks for the release workflow (publishes images that run in production)."""

import re
from pathlib import Path
from typing import Any

import yaml

WORKFLOW = Path(__file__).resolve().parents[4] / ".github" / "workflows" / "release.yml"


def text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def load() -> dict[Any, Any]:
    data = yaml.safe_load(text())
    assert isinstance(data, dict)
    return data


def triggers() -> Any:
    # YAML 1.1 reads the key `on` as the boolean True.
    data = load()
    return data.get("on", data.get(True))


def job() -> dict[str, Any]:
    jobs = load()["jobs"]
    assert list(jobs) == ["release"]
    result: dict[str, Any] = jobs["release"]
    return result


def steps() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = job()["steps"]
    return result


def test_a_release_is_only_ever_started_by_hand() -> None:
    assert list(triggers()) == ["workflow_dispatch"]


def test_it_can_only_run_from_main() -> None:
    assert "github.ref == 'refs/heads/main'" in str(job()["if"])


def test_publishing_waits_for_the_protected_production_environment() -> None:
    # The environment carries the required reviewer configured in the repository settings.
    assert job()["environment"] == "production"


def test_default_permissions_are_read_only_and_the_job_gets_only_what_it_needs() -> None:
    assert load()["permissions"] == {"contents": "read"}
    assert job()["permissions"] == {
        "contents": "read",
        "packages": "write",
        "id-token": "write",
        "attestations": "write",
    }


def test_releases_never_overlap_and_have_a_timeout() -> None:
    assert load()["concurrency"]["cancel-in-progress"] is False
    assert "timeout-minutes" in job()


def test_images_are_built_natively_for_arm64() -> None:
    assert "arm" in job()["runs-on"]
    builds = [s for s in steps() if str(s.get("uses", "")).startswith("docker/build-push-action@")]
    assert len(builds) == 2
    for build in builds:
        assert build["with"]["platforms"] == "linux/arm64"
        assert build["with"]["push"] is True
        assert build["with"]["sbom"] is True
        assert "mode=max" in str(build["with"]["provenance"])


def test_images_are_tagged_with_the_commit_only_never_latest() -> None:
    assert "latest" not in text().lower().replace("github.sha", "")
    for step in steps():
        tags = str(step.get("with", {}).get("tags", ""))
        if tags:
            assert re.fullmatch(
                r"ghcr\.io/muratacarr/alvo-(api|web):sha-\$\{\{ github\.sha \}\}", tags
            )


def test_both_images_get_signed_provenance_attestations() -> None:
    attests = [s for s in steps() if str(s.get("uses", "")).startswith("actions/attest@")]
    assert len(attests) == 2
    for attest in attests:
        assert attest["with"]["push-to-registry"] is True
        assert "digest" in attest["with"]["subject-digest"]


def test_the_web_image_is_never_built_with_the_development_login() -> None:
    assert "VITE_DEV_LOGIN" not in text()


def test_the_only_secret_used_is_the_built_in_token() -> None:
    assert set(re.findall(r"secrets\.([A-Za-z0-9_]+)", text())) == {"GITHUB_TOKEN"}


def test_checkout_never_persists_credentials() -> None:
    checkouts = [s for s in steps() if str(s.get("uses", "")).startswith("actions/checkout@")]
    assert checkouts
    for checkout in checkouts:
        assert checkout["with"]["persist-credentials"] is False


def test_a_release_manifest_with_the_commit_and_both_digests_is_published() -> None:
    body = text()
    assert "release-manifest.json" in body
    assert any(str(s.get("uses", "")).startswith("actions/upload-artifact@") for s in steps())
    for field in ("commit", "api_digest", "web_digest"):
        assert field in body


def test_no_user_controlled_text_is_interpolated_into_shell_commands() -> None:
    dangerous = ("github.event.", "github.head_ref", "github.event_name == 'x'")
    for step in steps():
        run = str(step.get("run", ""))
        assert "${{" not in run, step.get("name")
        for word in dangerous:
            assert word not in run
