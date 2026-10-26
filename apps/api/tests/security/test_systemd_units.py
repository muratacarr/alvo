"""The backup runs by itself every six hours: check the systemd units that schedule it."""

import re
from pathlib import Path

OPS = Path(__file__).resolve().parents[4] / "ops"
SERVICE = OPS / "systemd" / "alvo-backup.service"
TIMER = OPS / "systemd" / "alvo-backup.timer"
BACKUP = OPS / "backup" / "backup.sh"


def test_the_timer_runs_every_six_hours_and_catches_up_after_downtime() -> None:
    text = TIMER.read_text(encoding="utf-8")
    match = re.search(r"^OnCalendar=\*-\*-\* ([0-9,]+):00:00$", text, re.MULTILINE)
    assert match is not None
    hours = [int(hour) for hour in match.group(1).split(",")]
    assert hours == [2, 8, 14, 20]  # RPO of six hours
    assert "Persistent=true" in text
    assert "WantedBy=timers.target" in text
    assert "RandomizedDelaySec=" in text


def test_the_service_runs_the_backup_script_once_with_limited_privileges() -> None:
    text = SERVICE.read_text(encoding="utf-8")
    assert "Type=oneshot" in text
    assert "ExecStart=/opt/alvo/ops/backup/backup.sh" in text
    assert "EnvironmentFile=/etc/alvo/backup.env" in text
    for setting in ("NoNewPrivileges=yes", "PrivateTmp=yes", "ProtectHome=yes"):
        assert setting in text
    assert "TimeoutStartSec=" in text


def test_the_units_contain_no_keys_or_secrets() -> None:
    for unit in (SERVICE, TIMER):
        text = unit.read_text(encoding="utf-8")
        assert "age1" not in text
        assert "AGE-SECRET-KEY" not in text


def test_the_backup_reaches_the_stack_by_project_name_not_by_compose_file() -> None:
    # The production Compose file refuses to load without release variables; a running
    # stack is addressed by its project name instead.
    text = BACKUP.read_text(encoding="utf-8")
    assert "docker compose -p alvo" in text
    assert "compose.prod.yaml" not in text.split("set -euo pipefail")[1]
