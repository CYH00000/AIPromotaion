import pytest

import api.services.collection_pipeline as pipeline
import api.services.filter_model_client as model_client


@pytest.mark.asyncio
async def test_request_json_retries_transient_timeouts(monkeypatch):
    attempts = {"post": 0, "sleep": 0}

    monkeypatch.setattr(
        model_client,
        "model_configuration",
        lambda: {
            "base_url": "https://example.com",
            "api_key": "test-key",
            "model_name": "test-model",
            "timeout_seconds": 90,
            "configured": True,
        },
    )

    async def fake_validate(_base_url):
        return "https://example.com/chat/completions"

    async def fake_post(_url, _payload, _config):
        attempts["post"] += 1
        if attempts["post"] < 3:
            raise model_client.FilterModelError("智能筛选服务请求超时。", "timeout")
        return {"ok": True}

    async def fake_sleep(_seconds):
        attempts["sleep"] += 1

    monkeypatch.setattr(model_client, "_validate_cloud_endpoint", fake_validate)
    monkeypatch.setattr(model_client, "_post_once", fake_post)
    monkeypatch.setattr(model_client.asyncio, "sleep", fake_sleep)

    result = await model_client._request_json("system", {"value": 1})

    assert result == {"ok": True}
    assert attempts == {"post": 3, "sleep": 2}


@pytest.mark.asyncio
async def test_request_json_does_not_retry_config_errors(monkeypatch):
    attempts = {"post": 0}

    monkeypatch.setattr(
        model_client,
        "model_configuration",
        lambda: {
            "base_url": "https://example.com",
            "api_key": "test-key",
            "model_name": "test-model",
            "timeout_seconds": 90,
            "configured": True,
        },
    )

    async def fake_validate(_base_url):
        return "https://example.com/chat/completions"

    async def fake_post(_url, _payload, _config):
        attempts["post"] += 1
        raise model_client.FilterModelError("配置错误。", "config")

    monkeypatch.setattr(model_client, "_validate_cloud_endpoint", fake_validate)
    monkeypatch.setattr(model_client, "_post_once", fake_post)

    with pytest.raises(model_client.FilterModelError) as exc:
        await model_client._request_json("system", {"value": 1})

    assert exc.value.code == "config"
    assert attempts["post"] == 1


@pytest.mark.asyncio
async def test_evaluate_candidates_continues_after_one_failed_batch(monkeypatch):
    candidates = [
        {"normalized": {"body": f"评论 {index}"}, "matched_keywords": []}
        for index in range(60)
    ]
    calls = {"count": 0}

    async def fake_evaluate(_rule, comments):
        calls["count"] += 1
        if calls["count"] == 2:
            raise model_client.FilterModelError("智能筛选服务请求超时。", "timeout")
        return [
            {"index": item["index"], "matched": True, "reason": "符合需求"}
            for item in comments
        ]

    monkeypatch.setattr(pipeline, "evaluate_comment_batch", fake_evaluate)

    counts = await pipeline.evaluate_candidates(candidates, {"id": "rule-1"})

    assert calls["count"] == 3
    assert counts["semantic_matched"] == 40
    assert counts["semantic_failed"] == 20
    assert counts["semantic_error_code"] == "timeout"
    assert candidates[20]["semantic_decision"] is None
    assert candidates[40]["semantic_decision"]["matched"] is True
