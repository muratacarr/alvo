import pytest

from alvo.entitlements.domain import (
    Access,
    Entitlement,
    Feature,
    GrantCaps,
    GrantError,
    evaluate,
    validate_grant,
)

CAPS = GrantCaps(requests_per_day=100, monthly_units=10_000)
NO_CAPS = GrantCaps(requests_per_day=0, monthly_units=0)


def test_no_entitlement_is_denied() -> None:
    assert evaluate(None) == Access(allowed=False, exempt=False)


def test_limited_entitlement_is_allowed_and_not_exempt() -> None:
    entitlement = Entitlement(Feature.LLM, "limited", requests_per_day=10, monthly_units=500)
    assert evaluate(entitlement) == Access(allowed=True, exempt=False)


def test_exempt_entitlement_is_allowed_and_marked_exempt() -> None:
    assert evaluate(Entitlement(Feature.STT, "exempt", None, None)) == Access(True, True)


def test_valid_limited_grant_passes() -> None:
    validate_grant("limited", requests_per_day=100, monthly_units=10_000, caps=CAPS)


@pytest.mark.parametrize(
    ("requests", "units"),
    [(0, 10), (10, 0), (-1, 10), (10, -5), (101, 10), (10, 10_001), (None, 10), (10, None)],
)
def test_limited_grant_rejects_missing_nonpositive_or_above_cap_limits(
    requests: int | None, units: int | None
) -> None:
    with pytest.raises(GrantError):
        validate_grant("limited", requests_per_day=requests, monthly_units=units, caps=CAPS)


def test_with_zero_caps_no_limited_grant_is_possible() -> None:
    with pytest.raises(GrantError):
        validate_grant("limited", requests_per_day=1, monthly_units=1, caps=NO_CAPS)


def test_exempt_grant_carries_no_per_user_limits() -> None:
    validate_grant("exempt", requests_per_day=None, monthly_units=None, caps=NO_CAPS)
    with pytest.raises(GrantError):
        validate_grant("exempt", requests_per_day=5, monthly_units=None, caps=CAPS)


def test_unknown_mode_is_rejected() -> None:
    with pytest.raises(GrantError):
        validate_grant("unlimited", requests_per_day=None, monthly_units=None, caps=CAPS)


def test_features_are_a_closed_set() -> None:
    assert {f.value for f in Feature} == {"llm", "stt", "tts"}
