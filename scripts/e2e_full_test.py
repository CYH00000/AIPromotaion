# -*- coding: utf-8 -*-
r"""Small-end-to-end acceptance test against the running local API.

Run: .tools\uv.exe run --env-file .env python scripts/e2e_full_test.py
"""

import csv
import io
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from openpyxl import load_workbook


BASE = "http://127.0.0.1:8080"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_admin_credentials() -> tuple[str, str]:
    values: dict[str, str] = {}
    for line in (PROJECT_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip()
    return values["ADMIN_USERNAME"], values["ADMIN_PASSWORD"]


class ApiClient:
    def __init__(self) -> None:
        self.client = httpx.Client(base_url=BASE, timeout=90.0)
        self.csrf = self.client.get("/api/auth/csrf").json()["csrf_token"]

    def login(self, username: str, password: str) -> None:
        response = self.client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
            headers={"X-CSRF-Token": self.csrf},
        )
        response.raise_for_status()
        self.csrf = self.client.get("/api/auth/csrf").json()["csrf_token"]

    def post(self, path: str, body=None) -> httpx.Response:
        return self.client.post(path, json=body, headers={"X-CSRF-Token": self.csrf})

    def patch(self, path: str, body) -> httpx.Response:
        return self.client.patch(path, json=body, headers={"X-CSRF-Token": self.csrf})

    def tasks(self) -> dict:
        return self.client.get("/api/tasks").json()

    def runs(self, task_id: str) -> dict:
        return self.client.get("/api/runs", params={"task_id": task_id, "limit": 1}).json()

    def comments(self, task_id: str) -> dict:
        return self.client.get(
            "/api/comments", params={"task_id": task_id, "limit": 50}
        ).json()


def wait_run(api: ApiClient, task_id: str, timeout: int = 300) -> dict:
    deadline = time.time() + timeout
    last: dict | None = None
    while time.time() < deadline:
        items = api.runs(task_id).get("items", [])
        if items:
            last = items[0]
            print(
                f"  run={last['id'][:8]} status={last['status']} phase={last['phase']} "
                f"progress={last.get('progress', {})}",
                flush=True,
            )
            if last["status"] not in {"queued", "running"}:
                return last
        time.sleep(5)
    raise TimeoutError(f"run did not finish: {last}")


def run_task(api: ApiClient, task_id: str, attempts: int = 2) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        response = api.post(f"/api/tasks/{task_id}/run")
        if response.status_code != 202:
            raise AssertionError(f"run rejected: {response.status_code} {response.text}")
        result = wait_run(api, task_id)
        if result["status"] in {"succeeded", "partial"}:
            return result
        last_error = AssertionError(f"run failed: {result}")
        if attempt < attempts:
            print(f"  retrying failed run (attempt {attempt + 1})", flush=True)
            time.sleep(5)
    raise last_error or AssertionError("run failed")


def create_task(api: ApiClient, payload: dict) -> dict:
    response = api.post("/api/tasks", payload)
    if response.status_code != 201:
        raise AssertionError(f"task creation failed: {response.status_code} {response.text}")
    return response.json()


def check_exports(api: ApiClient, task_id: str, expected_rows: int) -> None:
    csv_response = api.client.get(
        "/api/exports/comments", params={"task_id": task_id, "format": "csv"}
    )
    csv_response.raise_for_status()
    rows = list(csv.reader(io.StringIO(csv_response.text)))
    assert len(rows) == expected_rows, f"CSV rows={len(rows)} expected={expected_rows}"
    xlsx_response = api.client.get(
        "/api/exports/comments", params={"task_id": task_id, "format": "xlsx"}
    )
    xlsx_response.raise_for_status()
    assert xlsx_response.content[:2] == b"PK"
    workbook = load_workbook(io.BytesIO(xlsx_response.content), read_only=True)
    xlsx_rows = list(workbook.active.iter_rows(values_only=True))
    assert len(xlsx_rows) == expected_rows, len(xlsx_rows)
    print(f"  export CSV rows={len(rows)} XLSX rows={len(xlsx_rows)}", flush=True)


def main() -> int:
    failures: list[str] = []
    username, password = load_admin_credentials()
    api = ApiClient()

    unauthenticated = api.client.get("/api/tasks")
    assert unauthenticated.status_code == 401, unauthenticated.text
    api.login(username, password)
    me = api.client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["username"] == username
    print("PHASE_AUTH OK", flush=True)

    stamp = datetime.now().strftime("%H%M%S")
    search_task = create_task(
        api,
        {
            "name": f"E2E-Search-{stamp}",
            "platform": "dy",
            "source_mode": "search",
            "source_values": ["软件开发"],
            "include_keywords": [],
            "exclude_keywords": [],
            "filter_rule_id": None,
            "max_contents": 1,
            "max_comments_per_content": 5,
            "content_sort": "latest",
            "publish_time_days": 7,
            "schedule_type": "manual",
            "schedule_value": None,
        },
    )
    assert search_task["content_sort"] == "latest"
    assert search_task["publish_time_days"] == 7
    paused = api.post(f"/api/tasks/{search_task['id']}/pause")
    assert paused.status_code == 200, paused.text
    search_result = run_task(api, search_task["id"])
    counts = search_result["counts"]
    seen = int(counts.get("seen", 0))
    assert 0 < seen <= 5, counts
    assert counts.get("matched") == seen, counts
    search_comments = api.comments(search_task["id"])
    assert search_comments["total"] == seen, search_comments
    print("PHASE_SEARCH OK", search_comments["items"][0]["content_title"], flush=True)
    check_exports(api, search_task["id"], seen + 1)

    detail_task = create_task(
        api,
        {
            "name": f"E2E-Dedup-{stamp}",
            "platform": "dy",
            "source_mode": "detail",
            "source_values": [
                "https://www.douyin.com/video/7706834804931842047"
            ],
            "include_keywords": [],
            "exclude_keywords": [],
            "filter_rule_id": None,
            "max_contents": 1,
            "max_comments_per_content": 5,
            "content_sort": "general",
            "publish_time_days": 0,
            "schedule_type": "manual",
            "schedule_value": None,
        },
    )
    first_detail = run_task(api, detail_task["id"])
    second_detail = run_task(api, detail_task["id"])
    detail_comments = api.comments(detail_task["id"])
    first_total = int(first_detail["counts"].get("matched", 0))
    second_total = int(second_detail["counts"].get("matched", 0))
    assert first_total > 0 and second_total > 0
    assert detail_comments["total"] == first_total, detail_comments
    snapshots = api.client.get(
        f"/api/comments/{detail_comments['items'][0]['id']}/snapshots"
    ).json()
    snapshot_items = snapshots.get("items", snapshots if isinstance(snapshots, list) else [])
    assert len(snapshot_items) >= 2, snapshots
    print("PHASE_DEDUP OK comments=", detail_comments["total"], "snapshots=", len(snapshot_items), flush=True)

    ai_task = create_task(
        api,
        {
            "name": f"E2E-AI-{stamp}",
            "platform": "dy",
            "source_mode": "detail",
            "source_values": [
                "https://www.douyin.com/video/7706834804931842047"
            ],
            "include_keywords": [],
            "exclude_keywords": [],
            "filter_rule_id": "3b12eb90-0b3a-4277-8aba-1d6878d4b52e",
            "max_contents": 1,
            "max_comments_per_content": 5,
            "content_sort": "general",
            "publish_time_days": 0,
            "schedule_type": "manual",
            "schedule_value": None,
        },
    )
    ai_result = run_task(api, ai_task["id"])
    ai_counts = ai_result["counts"]
    print("PHASE_AI", ai_result["status"], ai_counts, flush=True)
    semantic_total = sum(
        int(ai_counts.get(key, 0))
        for key in ("semantic_matched", "semantic_filtered", "semantic_failed")
    )
    assert semantic_total == int(ai_counts.get("seen", 0)), ai_counts

    logout = api.post("/api/auth/logout")
    assert logout.status_code == 204, logout.text
    assert api.client.get("/api/tasks").status_code == 401
    print("PHASE_LOGOUT OK", flush=True)
    print("ALL_API_E2E_OK", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"E2E_FAILED: {type(exc).__name__}: {exc}", flush=True)
        raise
