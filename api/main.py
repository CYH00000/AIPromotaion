# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/main.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

"""
MediaCrawler WebUI API Server
Start command: uvicorn api.main:app --port 8080 --reload
Or: python -m api.main
"""
import asyncio
import os
import sys
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import HTTPException
from sqlalchemy import text

from .routers import accounts_router, auth_router, collection_router, crawler_router, data_router, filter_rules_router, websocket_router
from .services.auth_service import require_admin
from .services.collection_worker import collection_worker
from database.collector_database import apply_collector_migrations, close_collector_database, engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    admin_username = os.getenv("ADMIN_USERNAME", "")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if not admin_username or len(admin_password) < 16 or admin_password.startswith("replace-with"):
        raise RuntimeError("Set ADMIN_USERNAME and a unique ADMIN_PASSWORD of at least 16 characters in .env")
    await apply_collector_migrations()
    await collection_worker.start()
    try:
        yield
    finally:
        await collection_worker.stop()
        await close_collector_database()

app = FastAPI(
    title="MediaCrawler WebUI API",
    description="Comment collection management API",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

# Get webui static files directory
WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")

# CORS configuration - allow frontend dev server access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Backup port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(crawler_router, prefix="/api", dependencies=[Depends(require_admin)])
app.include_router(data_router, prefix="/api", dependencies=[Depends(require_admin)])
app.include_router(websocket_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(collection_router, prefix="/api")
app.include_router(filter_rules_router, prefix="/api")
app.include_router(accounts_router, prefix="/api")


@app.get("/")
async def serve_frontend():
    """Return frontend page"""
    index_path = os.path.join(WEBUI_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "message": "MediaCrawler WebUI API",
        "version": "1.0.0",
        "docs": "/docs",
        "note": "WebUI not found, please build it first: cd webui && npm run build"
    }


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/health/live")
async def liveness_probe():
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness_probe():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Required service is unavailable") from exc
    return {"status": "ready"}


@app.get("/api/env/check", dependencies=[Depends(require_admin)])
async def check_environment():
    """Check if MediaCrawler environment is configured correctly"""
    try:
        # Run uv run main.py --help command to check environment
        # Use PROJECT_ROOT so it works regardless of where uvicorn was started
        if sys.platform == "win32":
            loop = asyncio.get_running_loop()
            process = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    [sys.executable, "main.py", "--help"],
                    capture_output=True,
                    timeout=30.0,
                    cwd=str(PROJECT_ROOT)
                )
            )
            stdout, stderr = process.stdout, process.stderr  # bytes
        else:
            process = await asyncio.create_subprocess_exec(
                sys.executable, "main.py", "--help",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(PROJECT_ROOT)  # Project root directory
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0  # 30 seconds timeout
            )
        if process.returncode == 0:
            return {
                "success": True,
                "message": "采集环境检查通过",
                "output": stdout.decode("utf-8", errors="ignore")[:500]  # Truncate to first 500 characters
            }
        else:
            error_msg = stderr.decode("utf-8", errors="ignore") or stdout.decode("utf-8", errors="ignore")
            return {
                "success": False,
                "message": "环境检查失败",
                "error": error_msg[:500]
            }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "message": "环境检查超时",
            "error": "命令执行超过 30 秒"
        }
    except FileNotFoundError:
        return {
            "success": False,
            "message": "未找到 uv 命令",
            "error": "请确认 uv 已安装并加入系统 PATH"
        }
    except Exception as e:
        return {
            "success": False,
            "message": "环境检查异常",
            "error": f"{type(e).__name__}: {str(e) or '未知错误'}"
        }


@app.get("/api/config/platforms", dependencies=[Depends(require_admin)])
async def get_platforms():
    """Get list of supported platforms"""
    return {
        "platforms": [
            {"value": "xhs", "label": "小红书", "icon": "book-open"},
            {"value": "dy", "label": "抖音", "icon": "music"},
            {"value": "ks", "label": "快手", "icon": "video"},
            {"value": "bili", "label": "哔哩哔哩", "icon": "tv"},
            {"value": "wb", "label": "微博", "icon": "message-circle"},
            {"value": "tieba", "label": "百度贴吧", "icon": "messages-square"},
            {"value": "zhihu", "label": "知乎", "icon": "help-circle"},
        ]
    }


@app.get("/api/config/options", dependencies=[Depends(require_admin)])
async def get_config_options():
    """Get all configuration options"""
    return {
        "login_types": [
            {"value": "qrcode", "label": "扫码登录"},
            {"value": "cookie", "label": "Cookie 登录"},
        ],
        "crawler_types": [
            {"value": "search", "label": "关键词搜索"},
            {"value": "detail", "label": "指定内容"},
            {"value": "creator", "label": "创作者主页"},
        ],
        "save_options": [
            {"value": "jsonl", "label": "JSONL 文件"},
            {"value": "json", "label": "JSON 文件"},
            {"value": "csv", "label": "CSV 文件"},
            {"value": "excel", "label": "Excel 文件"},
            {"value": "sqlite", "label": "SQLite 数据库"},
            {"value": "db", "label": "MySQL 数据库"},
            {"value": "mongodb", "label": "MongoDB 数据库"},
        ],
    }


# Mount static resources - must be placed after all routes
if os.path.exists(WEBUI_DIR):
    assets_dir = os.path.join(WEBUI_DIR, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    # Mount logos directory
    logos_dir = os.path.join(WEBUI_DIR, "logos")
    if os.path.exists(logos_dir):
        app.mount("/logos", StaticFiles(directory=logos_dir), name="logos")
    # Mount application static files.
    app.mount("/static", StaticFiles(directory=WEBUI_DIR), name="webui-static")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
