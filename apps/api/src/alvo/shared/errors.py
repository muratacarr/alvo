"""Error contract shared by all modules: a status code and a stable, non-revealing code."""


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, extra: dict[str, object] | None = None) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.extra = extra or {}
