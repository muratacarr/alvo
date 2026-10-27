"""The Pi-side deploy script: it must refuse anything that is not an approved, fresh, safe release.

Stand-ins replace `docker`, `gh` and the clock-dependent files, so every refusal and the order of
the real steps are tested without a server. The first real run on the Pi is part of the runbook.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "ops" / "deploy" / "deploy.sh"
BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(BASH is None, reason="bash not available")

COMMIT = "a" * 40
API = "sha256:" + "1" * 64
WEB = "sha256:" + "2" * 64

MANIFEST = f"""{{
  "schema": 1,
  "commit": "{COMMIT}",
  "api_digest": "{API}",
  "web_digest": "{WEB}"
}}
"""


def test_script_fails_fast_and_never_traces() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    assert "set -x" not in text
    assert "docker.sock" not in text


class Setup:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.log = tmp / "calls.log"
        self.manifest = tmp / "manifest.json"
        self.manifest.write_text(MANIFEST, encoding="utf-8")
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        for name in ("docker", "gh"):
            path = bin_dir / name
            path.write_text(
                "#!/usr/bin/env bash\n"
                f'echo "{name} $*" >> "{self.log}"\n'
                'case "$*" in *"${FAIL_ON:-@@never@@}"*) exit 1;; esac\n',
                encoding="utf-8",
            )
            path.chmod(0o755)
        self.secrets = tmp / "secrets"
        self.secrets.mkdir()
        for secret in (
            "db_password",
            "alvo_database_url",
            "alvo_session_secret",
            "alvo_google_client_secret",
            "tunnel_token",
        ):
            (self.secrets / secret).write_text("x", encoding="utf-8")
        (tmp / "compose.prod.yaml").write_text("name: alvo\n", encoding="utf-8")
        self.backup_state = tmp / "backup-state"
        self.backup_state.mkdir()
        self.mark_backup(age_seconds=60)
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "ALVO_PUBLIC_ORIGIN": "https://alvo.example.org",
            "ALVO_GOOGLE_CLIENT_ID": "1-test.apps.googleusercontent.com",
            "ALVO_COMPOSE_FILE": str(tmp / "compose.prod.yaml"),
            "ALVO_SECRETS_DIR": str(self.secrets),
            "ALVO_DEPLOY_STATE_DIR": str(tmp / "deploy-state"),
            "ALVO_BACKUP_STATE_DIR": str(self.backup_state),
            "ALVO_DOCKER_ROOT": str(tmp),
            "ALVO_MIN_FREE_GB": "0",
        }

    def mark_backup(self, age_seconds: int) -> None:
        (self.backup_state / "last-success").write_text(
            str(int(time.time()) - age_seconds), encoding="utf-8"
        )

    def run(self, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
        assert BASH is not None
        return subprocess.run(  # noqa: S603
            [BASH, str(SCRIPT), *args, str(self.manifest)],
            env={**self.env, **env},
            capture_output=True,
            text=True,
            check=False,
        )

    def calls(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []


@pytest.fixture
def setup(tmp_path: Path) -> Setup:
    return Setup(tmp_path)


@needs_bash
def test_a_good_release_runs_the_steps_in_order_and_is_recorded(setup: Setup) -> None:
    result = setup.run()
    assert result.returncode == 0, result.stderr
    steps = [call.split(" -f ")[-1].split(" ", 1)[-1] for call in setup.calls() if "docker" in call]
    joined = "\n".join(setup.calls())
    order = [
        "gh attestation verify",
        "config -q",
        "pull",
        "run --rm api alembic upgrade head",
        "up -d --wait",
    ]
    positions = [joined.index(item) for item in order]
    assert positions == sorted(positions), joined
    assert steps  # at least the docker calls were made
    assert "healthz" in joined and "health/ready" in joined
    state = Path(setup.env["ALVO_DEPLOY_STATE_DIR"])
    assert (state / "current.json").read_text(encoding="utf-8") == MANIFEST
    assert len(list((state / "history").glob("*.json"))) == 1


@needs_bash
def test_the_previous_release_is_kept_for_rollback(setup: Setup) -> None:
    assert setup.run().returncode == 0
    newer = MANIFEST.replace("a" * 40, "b" * 40).replace("1" * 64, "3" * 64)
    setup.manifest.write_text(newer, encoding="utf-8")
    assert setup.run().returncode == 0
    state = Path(setup.env["ALVO_DEPLOY_STATE_DIR"])
    assert (state / "previous.json").read_text(encoding="utf-8") == MANIFEST
    assert (state / "current.json").read_text(encoding="utf-8") == newer


@needs_bash
@pytest.mark.parametrize(
    "bad",
    [
        MANIFEST.replace(API, "sha256:short"),
        MANIFEST.replace(WEB, "latest"),
        MANIFEST.replace("a" * 40, "not-a-commit"),
        MANIFEST.replace('"schema": 1', '"schema": 2'),
        MANIFEST.replace(API, API + '", "x": "' + "sha256:" + "9" * 64),
        "",
    ],
)
def test_a_malformed_or_unlisted_manifest_is_refused_before_anything_runs(
    setup: Setup, bad: str
) -> None:
    setup.manifest.write_text(bad, encoding="utf-8")
    result = setup.run()
    assert result.returncode == 2
    assert setup.calls() == []
    assert not result.stderr.strip().endswith(" 2")  # the exit code is not part of the message


@needs_bash
def test_a_release_without_a_valid_attestation_is_refused_before_pulling(setup: Setup) -> None:
    result = setup.run(FAIL_ON="attestation verify")
    assert result.returncode != 0
    assert not any("pull" in call for call in setup.calls())


@needs_bash
def test_attestation_checks_can_only_be_skipped_on_purpose(setup: Setup) -> None:
    result = setup.run(ALVO_VERIFY_ATTESTATIONS="no")
    assert result.returncode == 0
    assert not any(call.startswith("gh ") for call in setup.calls())
    assert "NOT verified" in result.stdout + result.stderr


@needs_bash
def test_no_backup_or_a_stale_backup_stops_the_deploy(setup: Setup) -> None:
    setup.mark_backup(age_seconds=20 * 3600)
    stale = setup.run()
    assert stale.returncode != 0
    (setup.backup_state / "last-success").unlink()
    missing = setup.run()
    assert missing.returncode != 0
    assert not any("pull" in call for call in setup.calls())


@needs_bash
def test_too_little_free_disk_space_stops_the_deploy(setup: Setup) -> None:
    result = setup.run(ALVO_MIN_FREE_GB="99999999")
    assert result.returncode != 0
    assert not any("pull" in call for call in setup.calls())


@needs_bash
def test_a_missing_google_secret_or_client_id_stops_the_deploy(setup: Setup) -> None:
    (setup.secrets / "alvo_google_client_secret").unlink()
    assert setup.run().returncode != 0
    assert setup.calls() == []


@needs_bash
def test_a_missing_google_client_id_stops_the_deploy(setup: Setup) -> None:
    assert setup.run(ALVO_GOOGLE_CLIENT_ID="").returncode != 0
    assert setup.calls() == []


@needs_bash
def test_missing_secrets_stop_the_deploy(setup: Setup) -> None:
    (setup.secrets / "tunnel_token").unlink()
    result = setup.run()
    assert result.returncode != 0
    assert setup.calls() == []


@needs_bash
def test_a_failed_migration_stops_before_the_new_version_is_started(setup: Setup) -> None:
    result = setup.run(FAIL_ON="alembic")
    assert result.returncode != 0
    assert not any("up -d" in call for call in setup.calls())
    assert not (Path(setup.env["ALVO_DEPLOY_STATE_DIR"]) / "current.json").exists()


@needs_bash
def test_a_failed_health_check_is_not_recorded_as_current(setup: Setup) -> None:
    result = setup.run(FAIL_ON="health/ready")
    assert result.returncode != 0
    assert not (Path(setup.env["ALVO_DEPLOY_STATE_DIR"]) / "current.json").exists()
    assert "--rollback" in result.stdout + result.stderr


@needs_bash
def test_rollback_skips_migrations_and_the_backup_freshness_check(setup: Setup) -> None:
    (setup.backup_state / "last-success").unlink()
    result = setup.run("--rollback")
    assert result.returncode == 0, result.stderr
    assert not any("alembic" in call for call in setup.calls())
    assert any("up -d --wait" in call for call in setup.calls())


@needs_bash
def test_the_checked_out_stack_definition_must_match_the_release_commit(setup: Setup) -> None:
    git = shutil.which("git")
    assert git is not None
    repo = setup.tmp
    subprocess.run([git, "init", "-q", str(repo)], check=True)  # noqa: S603
    subprocess.run(  # noqa: S603
        [
            git,
            "-C",
            str(repo),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.org",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "x",
        ],
        check=True,
    )
    result = setup.run()
    assert result.returncode != 0
    assert "checked-out" in result.stdout + result.stderr
    assert setup.calls() == []


@needs_bash
def test_the_very_first_deploy_may_skip_the_backup_check_only_when_nothing_was_deployed(
    setup: Setup,
) -> None:
    (setup.backup_state / "last-success").unlink()
    first = setup.run("--first")
    assert first.returncode == 0, first.stderr
    assert any("alembic upgrade head" in call for call in setup.calls())
    # A second "first" deploy is refused: from now on a fresh backup is required.
    again = setup.run("--first")
    assert again.returncode == 2
    assert "already" in again.stdout + again.stderr


@needs_bash
def test_first_and_rollback_cannot_be_combined(setup: Setup) -> None:
    result = setup.run("--first", "--rollback")
    assert result.returncode == 2
    assert setup.calls() == []
