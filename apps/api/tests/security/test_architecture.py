"""Module boundaries of the modular monolith are enforced by import-linter contracts."""

import subprocess  # noqa: S404
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[2]


def test_import_contracts_hold() -> None:
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-c",
            "import sys; from importlinter.cli import lint_imports_command; "
            "sys.argv = ['lint-imports']; lint_imports_command()",
        ],
        cwd=API_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
