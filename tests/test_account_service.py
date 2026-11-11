import pytest

import api.services.account_service as account_service
import config


@pytest.fixture
def browser_root(tmp_path, monkeypatch):
    monkeypatch.setattr(account_service, "BROWSER_DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "ENABLE_CDP_MODE", False)
    account_service._login_states.update(
        {
            platform: {"state": "idle", "started_at": None, "error": None}
            for platform in account_service.PLATFORMS
        }
    )
    return tmp_path


def test_profile_dir_uses_standard_and_cdp_names(browser_root, monkeypatch):
    assert account_service.profile_dir("dy") == browser_root / "dy_user_data_dir"
    monkeypatch.setattr(config, "ENABLE_CDP_MODE", True)
    assert account_service.profile_dir("dy") == browser_root / "cdp_dy_user_data_dir"
    with pytest.raises(account_service.AccountPlatformError):
        account_service.profile_dir("bad")


def test_status_reads_marker_and_falls_back_to_directory(browser_root):
    profile = account_service.profile_dir("xhs")
    profile.mkdir()
    marker = account_service.login_marker_path("xhs")
    marker.parent.mkdir(parents=True)
    marker.write_text('{"logged_in_at": "2026-11-11T08:00:00+00:00"}', encoding="utf-8")

    items = {item["platform"]: item for item in account_service.account_status()}

    assert items["xhs"]["configured"] is True
    assert items["xhs"]["last_login_at"].startswith("2026-11-11T08:00:00")
    assert items["dy"]["configured"] is False


@pytest.mark.asyncio
async def test_unbind_removes_profile_and_marker(browser_root):
    profile = account_service.profile_dir("dy")
    profile.mkdir()
    marker = account_service.login_marker_path("dy")
    marker.parent.mkdir(parents=True)
    marker.write_text("{}", encoding="utf-8")

    await account_service.unbind("dy")

    assert not profile.exists()
    assert not marker.exists()
    await account_service.unbind("dy")  # idempotent


@pytest.mark.asyncio
async def test_unbind_rejects_path_outside_browser_data(browser_root, monkeypatch):
    outside = browser_root.parent / "outside"
    monkeypatch.setattr(account_service, "profile_dir", lambda platform: outside)
    with pytest.raises(account_service.AccountPlatformError):
        await account_service.unbind("dy")


@pytest.mark.asyncio
async def test_login_rejects_busy_process(browser_root, monkeypatch):
    class RunningProcess:
        def poll(self):
            return None

    monkeypatch.setattr(account_service.crawler_manager, "process", RunningProcess())
    with pytest.raises(account_service.AccountBusyError):
        await account_service.start_login("dy")
