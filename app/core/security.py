import hmac
import re
from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from app.core.config import settings


SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.:-]+$")


@dataclass(frozen=True)
class SecurityContext:
    require_api_key: bool
    allowed_tool_scopes: set[str]


def security_context() -> SecurityContext:
    return SecurityContext(
        require_api_key=settings.require_api_key,
        allowed_tool_scopes={
            item.strip()
            for item in settings.allowed_tool_scopes.split(",")
            if item.strip()
        },
    )


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.require_api_key:
        return
    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key auth is enabled but API_KEY is not configured",
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")


def validate_session_id(session_id: str) -> str:
    if len(session_id) > settings.max_session_id_length:
        raise ValueError("session_id is too long")
    if not SESSION_ID_PATTERN.match(session_id):
        raise ValueError("session_id contains unsupported characters")
    return session_id


def validate_text_length(name: str, value: str, max_length: int) -> str:
    if len(value) > max_length:
        raise ValueError(f"{name} is too long")
    return value
