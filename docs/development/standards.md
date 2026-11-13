# 开发规范

## 1. 源码与许可证

- 平台采集能力必须来自固定的 MediaCrawler 上游版本，不从零重写平台客户端。
- 保留上游文件版权头、根目录非商业学习许可证和 WebUI GPL-3.0 许可证；新增代码不能覆盖或删除来源标记。
- 采集 Worker 只持久化已批准的数据字段。禁止在日志中写 Cookie、Token、完整请求头、模型 Key 或额外作者资料。
- 限定个人学习/非商业研究和小范围访问。不得绕过验证、限流、登录控制或平台访问限制。

## 2. Git 工作流

- 上游基线固定为 SHA 68d9ef1c1da22eab75940dfd7cec259907006538。
- 单维护者阶段使用受保护的 main 和短期功能分支；分支命名 codex/<scope>，例如 codex/comment-snapshots。团队/CI 扩大后再评估是否引入 develop/release 分支，不为流程而增加长期分支。
- 一个提交聚焦一个可审查改动；使用 Conventional Commits：feat、fix、docs、test、refactor、chore。
- 每个功能先写失败测试，再实现最小改动，再运行目标测试与全量必要检查。
- 不直接改写上游提交；采用可追踪的增量提交，保留上游 remote。
- 远程仓库可用后，变更经 Pull Request、CI 和至少一位审查者批准后合并；不直接推送 main。没有远程仓库配置时只做本地提交，不擅自推送或创建 PR。

## 3. 设计与契约门禁

- 每个功能必须按“功能设计 → 用户确认 → 接口与数据库设计 → 用户确认 → 实施计划 → 编码与测试 → 审查与发布”的顺序推进，不得从已确认的功能设计直接跳到编码。
- 功能设计确认后，先完成接口契约、数据模型、数据库迁移与校验设计；接口和数据库设计未获用户确认前，不得新增业务接口、执行数据库迁移或编写实现代码。
- 接口设计至少包含：受影响端点、请求/响应模型、字段类型与必填性、认证与权限、分页与筛选、错误码与中文错误提示、幂等与并发行为、兼容性影响和 OpenAPI 示例。
- 数据库设计至少包含：实体关系、表与字段数据字典、长度与精度、可空性、默认值、唯一/外键/检查约束、索引及查询依据、事务边界、数据保留与敏感级别、升级/回滚步骤和迁移测试方案。
- 设计变更必须回到对应门禁重新评审；实现、OpenAPI、数据字典和迁移脚本必须使用同一组术语和语义。
- 接口以项目现有 OpenAPI 3.1 契约和 HTTP 语义为不破坏基线，参考阿里云 OpenAPI 风格的资源化路径、稳定状态码、统一错误信息和向后兼容原则。
- 数据库及编码参考阿里云 P3C 的通用工程原则，并结合本项目 Python/FastAPI/PostgreSQL 技术栈适配：snake_case 字段、显式可空性、UTC 时间、受限长度、明确约束和索引、Alembic 可审查迁移。
- 与外部规范冲突时，以项目已批准的设计、现有兼容边界和安全要求为准，并在设计中记录偏离原因，不能静默改变既有契约。

## 4. 代码边界

- 继续采用上游 Python/FastAPI API 与 React/Vite WebUI；优先扩展已有 routers、schemas、services 和组件。
- 新增业务服务按单一职责拆分；API 只做验证和编排，数据库访问集中在存储/仓储模块，采集运行由 Worker 执行。
- 数据库字段 snake_case；Python 类型/类 PascalCase，函数与变量 snake_case；React 组件 PascalCase，函数 camelCase。
- 所有请求/响应都使用显式 Pydantic 模型和 OpenAPI 文档；不得返回 ORM 对象或原始上游 JSON。
- 异常必须映射到稳定错误码；关键路径不得吞异常。
- 作者白名单仅包含 platform_user_id、nickname、profile_url。链接在持久化前清理临时查询令牌。

## 5. Python 与前端质量

- Python 最低版本跟随上游 pyproject.toml：3.11；依赖锁使用上游 uv.lock 为起点。
- Python 文件头按上游 tools/file_header_manager.py 要求添加并通过检查。
- Python 验证使用 pytest/pytest-asyncio，数据库集成测试使用独立 Postgres 测试库。
- 前端沿用上游 package-lock.json；提交前执行 npm run lint 和 npm run build。
- Python 先执行目标 pytest；提交前执行完整项目测试命令及 pre-commit run --all-files。
- 未经用户明确要求，不在 CI 或后台自动触发真实平台采集。
- 远程 CI 可用后按依赖安装、lint/type check、单元/集成测试、构建、安全扫描的顺序执行；所有自动化平台/模型测试使用 fixture 和 mock。
- CHANGELOG 使用 Keep a Changelog；API、数据模型、部署边界变更要同步更新对应文档和 GitHub PR 模板中的审查项。

## 6. 数据与秘密

- 所有时间戳以 UTC 存储，UI 以 Asia/Shanghai 显示。
- 评论主记录唯一键为 (platform, external_comment_id)；每次运行的快照唯一键为 (comment_id, task_run_id)。
- 登录 Cookie、浏览器配置、模型 Key 通过服务端秘密配置持有；前端只看到是否已配置和非敏感模型名/地址。
- 测试使用合成数据或脱敏 JSONL fixture。禁止将真实评论、Cookie 或账号数据提交到 Git。
- 模型输出只允许符合 FilterRule DSL 的 JSON；不执行 SQL、代码、工具调用或模型指定 URL。

## 7. 代码审查清单

- 与已批准的功能设计、接口契约、数据库设计和实施计划一致；缺少任一确认门禁时不得合并。
- 变更只影响声明的模块；数据库变化含迁移及回滚说明。
- 去重、快照、任务恢复和权限边界有测试。
- 用户字段符合最小化策略；日志和错误响应无秘密。
- 上游版权/许可证未丢失；新增依赖的许可证已登记。
- Python/前端检查通过，文档、API 与实现一致。
