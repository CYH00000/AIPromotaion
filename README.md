# 抖音与小红书评论采集工作台

用于个人学习和非商业研究的本地评论采集管理工具。支持管理小范围采集任务、筛选公开评论、查看运行记录，并导出 CSV 或 Excel。

## MVP 能力

- 抖音与小红书：按关键词搜索，或输入指定笔记/视频链接；关键词任务可选择综合/最新/最多点赞排序，并限制一天、一周或半年内的内容。
- 手动执行、固定间隔和 Cron 定时；支持暂停、恢复、查看最近运行和运行详情。
- 平台账号管理：抖音/小红书扫码登录、配置状态查看和解绑；登录态保存在本机浏览器配置目录。
- 运行观测：查看当前阶段、暂存内容/评论数、最近活动时间、最近日志，并可停止运行。
- 按平台并行：抖音和小红书各有一个独立运行时，同平台任务严格按顺序执行，不同平台可同时采集；登录、取消、日志和账号解绑互不阻塞。
- 按包含词和排除词筛选评论。
- 新增任务可用智能助手把自然语言转成语义规则，预览并确认后才生效；模型调用支持超时重试和批次失败隔离。
- 评论主记录去重，并保存每次运行的观察快照。
- 作者仅保存平台用户 ID、昵称和主页链接。
- 本地网页中搜索评论，并导出 CSV/XLSX。
- 管理页面与运行状态全部使用中文。
- PostgreSQL 持久化，Docker Compose 本地启动；使用 Alembic 管理项目表。
- Ubuntu 24.04 单机私有云部署包：私有 PostgreSQL、Playwright/Xvfb/noVNC 单容器运行时、Tailscale Serve HTTPS、加密备份与显式恢复。

## 本机启动

### 环境要求

- Windows PowerShell
- Docker Desktop
- Python 3.12
- Node.js 22
- uv

### 配置

    Copy-Item .env.example .env

在 .env 中设置 PostgreSQL 密码和 ADMIN_PASSWORD。管理员密码至少 16 个字符，不要提交 .env。启用 AI 筛选时，还需配置 `AI_FILTER_API_BASE_URL`、`AI_FILTER_API_KEY` 和 `AI_FILTER_MODEL`；密钥只保存在服务端 `.env`。

### 启动

    .\scripts\start-local.ps1

首次启动会准备 PostgreSQL、同步 Python 依赖、执行数据库迁移并构建网页。启动后访问：

    http://127.0.0.1:8080

管理员用户名由 ADMIN_USERNAME 配置，密码由 ADMIN_PASSWORD 配置。

## 使用边界

- 仅限个人学习和非商业研究。采集核心和 WebUI 各自适用的许可证见 [许可证与来源清单](LICENSES.md)、根目录 LICENSE 和 webui/LICENSE。
- 采集使用已授权的平台登录态。遇到验证或限流时应停止任务并人工处理；系统不绕过验证码、限流或访问控制。
- 目前尚未完成真实平台端到端验收。小红书指定链接模式尤其需要在授权账号下验证。
- 私有云部署包已完成本地容器验收，但尚未在真实云服务器完成 tailnet、公网端口关闭和真实平台任务验收。真实域名当前保留不用；不要把回环端口直接改成公网监听。
- 账号管理目前只支持扫码登录、状态查看和解绑；不支持粘贴 Cookie、把二维码内嵌到网页或多账号管理。
- 本地默认使用标准 Playwright 持久浏览器配置；如需连接已有浏览器，必须先在 9222 端口启用远程调试。
- 开启 AI 语义筛选后，通过关键词预筛的评论文本会发送给配置的云模型；作者 ID、昵称、主页链接和平台会话不会发送。规则需先人工确认，模型调用失败的评论不会入库。详见 [AI 语义筛选设计](docs/architecture/ai-filter-rules.md)。

## 私有云部署

首版目标环境是 Ubuntu 24.04 + Docker Compose + Tailscale。生产配置、容器构建、私有服务入口、备份、恢复和升级脚本均在 `deploy/` 下。完整中文步骤、安全组设置、noVNC 扫码和上线门禁见 [云部署与运维说明](docs/deployment/cloud-deployment.md)。

云服务器不需要开放 8080、6080、5432 或 9222；只有管理员可访问的 SSH，以及 Tailscale 私有 HTTPS 入口。真实服务器地址和 SSH 权限确认前，不执行远程部署。

## 文档

- [项目范围与当前状态](docs/project-overview.md)
- [架构决策与路线图](docs/architecture/decisions.md)、[实施路线图](docs/architecture/roadmap.md)
- [后续计划与未实现能力](docs/architecture/backlog.md)
- [API 契约](docs/api/openapi.yaml)
- [开发规范](docs/development/standards.md)
- [部署说明](docs/deployment/cloud-deployment.md)
- [安全威胁模型](docs/security/threat-model.md)
- [测试与验收计划](docs/testing/test-and-acceptance-plan.md)

## 开发验证

    uv run --env-file .env pytest tests -q
    Push-Location webui
    npm ci
    npm run lint
    npm run build
    Pop-Location
