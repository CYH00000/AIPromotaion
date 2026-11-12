# 2026-11-12 全流程验收记录

- 代码基线：`5f2e539 docs(auth): define registration and user isolation`
- 环境：Windows PowerShell、Python 3.12、Playwright Chromium、Docker PostgreSQL 18
- 目的：验证当前本地 MVP 在部署前的自动化和实际运行链路

## 自动化门禁

| 项目 | 命令 | 结果 |
|---|---|---|
| Python 测试 | `uv run --env-file .env pytest tests -q` | 364 通过，2 跳过，1 个 SQLAlchemy 2.0 弃用警告 |
| 前端静态检查 | `npm run lint` | 0 错误，8 个既有 React Hook/Fast Refresh 警告 |
| 前端生产构建 | `npm run build` | 成功；主 JS 约 500.62 kB，存在分包体积提示 |
| 数据库迁移 | `alembic current/heads/upgrade head/check` | 当前与最新版本均为 `2b3c4d5e6f70`，无待生成迁移 |
| pre-commit | `pre-commit run --all-files` | 未完成：GitHub 连接重置，无法下载钩子环境；不是代码检查失败 |

## 实际进程与页面

- FastAPI 在 `http://127.0.0.1:8080` 实际启动。
- `/api/health`、`/health/ready` 和前端首页均返回 200。
- 未认证业务接口返回 401。
- 管理员 CSRF 登录、`/api/auth/me`、任务列表、平台状态、退出登录均通过；退出后旧会话返回 401。
- Playwright UI 验收通过：登录、中文主题文案、任务/评论/账号标签、任务详情、内容排序和发布时间选项、退出登录均可用。
- UI 截图：`C:\Users\22574\AppData\Local\Temp\codex-e2e-ui.png`

## 真实平台小范围验收

抖音单平台验收使用每项最多 1 条内容、5 条评论：

- 关键词搜索：「软件开发」，最新发布、一周内；采集 5 条评论，运行成功。
- CSV 和 XLSX 导出均包含表头在内的 6 行。
- 指定视频链接连续运行两次；评论主记录保持 5 条，生成 2 个运行快照，验证去重和快照累积。
- AI 语义筛选处理 5 条评论：0 条语义失败，规则链路完成，运行成功。
- 验收脚本退出登录并验证未认证访问被拒绝。

本次没有执行小红书真实平台验收。小红书指定链接与发布时间过滤仍需使用已授权账号进行受控小范围验证。

## 私有云部署包本地验收（2026-11-12）

本轮在 `codex/cloud-deployment` 分支对生产 Dockerfile、Compose 拓扑、容器运行入口、私有 HTTPS 脚本、备份恢复和前端运行链路做了隔离验收。没有连接真实云服务器，也没有读取或输出任何真实秘密值。

### 环境与隔离范围

- Windows 11、Docker Desktop 29.5.3、Git Bash、Python 3.12。
- 合成 Compose 项目：`collector-cloud-backup-test`。
- 合成宿主机端口：应用 `127.0.0.1:18080`，noVNC `127.0.0.1:16080`。
- PostgreSQL 18、独立命名卷和一次性测试口令均为本轮合成数据。
- 生产配置模板仍强制 `SESSION_COOKIE_SECURE=true`；本地 API 冒烟测试仅在测试客户端中携带来回 Secure Cookie，没有放宽应用配置。

### 自动化与构建

| 项目 | 命令 | 结果 |
|---|---|---|
| 完整 Python 测试 | `uv run --env-file .env pytest tests -q` | 389 通过，2 跳过，1 个 SQLAlchemy 弃用警告 |
| 云部署契约测试 | `uv run --env-file .env pytest tests/test_cloud_deployment.py -q` | 25 通过 |
| 前端静态检查 | `npm run lint` | 0 错误，8 个既有 React Hook/Fast Refresh 警告 |
| 前端生产构建 | `npm run build` | 成功；主 JS 500.62 kB，仍有分包体积提示 |
| Shell 语法 | Git Bash 对 `deploy/*.sh` 执行 `bash -n` | 全部通过 |
| Compose 渲染 | `docker compose ... config --quiet` | 通过 |
| 生产镜像 | `docker build -f deploy/Dockerfile ...` | 成功；Node 22 构建页、Playwright Python 1.61 运行 |

### 容器与页面

- `app` 和 `postgres` 均达到健康状态，`/health/ready` 返回 200，前端首页返回 200。
- noVNC `/vnc.html` 返回 200，容器内 Xvfb、x11vnc、websockify 和 Uvicorn 均由入口脚本监管。
- 容器实际用户为 UID/GID `10001:10001`，不是 root。
- 应用端口只发布到 `127.0.0.1:18080`，noVNC 只发布到 `127.0.0.1:16080`；PostgreSQL 没有宿主机端口，容器未发布 9222。
- `/api/tasks` 未登录返回 401；CSRF 登录、`/api/auth/me`、任务列表和退出登录全部通过，退出后旧会话再次返回 401。
- Playwright 对容器内的生产前端做 UI 验收：登录、任务管理、评论结果、账号管理、任务创建字段、中文主题和退出登录均通过。
- UI 截图：`C:\Users\22574\AppData\Local\Temp\codex-e2e-ui.png`。

### 持久化与恢复

- 创建合成任务“云端持久化验收-20261112”，重启 `app` 后任务仍存在。
- 在 `browser_data` 和 `project_data` 写入不同标记；重启 `app` 后再重启 `app + postgres`，两个标记和合成任务都保持存在。
- 加密备份生成 `postgres.dump.enc`、`browser_data.tar.gz.enc`、`project_data.tar.gz.enc`、`metadata.txt` 和 `SHA256SUMS`。
- 三个加密产物均具有 `Salted__` 头，`sha256sum -c SHA256SUMS` 全部通过；解密后的两个卷归档均通过 `gzip -t`，并包含恢复时预期的标记。
- 故意修改数据库、浏览器卷和项目卷的标记后执行 `restore.sh --confirm`，三类标记均恢复为备份时值，应用重新达到 ready。
- 验收中发现并修复：Windows OpenSSL 不识别 MSYS 路径、停止应用后错误执行 `compose exec`、容器构建日志污染备份流，以及跨 shell 后应用镜像标签不一致。

### 尚未完成的真实环境门禁

- 尚未在真实 Ubuntu 24.04 云服务器安装或执行本部署包；用户需提供服务器地址和 SSH 访问方式后才能远程实施。
- 尚未验证真实 Tailscale Serve 私有域名、服务器安全组、云外部端口扫描和云端 noVNC 扫码登录。
- 尚未在最终云服务器上执行真实抖音/小红书小范围任务；平台登录态、限流和账号权限必须由用户授权后人工确认。
- 现有真实域名按方案保留不用。公网域名入口、云端管理员页面、多用户管理和异地数据库均不属于本次交付。
- Docker 构建时 npm 报告 20 个依赖审计告警；禁止直接执行破坏性 `npm audit fix --force`，需要在独立兼容性评估后处理。

## 部署结论

较早的本地功能、数据库、页面和抖音真实采集链路验收仍作为业务基线有效。当前分支新增的私有云部署包也已通过容器打包、页面、登录、持久卷和加密备份恢复的本地验收，但仍不能据此认定远程生产环境已经上线：

- 生产 Compose、私有网络、非 root 浏览器容器、Tailscale Serve 和秘密配置校验已经提供。
- 云端浏览器必须运行在云服务器；现有 CDP 连接固定为 Worker 主机的 `localhost`。
- 云端扫码登录使用私有 noVNC 画面，浏览器资料保存在持久卷；Cookie 粘贴仍未实现。
- 9222 调试端口不得暴露公网，浏览器资料必须使用持久卷并限制访问权限。
- 正式部署前仍需在真实 Ubuntu 主机完成 Tailscale HTTPS、防火墙、noVNC 登录、公网端口关闭和用户授权平台任务验收。
