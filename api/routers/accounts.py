# -*- coding: utf-8 -*-
# Derived from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler).
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.

from fastapi import APIRouter, Depends, HTTPException, status

from api.services.account_service import (
    AccountBusyError,
    AccountPlatformError,
    account_status,
    start_login,
    unbind,
)
from api.services.auth_service import require_admin, require_csrf


router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("")
async def list_accounts(_username: str = Depends(require_admin)):
    return {"items": account_status()}


@router.post("/{platform}/login", status_code=status.HTTP_202_ACCEPTED)
async def login_account(
    platform: str,
    _username: str = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
):
    try:
        return await start_login(platform)
    except AccountPlatformError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccountBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/{platform}", status_code=status.HTTP_204_NO_CONTENT)
async def unbind_account(
    platform: str,
    _username: str = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
):
    try:
        await unbind(platform)
    except AccountPlatformError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccountBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
