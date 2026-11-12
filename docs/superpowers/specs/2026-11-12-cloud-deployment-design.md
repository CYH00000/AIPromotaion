# 单机私有云部署设计

- 日期：2026-11-12
- 状态：已确认，待实施计划
- 目标环境：一台全新 Ubuntu 24.04 云服务器
- 访问方式：Tailscale 私有网络
- 公网入口：不开放 Web、数据库、浏览器调试或 noVNC 端口
- 当前身份模型：单个环境变量管理员

## 1. 目标

为当前本地 MVP 增加一套可重复构建、启动、验证、备份和恢复的单机云端部署包，使管理员能够通过 Tailscale 使用完整工作台，并在云端完成抖音和小红书扫码登录。

部署后必须满足：

- 应用、采集 Worker 和浏览器全部运行在云服务器。
- 浏览器资料、采集暂存数据和 PostgreSQL 数据在容器重启后保留。
- 管理员通过 Tailscale 的 HTTPS 地址访问工作台。
- 扫码登录时通过 Tailscale 私有访问的 noVNC 查看云端浏览器。
- PostgreSQL、应用端口、VNC 和浏览器调试端口均不对公网开放。
- 用一条可重复执行的部署命令完成构建、迁移、启动和健康检查。
- 备份和恢复流程可独立执行并经过验证。

## 2. 非目标

- 公网域名、公网 HTTPS 入口或 ICP 备案。
- 多管理员、公开注册或用户管理页面。
- 多机高可用、分布式 Worker 或多实例调度。
- 将 PostgreSQL 或用户数据迁移到独立数据库服务器。
- 自动登录平台、绕过验证码或平台访问控制。
- 自动从管理员家庭电脑接管浏览器。
- 完整的监控平台、告警供应商或日志托管服务。

## 3. 当前代码约束

- FastAPI 生命周期当前直接启动全局调度监督器和各平台 Worker，因此 Web/API 与 Worker 必须在同一应用进程中，且只能运行一个应用副本。
- 登录和采集请求当前使用 `headless=False`。在无显示器的 Linux 主机上必须提供 Xvfb 虚拟显示。
- 默认使用 Playwright 持久浏览器模式，`ENABLE_CDP_MODE=False`。本方案不启用 CDP，也不公开 `9222`。
- PostgreSQL 连接参数来自 `POSTGRES_DB_*` 环境变量。
- 应用启动时会执行 Alembic 升级；部署脚本还需在启动前显式执行并验证迁移版本。
- 前端生产构建输出到 `api/webui/`，由 FastAPI 同源提供。

## 4. 架构选择

### 4.1 采用方案：单应用容器

一个应用容器同时运行：

- Uvicorn/FastAPI
- 单实例采集 Worker 与调度器
- Playwright Chromium
- Xvfb 虚拟显示
- x11vnc
- noVNC/websockify

选择原因：

- 与当前 Web/API 和 Worker 同进程的结构一致，不需要先拆分 Worker。
- 浏览器与 x11vnc 位于同一容器和同一虚拟显示，登录时可立即通过 noVNC 操作。
- 只有一套应用生命周期和持久卷，适合单管理员、单服务器首版。
- 比通过共享 X11 socket 串联多个容器更少故障点。

代价：

- 镜像体积较大，包含 Python、Chromium 和桌面工具。
- 重启应用会同时重启 API、Worker 和浏览器。
- 不适用于横向扩展；后续拆分 Worker 时必须重新设计显示和作业领取边界。

### 4.2 未采用方案

- 浏览器独立 sidecar：安全边界更细，但需要共享 X11 socket、协调启动顺序和两套健康检查，首版复杂度不划算。
- 主机原生启动所有进程：调试直接，但依赖服务器现场配置，升级和回滚不可重复。
- 本地浏览器 CDP 隧道：依赖管理员电脑长期在线，不适合无人值守云服务。

## 5. 运行拓扑

```text
管理员设备
    |
    | Tailscale 加密私有网络
    v
云主机 Tailscale Serve (HTTPS)
    |-- https://<tailnet-host>/       -> 127.0.0.1:8080  工作台/API
    `-- https://<tailnet-host>:8443/  -> 127.0.0.1:6080  noVNC
                                                     |
                                              Docker 私有网络
                                      +--------------+--------------+
                                      |                             |
                                 app 容器                       postgres 容器
                         FastAPI + Worker + Chromium          PostgreSQL 18
                         Xvfb + x11vnc + noVNC              无宿主机端口
                                      |
                            browser_data / project_data 持久卷
```

所有 Docker 端口只发布到云主机的 `127.0.0.1`。Tailscale Serve 负责私有 HTTPS；不部署 Caddy 或公网反向代理。

## 6. 容器设计

### 6.1 应用镜像

使用多阶段构建：

1. Node 阶段执行 `npm ci` 和前端生产构建。
2. Python/Playwright 阶段从锁文件同步 Python 依赖。
3. 最终镜像安装 Xvfb、x11vnc、noVNC、websockify 和运行时工具。
4. 应用以非 root 用户运行，工作目录固定为 `/app`。
5. 浏览器可执行文件使用镜像内 Playwright Chromium，不依赖宿主机 Chrome。

最终镜像包含：

- `/app` 应用源码和构建后的 `api/webui/`
- `/app/browser_data` 浏览器资料卷挂载点
- `/app/data` 采集暂存、恢复目录和运行文件卷挂载点
- `/app/deploy/container-entrypoint.sh` 容器启动入口

### 6.2 启动顺序

容器入口按以下顺序执行：

1. 校验必需环境变量和禁止使用的占位值。
2. 启动 Xvfb `:99` 并等待显示可用。
3. 使用 `NOVNC_PASSWORD` 生成 x11vnc 临时密码文件。
4. 启动 x11vnc，仅监听容器内 `127.0.0.1:5900`。
5. 启动 websockify/noVNC，监听容器内 `0.0.0.0:6080`。
6. 执行 `alembic upgrade head`，失败则容器退出。
7. 启动单个 Uvicorn 进程，使用可信代理头并监听容器内 `0.0.0.0:8080`。

入口脚本使用 `wait -n` 监视 Xvfb、x11vnc、websockify 和 Uvicorn。任一关键子进程退出时，入口脚本终止其余子进程并以非零状态退出容器，再由 Compose 重启，不能继续提供半可用服务。

## 7. Compose 服务

生产 Compose 仅包含：

- `app`：一个副本，依赖 PostgreSQL 健康，发布 `127.0.0.1:8080` 和 `127.0.0.1:6080`。
- `postgres`：PostgreSQL 18，不发布宿主机端口，只连接内部网络。

约束：

- `app` 使用 `init: true`、健康检查、`restart: unless-stopped` 和足够的共享内存。
- `app` 暴露 `/health/live` 与 `/health/ready`；Docker 健康检查使用 ready 探针。
- PostgreSQL 健康检查使用 `pg_isready`。
- 只允许一个 `app` 副本；部署脚本检测意外扩容。
- 容器日志使用 JSON 文件驱动并限制轮转大小和份数。
- 应用和数据库不共享数据卷。

## 8. 持久化

使用 Docker 命名卷：

- `collector_postgres_data`：挂载到 PostgreSQL 数据目录。
- `collector_browser_data`：挂载到 `/app/browser_data`，保存平台登录态和浏览器资料。
- `collector_project_data`：挂载到 `/app/data`，保存运行暂存和恢复数据。

镜像创建上述应用目录并赋予运行用户写权限，保证新命名卷首次挂载后权限正确。禁止将浏览器资料或数据库目录写入源码目录并随后通过 Git 提交。

## 9. 配置与秘密

生产配置放在服务器上的 `deploy/.env.production`，权限 `600`，由 Compose `env_file` 注入，禁止写入镜像或提交 Git。

应用必备配置：

- `POSTGRES_DB_NAME`
- `POSTGRES_DB_USER`
- `POSTGRES_DB_PWD`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `SESSION_COOKIE_SECURE=true`
- `NOVNC_PASSWORD`

可选 AI 配置：

- `AI_FILTER_API_BASE_URL`
- `AI_FILTER_API_KEY`
- `AI_FILTER_MODEL`

应用容器内部覆盖数据库主机为 `postgres`、端口为 `5432`，不沿用开发机的 `localhost:5433`。

部署脚本拒绝以下配置：

- `ADMIN_PASSWORD` 少于 16 个字符或以示例占位文字开头。
- `POSTGRES_DB_PWD` 为空或使用示例占位值。
- `NOVNC_PASSWORD` 为空或少于 12 个字符。
- 生产环境 `SESSION_COOKIE_SECURE=false`。
- `ENABLE_CDP_MODE=true`。

AI 的三个配置必须同时为空或同时填写。全部为空时允许启动，但前端明确显示 AI 未配置；只填写一部分时部署脚本拒绝使用该配置，不把空值伪装成可用。

## 10. 网络与安全

- 云安全组只允许受限来源的 SSH；不开放 80、443、8080、5433、5900、6080、9222。
- 主机防火墙允许 Tailscale 接口，禁止 Docker 改写公网端口规则暴露内部服务。
- `tailscale serve` 只代理到 `127.0.0.1`。
- Tailscale 必须启用 MagicDNS 和 HTTPS 证书能力；管理员设备必须已登录同一 tailnet，且只向管理员设备分享节点。
- PostgreSQL 只位于 Compose 内部网络。
- noVNC 还必须输入 x11vnc 密码；Tailscale 成员资格不是唯一控制。
- 不启用 CDP；浏览器调试端口不产生。
- 应用 Cookie 使用 `Secure`、`HttpOnly`、`SameSite=Lax`。
- API 文档继续关闭，健康探针不包含秘密。
- 所有生产秘密不得出现在日志、Compose 展开输出、部署记录或截图。

## 11. 部署脚本

新增 `deploy/` 目录并提供：

- `prepare.sh`：检查 Ubuntu、Docker Compose、Tailscale、磁盘空间和配置权限；不自动安装系统软件。
- `deploy.sh`：校验配置、构建镜像、启动 PostgreSQL、执行迁移、启动应用、等待健康检查并检查服务副本数量。
- `status.sh`：显示 Compose 状态、健康结果和 Tailscale 暴露摘要，不输出秘密值。
- `logs.sh`：输出应用或数据库最近日志。
- `backup.sh`：创建数据库、浏览器资料和项目数据加密备份。
- `restore.sh`：执行显式确认后停止应用、恢复指定备份并重新验证健康。
- `upgrade.sh`：备份后拉取指定提交、重建并健康检查；失败时输出回滚命令。

部署脚本使用 `set -euo pipefail`，所有路径相对于脚本位置解析，可从任意当前目录执行。

## 12. 迁移与升级

- 首次部署前执行 `alembic upgrade head`，并确认 `alembic current` 与 `alembic heads` 一致。
- 应用启动时仍保留现有自动迁移作为兜底。
- 升级顺序：配置检查、加密备份、拉取指定 commit、构建新镜像、迁移、替换应用、健康检查。
- 升级失败时保留旧镜像标识；需要回滚数据库时不兼容的迁移先恢复备份。
- 不使用浮动 `latest` 作为生产追溯依据；镜像标记包含 Git commit。

## 13. 备份与恢复

`backup.sh` 生成一组带 UTC 时间戳的文件：

- PostgreSQL 逻辑备份。
- 浏览器资料归档。
- 项目数据归档。
- 元数据文件，包含 Git commit、Alembic 版本和文件校验和，不包含秘密。

数据库流使用 `pg_dump`，三个产物使用 AES-256 加密并通过 `BACKUP_PASSPHRASE_FILE` 读取口令。备份默认写入 `deploy/backups/`，目录权限 `700`，文件权限 `600`，且加入 `.gitignore`。

`restore.sh` 要求显式 `--confirm`，验证校验和、停止应用、恢复数据库和两个卷、执行迁移并检查健康。恢复期间禁止启动 Worker。备份和恢复测试使用合成数据，不读取真实平台账号内容。

备份口令通过服务器上的 `BACKUP_PASSPHRASE_FILE` 路径读取，口令文件权限必须为 `600`，不得与备份放在同一目录，也不进入 Compose 配置或镜像。缺少口令文件时 `backup.sh` 在创建任何备份前失败。

## 14. 测试与验收

### 14.1 静态配置测试

- 生产 Compose 中 PostgreSQL 没有任何宿主机端口。
- 应用端口和 noVNC 端口只绑定 `127.0.0.1`。
- 不存在 9222 发布、公开 80/443、公开数据库或根目录挂载。
- 只定义一个应用副本、一个数据库服务和一个内部网络。
- 必需环境变量、健康检查、日志轮转和持久卷存在。
- Shell 脚本通过 `bash -n`，部署配置不含示例秘密。

### 14.2 镜像与容器集成测试

- 前端和 Python 依赖从锁文件可重复安装。
- 镜像可构建，应用以非 root 用户运行。
- 容器启动后 Xvfb、x11vnc、noVNC、PostgreSQL 和应用均健康。
- `/health/ready` 成功，登录、CSRF、任务列表和退出登录可用。
- noVNC 页面和 VNC 密码认证可用。
- 容器重启后数据库记录、浏览器资料和项目数据仍存在。

### 14.3 备份恢复测试

- 创建合成任务或数据库标记记录。
- 执行加密备份并验证输出不含明文凭据。
- 在隔离 Compose 项目名和隔离卷中恢复。
- 恢复后记录数量、迁移版本和健康检查一致。

### 14.4 云端验收

- 在 Ubuntu 24.04 主机安装 Docker 和 Tailscale。
- 从非 Tailscale 公网确认所有应用端口不可访问。
- 从已登录 Tailscale 的管理员设备访问 HTTPS 工作台和 noVNC。
- 在云端完成一次抖音扫码登录和小范围采集。
- 重启服务器后验证服务自动恢复、登录资料保留和任务状态正确。

## 15. 交付物

- `deploy/compose.prod.yml`
- `deploy/Dockerfile`
- `.dockerignore`
- `deploy/container-entrypoint.sh`
- `deploy/.env.production.example`
- `deploy/prepare.sh`
- `deploy/deploy.sh`
- `deploy/status.sh`
- `deploy/logs.sh`
- `deploy/backup.sh`
- `deploy/restore.sh`
- `deploy/upgrade.sh`
- 生产部署运维文档
- 配置、脚本、镜像和备份恢复测试

## 16. 风险

- 云端 IP 和全新浏览器环境可能触发平台额外验证；只能由管理员人工处理，不能绕过。
- 两个平台浏览器并行时内存占用较高；首版服务器建议 4 核 8 GB，并在真实验收中记录峰值。
- noVNC 暴露的是完整浏览器控制能力，必须保持 Tailscale 私有并设置 VNC 密码。
- 当前没有持久化服务日志；本方案只保证容器日志轮转，系统日志管理页仍属于后续功能。
- 当前没有 Cookie 导入功能；登录依赖云端虚拟桌面扫码，这是本方案的明确约束。
