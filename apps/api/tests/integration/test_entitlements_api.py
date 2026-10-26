"""Roles and default-deny AI entitlements, against a real PostgreSQL."""

from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from alvo.main import create_app
from tests.conftest import SettingsFactory
from tests.integration.conftest import FakeClock
from tests.integration.test_auth_api import (
    LOGIN,
    LOGOUT,
    ORIGIN,
    login,
)

ME_ENTITLEMENTS = "/api/v1/entitlements/me"
CAPS = {"ai_max_requests_per_day": "100", "ai_max_monthly_units": "10000"}


@pytest.fixture
def make_client(
    migrated_database_url: str, settings_factory: SettingsFactory, clock: FakeClock
) -> Callable[..., TestClient]:
    def build(**overrides: str) -> TestClient:
        settings = settings_factory(database_url=migrated_database_url, **{**CAPS, **overrides})
        app = create_app(settings, readiness_probe=lambda: True, clock=clock)
        return TestClient(app, base_url="https://testserver")

    return build


@pytest.fixture
def db(migrated_database_url: str) -> Any:
    engine = create_engine(migrated_database_url)
    yield engine
    engine.dispose()


def set_role(db: Any, user_id: str, role: str) -> None:
    with db.begin() as connection:
        connection.execute(
            text("UPDATE users SET role = :r WHERE id = :u"), {"r": role, "u": user_id}
        )


def admin_client(
    make_client: Callable[..., TestClient], db: Any
) -> tuple[TestClient, dict[str, Any]]:
    client = make_client()
    body = login(client)
    set_role(db, body["user_id"], "admin")
    return client, body


def grant_url(user_id: str, feature: str) -> str:
    return f"/api/v1/admin/users/{user_id}/entitlements/{feature}"


def headers(body: dict[str, Any]) -> dict[str, str]:
    return {**ORIGIN, "X-CSRF-Token": body["csrf_token"]}


LIMITED = {"mode": "limited", "requests_per_day": 50, "monthly_units": 5000}


def test_a_new_user_has_no_access_to_any_feature(make_client: Callable[..., TestClient]) -> None:
    client = make_client()
    login(client)
    response = client.get(ME_ENTITLEMENTS)
    assert response.status_code == 200
    assert response.json() == {
        "features": [
            {"feature": "llm", "allowed": False},
            {"feature": "stt", "allowed": False},
            {"feature": "tts", "allowed": False},
        ]
    }


def test_entitlements_require_a_session(make_client: Callable[..., TestClient]) -> None:
    assert make_client().get(ME_ENTITLEMENTS).status_code == 401


def test_a_normal_user_cannot_grant_anything(make_client: Callable[..., TestClient]) -> None:
    client = make_client()
    body = login(client)
    response = client.put(grant_url(body["user_id"], "llm"), json=LIMITED, headers=headers(body))
    assert response.status_code == 403
    assert client.get(ME_ENTITLEMENTS).json()["features"][0]["allowed"] is False


def test_an_admin_can_grant_a_limited_entitlement(
    make_client: Callable[..., TestClient], db: Any
) -> None:
    admin, admin_body = admin_client(make_client, db)
    learner = make_client()
    learner_body = login(learner)

    response = admin.put(
        grant_url(learner_body["user_id"], "llm"), json=LIMITED, headers=headers(admin_body)
    )
    assert response.status_code == 204
    features = {f["feature"]: f["allowed"] for f in learner.get(ME_ENTITLEMENTS).json()["features"]}
    assert features == {"llm": True, "stt": False, "tts": False}


def test_limited_grants_above_the_global_caps_are_rejected(
    make_client: Callable[..., TestClient], db: Any
) -> None:
    admin, admin_body = admin_client(make_client, db)
    learner_id = login(make_client())["user_id"]
    too_big = {"mode": "limited", "requests_per_day": 101, "monthly_units": 5000}
    response = admin.put(grant_url(learner_id, "llm"), json=too_big, headers=headers(admin_body))
    assert response.status_code == 422
    assert response.json() == {"error": "invalid_grant"}


def test_with_default_zero_caps_no_limited_grant_is_possible(
    make_client: Callable[..., TestClient], db: Any
) -> None:
    admin = make_client(ai_max_requests_per_day="0", ai_max_monthly_units="0")
    body = login(admin)
    set_role(db, body["user_id"], "admin")
    learner_id = login(make_client())["user_id"]
    response = admin.put(grant_url(learner_id, "llm"), json=LIMITED, headers=headers(body))
    assert response.status_code == 422


def test_an_exempt_grant_is_possible_and_marks_the_user_allowed(
    make_client: Callable[..., TestClient], db: Any
) -> None:
    admin, admin_body = admin_client(make_client, db)
    learner = make_client()
    learner_body = login(learner)
    response = admin.put(
        grant_url(learner_body["user_id"], "stt"),
        json={"mode": "exempt"},
        headers=headers(admin_body),
    )
    assert response.status_code == 204
    features = {f["feature"]: f["allowed"] for f in learner.get(ME_ENTITLEMENTS).json()["features"]}
    assert features["stt"] is True


def test_revoking_removes_access_and_is_idempotent(
    make_client: Callable[..., TestClient], db: Any
) -> None:
    admin, admin_body = admin_client(make_client, db)
    learner = make_client()
    learner_body = login(learner)
    url = grant_url(learner_body["user_id"], "tts")
    admin.put(url, json=LIMITED, headers=headers(admin_body))
    assert admin.delete(url, headers=headers(admin_body)).status_code == 204
    assert admin.delete(url, headers=headers(admin_body)).status_code == 204
    assert learner.get(ME_ENTITLEMENTS).json()["features"][2] == {
        "feature": "tts",
        "allowed": False,
    }


def test_grants_need_csrf_and_a_matching_origin(
    make_client: Callable[..., TestClient], db: Any
) -> None:
    admin, admin_body = admin_client(make_client, db)
    learner_id = login(make_client())["user_id"]
    url = grant_url(learner_id, "llm")
    assert admin.put(url, json=LIMITED, headers=ORIGIN).status_code == 403
    no_origin = {"X-CSRF-Token": admin_body["csrf_token"]}
    assert admin.put(url, json=LIMITED, headers=no_origin).status_code == 403


def test_a_stale_admin_session_must_sign_in_again(
    make_client: Callable[..., TestClient], db: Any, clock: FakeClock
) -> None:
    admin, admin_body = admin_client(make_client, db)
    learner_id = login(make_client())["user_id"]
    for _ in range(4):  # stay active for 20 minutes
        clock.advance(minutes=5)
        assert admin.get("/api/v1/auth/me").status_code == 200
    stale = admin.put(grant_url(learner_id, "llm"), json=LIMITED, headers=headers(admin_body))
    assert stale.status_code == 403
    assert stale.json() == {"error": "reauthentication_required"}
    fresh = login(admin, "re-login-" + uuid4().hex)  # a new sign-in is a fresh session
    set_role(db, fresh["user_id"], "admin")
    again = admin.put(grant_url(learner_id, "llm"), json=LIMITED, headers=headers(fresh))
    assert again.status_code == 204


def test_the_request_body_cannot_smuggle_extra_fields(
    make_client: Callable[..., TestClient], db: Any
) -> None:
    admin, admin_body = admin_client(make_client, db)
    learner_id = login(make_client())["user_id"]
    for extra in ({"role": "admin"}, {"user_id": str(uuid4())}, {"granted_by": "x"}):
        response = admin.put(
            grant_url(learner_id, "llm"), json={**LIMITED, **extra}, headers=headers(admin_body)
        )
        assert response.status_code == 422


def test_unknown_users_and_features_get_generic_errors(
    make_client: Callable[..., TestClient], db: Any
) -> None:
    admin, admin_body = admin_client(make_client, db)
    missing = admin.put(grant_url(str(uuid4()), "llm"), json=LIMITED, headers=headers(admin_body))
    assert missing.status_code == 404
    assert missing.json() == {"error": "not_found"}
    learner_id = login(make_client())["user_id"]
    bad_feature = admin.put(grant_url(learner_id, "gpu"), json=LIMITED, headers=headers(admin_body))
    assert bad_feature.status_code == 404


def test_login_cannot_assign_a_role(make_client: Callable[..., TestClient]) -> None:
    client = make_client()
    response = client.post(LOGIN, json={"subject": uuid4().hex, "role": "admin"}, headers=ORIGIN)
    assert response.status_code == 422


def test_demotion_takes_effect_on_the_next_request(
    make_client: Callable[..., TestClient], db: Any
) -> None:
    admin, admin_body = admin_client(make_client, db)
    learner_id = login(make_client())["user_id"]
    url = grant_url(learner_id, "llm")
    assert admin.put(url, json=LIMITED, headers=headers(admin_body)).status_code == 204
    set_role(db, admin_body["user_id"], "user")
    assert admin.put(url, json=LIMITED, headers=headers(admin_body)).status_code == 403


def test_users_only_see_their_own_entitlements(
    make_client: Callable[..., TestClient], db: Any
) -> None:
    admin, admin_body = admin_client(make_client, db)
    alice, bob = make_client(), make_client()
    alice_id = login(alice)["user_id"]
    login(bob)
    admin.put(grant_url(alice_id, "llm"), json=LIMITED, headers=headers(admin_body))
    assert alice.get(ME_ENTITLEMENTS).json()["features"][0]["allowed"] is True
    assert bob.get(ME_ENTITLEMENTS).json()["features"][0]["allowed"] is False


def test_grants_and_revocations_are_audited(
    make_client: Callable[..., TestClient], db: Any
) -> None:
    admin, admin_body = admin_client(make_client, db)
    learner_id = login(make_client())["user_id"]
    url = grant_url(learner_id, "llm")
    admin.put(url, json=LIMITED, headers=headers(admin_body))
    admin.delete(url, headers=headers(admin_body))
    with db.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT action, feature, mode, actor_id, requests_per_day FROM entitlement_events "
                "WHERE target_user_id = :t ORDER BY occurred_at, action"
            ),
            {"t": UUID(learner_id)},
        ).all()
    assert [(r.action, r.feature) for r in rows] == [("grant", "llm"), ("revoke", "llm")]
    assert str(rows[0].actor_id) == admin_body["user_id"]
    assert rows[0].mode == "limited"
    assert rows[0].requests_per_day == 50


def test_logout_still_works_for_admins(make_client: Callable[..., TestClient], db: Any) -> None:
    admin, admin_body = admin_client(make_client, db)
    assert admin.post(LOGOUT, headers=headers(admin_body)).status_code == 204
