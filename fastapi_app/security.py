import hmac

from fastapi import Header, HTTPException, status

from .config import settings


def _require(expected: str, authorization: str | None) -> None:
    provided = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not expected or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")


def require_portal_token(authorization: str | None = Header(default=None)) -> None:
    configured = settings()
    _require(configured.portal_auth_token or configured.service_auth_token, authorization)


def require_frappe_token(authorization: str | None = Header(default=None)) -> None:
    configured = settings()
    _require(configured.frappe_auth_token or configured.service_auth_token, authorization)
