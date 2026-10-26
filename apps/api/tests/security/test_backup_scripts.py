"""Backup and restore-drill scripts: policy checks plus behaviour with stand-in commands.

The stand-ins replace `docker`, `age` and `rclone`, so the logic (naming, size guard, upload,
marker, failure handling) is tested without a database or a cloud account. The real tools were
exercised end to end once by hand (see docs/ops/production-runbook.md).
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

OPS = Path(__file__).resolve().parents[4] / "ops" / "backup"
BACKUP = OPS / "backup.sh"
DRILL = OPS / "restore-drill.sh"
BASH = shutil.which("bash")

needs_bash = pytest.mark.skipif(BASH is None, reason="bash not available")


def test_scripts_fail_fast_and_keep_files_private() -> None:
    for script in (BACKUP, DRILL):
        text = script.read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env bash")
        assert "set -euo pipefail" in text
        assert "umask 077" in text
        assert "set -x" not in text  # would print secrets


def test_the_backup_uses_only_the_public_key_and_never_prints_it() -> None:
    text = BACKUP.read_text(encoding="utf-8")
    assert "age -r" in text
    assert "-i " not in text.replace("-i)", "")  # no private identity on the server
    for line in text.splitlines():
        if line.lstrip().startswith("echo"):
            assert "RECIPIENT" not in line


def test_the_drill_never_touches_the_live_database() -> None:
    text = DRILL.read_text(encoding="utf-8")
    assert "alvo_restore_drill" in text
    assert "DROP DATABASE alvo\n" not in text
    assert "-d alvo " not in text and '-d alvo"' not in text


def _stub(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(0o755)


def _env(tmp_path: Path, dump_bytes: int, **extra: str) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "rclone.log"
    _stub(bin_dir / "docker", f"head -c {dump_bytes} /dev/zero\n")
    _stub(bin_dir / "age", 'while [ "$1" != "-o" ]; do shift; done\ncat > "$2"\n')
    _stub(bin_dir / "rclone", f'echo "$@" >> "{log}"\n')
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "ALVO_COMPOSE": "docker compose",
        "ALVO_BACKUP_AGE_RECIPIENT": "age1testtesttesttesttesttesttesttesttesttesttesttesttesttest",
        "ALVO_BACKUP_REMOTE": "remote:bucket/db",
        "ALVO_BACKUP_STATE_DIR": str(tmp_path / "state"),
        **extra,
    }
    return env


def _run(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    return subprocess.run(  # noqa: S603
        [BASH, str(BACKUP)], env=env, capture_output=True, text=True, check=False
    )


@needs_bash
def test_a_good_backup_is_uploaded_once_with_a_timestamped_name(tmp_path: Path) -> None:
    result = _run(_env(tmp_path, 5000))
    assert result.returncode == 0, result.stderr
    uploads = (tmp_path / "rclone.log").read_text(encoding="utf-8").splitlines()
    assert len(uploads) == 1
    assert uploads[0].startswith("copyto ")
    assert "remote:bucket/db/alvo-" in uploads[0]
    assert uploads[0].endswith(".dump.age")
    assert (tmp_path / "state" / "last-success").read_text(encoding="utf-8").strip().isdigit()
    assert "age1" not in result.stdout + result.stderr


@needs_bash
def test_a_tiny_dump_is_not_uploaded_and_no_success_is_recorded(tmp_path: Path) -> None:
    result = _run(_env(tmp_path, 10))
    assert result.returncode != 0
    assert not (tmp_path / "rclone.log").exists()
    assert not (tmp_path / "state" / "last-success").exists()


@needs_bash
def test_missing_or_wrong_settings_stop_the_backup(tmp_path: Path) -> None:
    env = _env(tmp_path, 5000)
    del env["ALVO_BACKUP_REMOTE"]
    assert _run(env).returncode != 0
    second = tmp_path / "second"
    second.mkdir()
    env = _env(second, 5000)
    env["ALVO_BACKUP_AGE_RECIPIENT"] = "AGE-SECRET-KEY-not-a-public-key"
    result = _run(env)
    assert result.returncode == 2
    assert "AGE-SECRET-KEY" not in result.stdout + result.stderr
