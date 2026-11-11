# 抖音与小红书评论采集工作台

用于个人学习和非商业研究的本地评论采集管理工具。支持管理小范围采集任务、筛选公开评论、查看运行记录，并导出 CSV 或 Excel。

## MVP 能力

- 抖音与小红书：按关键词搜索，或输入指定笔记/视频链接。
- 手动执行、固定间隔和 Cron 定时；支持暂停、恢复和查看运行记录。
- 按包含词和排除词筛选评论。
- 新增任务可用 AI Agent 把自然语言转成语义规则，预览并确认后才生效。
- 评论主记录去重，并保存每次运行的观察快照。
- 作者仅保存平台用户 ID、昵称和主页链接。
- 本地网页中搜索评论，并导出 CSV/XLSX。
- PostgreSQL 持久化，Docker Compose 本地启动；使用 Alembic 管理项目表。

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
- 真实平台端到端验收、平台账号管理向导、云端 HTTPS 与公网安全加固尚未完成。不要将当前本地 MVP 直接暴露到公网。
- 开启 AI 语义筛选后，通过关键词预筛的评论文本会发送给配置的云模型；作者 ID、昵称、主页链接和平台会话不会发送。规则需先人工确认，模型调用失败的评论不会入库。详见 [AI 语义筛选设计](docs/architecture/ai-filter-rules.md)。

## 文档

- [项目范围与当前状态](docs/project-overview.md)
- [架构决策与路线图](docs/architecture/decisions.md)、[实施路线图](docs/architecture/roadmap.md)
- [API 契约](docs/api/openapi.yaml)
- [开发规范](docs/development/standards.md)
- [部署说明](docs/deployment/cloud-deployment.md)
- [安全威胁模型](docs/security/threat-model.md)
- [测试与验收计划](docs/testing/test-and-acceptance-plan.md)

## 开发验证

    uv run --env-file .env pytest tests/test_collection_limits.py tests/test_collection_pipeline.py tests/test_project_config_security.py tests/test_task_contracts.py -q
    Push-Location webui
    npm ci
    npm run build
    Pop-Location
