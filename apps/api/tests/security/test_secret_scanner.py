"""The secret scanner must flag realistic credentials and pass clean files."""

import os
import shutil
import subprocess  # noqa: S404
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG = REPO_ROOT / ".gitleaks.toml"

# Locally the tests skip without gitleaks; in CI a missing scanner must fail, not skip.
pytestmark = pytest.mark.skipif(
    shutil.which("gitleaks") is None and not os.environ.get("CI"),
    reason="gitleaks not installed",
)


def scan(directory: Path) -> int:
    executable = shutil.which("gitleaks")
    assert executable is not None
    result = subprocess.run(  # noqa: S603
        [
            executable,
            "dir",
            str(directory),
            "--config",
            str(CONFIG),
            "--no-banner",
            "--redact",
        ],
        capture_output=True,
        check=False,
    )
    return result.returncode


def test_flags_realistic_embedded_credential(tmp_path: Path) -> None:
    # Assembled at runtime so this source file never contains a scannable secret.
    fake_key = "AKIA" + "IOSFODNN7" + "REALKEY"
    (tmp_path / "seed.py").write_text(f'aws_access_key_id = "{fake_key}"\n', encoding="utf-8")
    assert scan(tmp_path) == 1


def test_flags_private_key_block(tmp_path: Path) -> None:
    header = "-----BEGIN " + "RSA PRIVATE KEY-----"
    footer = "-----END " + "RSA PRIVATE KEY-----"
    body = "MIIEowIBAAKCAQEA" + "x7Qk9vL2mN4pR8sT1uW3yZ5bC6dE7fG8hJ9kL0mN1oP2qR3sT4uV5wX6yZ7aB8c"
    (tmp_path / "key.txt").write_text(f"{header}\n{body}\n{footer}\n", encoding="utf-8")
    assert scan(tmp_path) == 1


def test_passes_clean_file(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text("VALUE = 'nothing secret here'\n", encoding="utf-8")
    assert scan(tmp_path) == 0
