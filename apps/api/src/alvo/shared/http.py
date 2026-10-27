"""HTTP-level guards that apply to every route."""

from datetime import datetime
from ipaddress import ip_address

from fastapi import Request
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send


def get_now(request: Request) -> datetime:
    """The application clock (injectable in tests)."""
    now: datetime = request.app.state.clock()
    return now


def client_address(request: Request, *, trust_forwarded_for: bool) -> str:
    """The caller's address for rate limiting.

    `X-Forwarded-For` is honoured only when configured, because only our own nginx (which
    overwrites it) may be trusted to set it. A malformed value falls back to the socket peer.
    """
    if trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[-1].strip()
        try:
            return str(ip_address(forwarded))
        except ValueError:
            pass
    return request.client.host if request.client else "unknown"


class PayloadTooLarge(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=413)


_TOO_LARGE_BODY = b'{"error":"payload_too_large"}'


class BodySizeLimitMiddleware:
    """Rejects oversized request bodies, whether or not the client declares a length.

    The declared `Content-Length` is only a fast path; the bytes actually received are
    counted too, so chunked uploads cannot bypass the limit.
    """

    def __init__(
        self,
        app: ASGIApp,
        max_bytes: int,
        large_suffixes: tuple[str, ...] = (),
        large_max_bytes: int | None = None,
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.large_suffixes = large_suffixes
        self.large_max_bytes = large_max_bytes or max_bytes

    def _limit_for(self, path: str) -> int:
        if self.large_suffixes and path.endswith(self.large_suffixes):
            return self.large_max_bytes
        return self.max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self._limit_for(scope["path"])
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = limit + 1
                if declared > limit:
                    await self._reject(send)
                    return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise PayloadTooLarge
            return message

        await self.app(scope, limited_receive, send)

    @staticmethod
    async def _reject(send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_TOO_LARGE_BODY)).encode()),
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _TOO_LARGE_BODY})
