"""FastAPI dependencies: auth, rate limits, logging."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.api_tokens import resolve_token
from api.rate_limit import LIMITER

bearer_scheme = HTTPBearer(auto_error=False)


def current_api_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    raw = creds.credentials.strip() if creds and creds.credentials else ""
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header.")
    user = resolve_token(raw)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired API token.")
    key = f"user:{user['UserId']}"
    if not LIMITER.allow(key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded (60/min).")
    request.state.user_id = int(user["UserId"])
    request.state.role = str(user.get("Role") or "User")
    return user


def require_admin(user: dict[str, Any] = Depends(current_api_user)) -> dict[str, Any]:
    if str(user.get("Role") or "") != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required.")
    return user
