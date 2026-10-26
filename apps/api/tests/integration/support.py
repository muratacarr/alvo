"""Helpers for API tests: an authenticated actor wrapping a TestClient."""

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx2 as httpx
from fastapi.testclient import TestClient

ORIGIN = {"Origin": "https://testserver"}


@dataclass
class Actor:
    client: TestClient
    user_id: str
    csrf: str

    def _headers(self) -> dict[str, str]:
        return {**ORIGIN, "X-CSRF-Token": self.csrf}

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.client.get(path, **kwargs)

    def post(self, path: str, json: Any = None) -> httpx.Response:
        return self.client.post(path, json=json, headers=self._headers())

    def patch(self, path: str, json: Any = None) -> httpx.Response:
        return self.client.patch(path, json=json, headers=self._headers())

    def delete(self, path: str) -> httpx.Response:
        return self.client.delete(path, headers=self._headers())


def sign_in(client: TestClient, subject: str | None = None) -> Actor:
    response = client.post(
        "/api/v1/auth/dev-login", json={"subject": subject or uuid4().hex}, headers=ORIGIN
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return Actor(client, body["user_id"], body["csrf_token"])
