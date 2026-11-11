from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.routers.accounts as accounts_module
from api.services.account_service import AccountBusyError, AccountPlatformError
from api.services.auth_service import require_admin, require_csrf


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(accounts_module.router, prefix="/api")
    app.dependency_overrides[require_admin] = lambda: "admin"
    app.dependency_overrides[require_csrf] = lambda: None
    return TestClient(app)


def test_list_accounts_returns_items(monkeypatch):
    monkeypatch.setattr(
        accounts_module,
        "account_status",
        lambda: [{"platform": "dy", "label": "抖音", "configured": True}],
    )

    response = make_client().get("/api/accounts")

    assert response.status_code == 200
    assert response.json()["items"][0]["platform"] == "dy"


def test_login_maps_platform_error_to_400(monkeypatch):
    async def fail(platform: str):
        raise AccountPlatformError("Unsupported platform")

    monkeypatch.setattr(accounts_module, "start_login", fail)
    response = make_client().post("/api/accounts/bad/login")
    assert response.status_code == 400


def test_login_maps_busy_error_to_409(monkeypatch):
    async def fail(platform: str):
        raise AccountBusyError("A collector process is already running.")

    monkeypatch.setattr(accounts_module, "start_login", fail)
    response = make_client().post("/api/accounts/dy/login")
    assert response.status_code == 409


def test_unbind_returns_204(monkeypatch):
    calls: list[str] = []

    async def fake_unbind(platform: str):
        calls.append(platform)

    monkeypatch.setattr(accounts_module, "unbind", fake_unbind)
    response = make_client().delete("/api/accounts/xhs")

    assert response.status_code == 204
    assert calls == ["xhs"]
