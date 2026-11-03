import re
from urllib.parse import unquote

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send


_GIT_METADATA_SEGMENT = re.compile(r"(?:^|/)\\.git(?:/|$)", re.IGNORECASE)


def _is_git_metadata_path(scope: Scope) -> bool:
    """Detect a .git directory path, including percent-encoded variants."""
    candidates = [str(scope.get("path") or "")]
    raw_path = scope.get("raw_path")
    if isinstance(raw_path, bytes):
        candidates.append(raw_path.decode("latin-1", errors="ignore"))

    for candidate in candidates:
        decoded = candidate
        # Repeated decoding also catches double-encoded dot/slash characters.
        for _ in range(3):
            if _GIT_METADATA_SEGMENT.search(decoded):
                return True
            next_value = unquote(decoded)
            if next_value == decoded:
                break
            decoded = next_value

    return False


class BlockGitMetadataMiddleware:
    """Deny direct HTTP access to Git metadata directories."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") == "http" and _is_git_metadata_path(scope):
            response = PlainTextResponse(
                "Not Found",
                status_code=404,
                headers={
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
