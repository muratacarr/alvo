"""Entitlement rules: who may use which paid AI feature. Pure logic, no I/O.

Default deny: absence of an entitlement means no access. `exempt` only removes the
per-user quotas; global budget, concurrency and kill-switch checks still apply to
everyone and are enforced by the budget gateway in a later phase.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, TypeGuard

Mode = Literal["limited", "exempt"]
_MODES = {"limited", "exempt"}


class Feature(StrEnum):
    LLM = "llm"
    STT = "stt"
    TTS = "tts"


@dataclass(frozen=True)
class Entitlement:
    feature: Feature
    mode: Mode
    requests_per_day: int | None
    monthly_units: int | None


@dataclass(frozen=True)
class Access:
    allowed: bool
    exempt: bool


@dataclass(frozen=True)
class GrantCaps:
    """Global ceilings for per-user limits an admin may grant (0 = grant nothing)."""

    requests_per_day: int
    monthly_units: int


class GrantError(ValueError):
    pass


def evaluate(entitlement: Entitlement | None) -> Access:
    if entitlement is None:
        return Access(allowed=False, exempt=False)
    return Access(allowed=True, exempt=entitlement.mode == "exempt")


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_grant(
    mode: str, *, requests_per_day: int | None, monthly_units: int | None, caps: GrantCaps
) -> None:
    if mode not in _MODES:
        raise GrantError("unknown mode")
    if mode == "exempt":
        if requests_per_day is not None or monthly_units is not None:
            raise GrantError("exempt grants carry no per-user limits")
        return
    if not _is_int(requests_per_day) or not _is_int(monthly_units):
        raise GrantError("limited grants need both limits")
    if not 0 < requests_per_day <= caps.requests_per_day:
        raise GrantError("requests_per_day outside the allowed range")
    if not 0 < monthly_units <= caps.monthly_units:
        raise GrantError("monthly_units outside the allowed range")
