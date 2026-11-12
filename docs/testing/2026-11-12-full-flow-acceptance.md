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

## 部署结论

本地功能、数据库、页面和抖音真实采集链路已通过本轮验收，但仍不能据此认定云端生产就绪：

- 仓库没有生产 Compose、HTTPS 反向代理和完整秘密注入部署包。
- 云端浏览器必须运行在云服务器；现有 CDP 连接固定为 Worker 主机的 `localhost`。
- 云端扫码登录需要 VNC/noVNC、Cookie 导入或受控隧道之一，当前 UI 尚未提供云端浏览器画面或 Cookie 粘贴。
- 9222 调试端口不得暴露公网，浏览器资料必须使用持久卷并限制访问权限。
- 正式部署前仍需完成 HTTPS、防火墙、备份恢复、云端登录和公网访问验收。
