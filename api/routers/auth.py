# -*- coding: utf-8 -*-
# Derived from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler).
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.

import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from api.services.auth_service import (
    AUTH_COOKIE,
    CSRF_COOKIE,
    check_login_rate_limit,
    cookie_secure,
    create_session,
    get_valid_session,
    record_failed_login,
    require_admin,
    require_csrf,
    revoke_session,
    rotate_csrf,
    verify_credentials,
)


router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    """Administrator credentials submitted over the same-origin API."""

    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


@router.get("/csrf")
async def get_csrf(request: Request, response: Response):
    token = request.cookies.get(AUTH_COOKIE)
    csrf_token = await rotate_csrf(token)
    if csrf_token is None:
        csrf_token = request.cookies.get(CSRF_COOKIE)
        if not csrf_token:
            import secrets

            csrf_token = secrets.token_urlsafe(32)
        response.set_cookie(
            CSRF_COOKIE,
            csrf_token,
            max_age=600,
            httponly=False,
            secure=cookie_secure(),
            samesite="lax",
            path="/",
        )
    response.headers["Cache-Control"] = "no-store"
    return {"csrf_token": csrf_token}


@router.post("/login")
async def login(payload: LoginRequest, request: Request, response: Response):
    client_ip = request.client.host if request.client else "unknown"
    check_login_rate_limit(client_ip)
    supplied_csrf = request.headers.get("X-CSRF-Token", "")
    csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
    if not supplied_csrf or not csrf_cookie or not hmac.compare_digest(supplied_csrf, csrf_cookie):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
    if not verify_credentials(payload.username, payload.password):
        record_failed_login(client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token, csrf_token = await create_session()
    response.set_cookie(
        AUTH_COOKIE,
        token,
        max_age=43200,
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=43200,
        httponly=False,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"username": payload.username}


@router.get("/me")
async def me(username: str = Depends(require_admin)):
    return {"username": username}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    _username: str = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
):
    await revoke_session(request.cookies.get(AUTH_COOKIE))
    response.delete_cookie(AUTH_COOKIE, path="/", secure=cookie_secure(), httponly=True, samesite="lax")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=cookie_secure(), samesite="lax")
