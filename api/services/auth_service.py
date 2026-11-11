# -*- coding: utf-8 -*-
# Derived from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler).
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.

import hashlib
import hmac
import os
import secrets
from datetime import timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import select, update

from database.collector_database import collector_session
from database.collector_models import AdminSession, utc_now


AUTH_COOKIE = "collector_session"
CSRF_COOKIE = "collector_csrf"
SESSION_TTL = timedelta(hours=12)
_failed_logins: dict[str, list[float]] = {}


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def cookie_secure() -> bool:
    return os.getenv("SESSION_COOKIE_SECURE", "false").casefold() == "true"


def check_login_rate_limit(client_ip: str) -> None:
    """Limit repeated failed logins without retaining usernames or passwords."""
    import time

    now = time.monotonic()
    attempts = [stamp for stamp in _failed_logins.get(client_ip, []) if now - stamp < 300]
    _failed_logins[client_ip] = attempts
    if len(attempts) >= 5:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Try again later")


def record_failed_login(client_ip: str) -> None:
    import time

    _failed_logins.setdefault(client_ip, []).append(time.monotonic())


def verify_credentials(username: str, password: str) -> bool:
    expected_username = os.getenv("ADMIN_USERNAME", "")
    expected_password = os.getenv("ADMIN_PASSWORD", "")
    if not expected_username or not expected_password:
        return False
    return hmac.compare_digest(username, expected_username) and hmac.compare_digest(password, expected_password)


async def create_session() -> tuple[str, str]:
    token = secrets.token_urlsafe(40)
    csrf_token = secrets.token_urlsafe(32)
    async with collector_session() as session:
        session.add(
            AdminSession(
                token_digest=_digest(token),
                csrf_digest=_digest(csrf_token),
                expires_at=utc_now() + SESSION_TTL,
            )
        )
    return token, csrf_token


async def get_valid_session(token: str | None) -> AdminSession | None:
    if not token:
        return None
    async with collector_session() as session:
        result = await session.execute(
            select(AdminSession).where(
                AdminSession.token_digest == _digest(token),
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > utc_now(),
            )
        )
        return result.scalar_one_or_none()


async def rotate_csrf(token: str | None) -> str | None:
    current = await get_valid_session(token)
    if current is None:
        return None
    csrf_token = secrets.token_urlsafe(32)
    async with collector_session() as session:
        await session.execute(
            update(AdminSession)
            .where(AdminSession.token_digest == current.token_digest)
            .values(csrf_digest=_digest(csrf_token))
        )
    return csrf_token


async def revoke_session(token: str | None) -> None:
    if not token:
        return
    async with collector_session() as session:
        await session.execute(
            update(AdminSession)
            .where(AdminSession.token_digest == _digest(token), AdminSession.revoked_at.is_(None))
            .values(revoked_at=utc_now())
        )


async def require_admin(request: Request) -> str:
    session = await get_valid_session(request.cookies.get(AUTH_COOKIE))
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return os.getenv("ADMIN_USERNAME", "admin")


async def require_csrf(request: Request) -> None:
    session = await get_valid_session(request.cookies.get(AUTH_COOKIE))
    supplied = request.headers.get("X-CSRF-Token", "")
    if session is None or not supplied or not hmac.compare_digest(session.csrf_digest, _digest(supplied)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
