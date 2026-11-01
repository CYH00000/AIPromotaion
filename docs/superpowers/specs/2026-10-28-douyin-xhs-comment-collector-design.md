# 抖音与小红书评论采集管理系统设计规格

- 日期：2026-10-28
- 状态：已确认；实现计划与工程文档已补齐
- 项目目录：D:\codex_project
- 当前阶段：上游基线已导入；项目专属功能尚未实现

## 1. 目标与范围

建设一个本地开发、后续可部署到单台云服务器的个人学习/非商业研究工具。系统支持通过关键词或指定内容链接创建抖音、小红书评论采集任务，按用户配置的规则筛选评论，并提供任务管理、评论检索和 CSV/Excel 导出。

系统基于 NanmiCoder/MediaCrawler 上游二次开发，复用其双平台采集器、FastAPI 接口和 React/Vite WebUI。新增功能集中在任务调度、评论与快照存储、筛选规则、单管理员登录、查询导出和云部署边界。平台采集逻辑不从零重写。

首期范围：

- 平台：抖音、小红书；每个平台一个用户授权账号。
- 任务来源：关键词搜索，或指定笔记/视频链接；一个任务选择一个平台和一种来源模式。关键词任务可包含多个关键词，链接任务可包含多个链接。
- 调度：手动立即运行、自定义固定间隔、Cron 日历时间；时区为 Asia/Shanghai。
- 数量控制：每任务配置内容数与每条内容的评论数上限，服务端同时设置硬上限，避免无界采集。
- 筛选：包含/排除关键词与 AI 语义筛选均可启用；AI 将自然语言条件转换为规则草稿，用户预览后批准才生效。
- 评论数据：平台、内容标题与链接、评论内容与时间、点赞数、回复数、作者字段、命中规则、采集时间。
- 作者字段：仅平台用户 ID、昵称、主页链接；主页补充默认只针对命中评论的作者。
- 去重与历史：评论主记录按平台评论 ID 去重；每次运行均记录观察快照，保存点赞数、回复数和作者三字段的变化。
- 管理：本地网页界面支持查看、搜索、任务管理、CSV/Excel 导出。
- 部署：本机开发与验证；本地/云端统一 PostgreSQL；云端公网访问通过单管理员账号密码及 HTTPS。

非目标：商业获客、规模化采集、自动联系用户、评论/内容发布、自动绕过验证或访问限制、多租户、公共注册、横向多 Worker 扩容。首期只按 MediaCrawler 默认一级评论采集；保存一级评论回复数，不展开二级评论正文。

## 2. GitHub 项目评估与复用决策

### 2.1 候选项目

| 项目 | 源码评估 | 结论 |
|---|---|---|
| NanmiCoder/MediaCrawler | 检查时约 68.8k Stars、13.1k Forks；支持抖音/小红书及搜索、详情、创作者模式；已包含 FastAPI API、React/Vite WebUI 和导出能力。当前未发现内建计划任务调度。 | 选为平台采集内核与 WebUI/API 底座。 |
| njueeRay/MediaCrawler | 有 WebUI、API 和 APScheduler，支持间隔、Cron、一次性及手动触发；检查时约 8 Stars、2 Forks；其 README 标出 AI 数据清洗、容器部署仍在开发。 | 只参考其任务恢复和调度流程，不作为正式代码底座。 |
| hyperMoss/geiwokehu | 有关键词工作台、评论查看和 AI 分析；仅 1 Star、2 次提交；面向本机单用户；上游作者标识仍匿名；GitHub API 未检测到仓库级许可证声明。 | 仅作为产品思路参考，不复制未明确授权的仓库代码。 |
| Aswellle/WeMediaCrawler | 有现代 WebUI、详情输入和上游同步记录，但检查时约 4 Stars、0 Forks，无调度器；核心仍沿用 MediaCrawler 非商业学习许可证。 | 作为 WebUI/同步模式补充参考，不替代上游底座。 |

### 2.2 选择的上游与版本基线

- 仓库：https://github.com/NanmiCoder/MediaCrawler
- 评估时 HEAD：68d9ef1c1da22eab75940dfd7cec259907006538，2026-10-27。
- Python：上游声明 Python 3.11 或更高版本。
- API：上游当前固定 FastAPI 0.110.2；公网部署前要做依赖兼容与安全审查，并固定通过验证的版本。
- WebUI：上游 package-lock.json 作为依赖锁定起点；package.json 使用 React 18.3.1、Vite 6 系列和 TypeScript 5.6 系列。
- 数据库：PostgreSQL 18 系列稳定版本，本地与云端使用同一主要版本；本规格按 18.6 记录。
- 调度：APScheduler 3.11 系列；单实例 Worker。应用数据库中的任务记录是任务配置来源，Worker 启动时从数据库恢复启用任务。

### 2.3 作者字段的源码差距

当前 MediaCrawler 上游对作者 ID 做匿名哈希、对昵称脱敏，且当前创作者保存实现不落库。这与用户确认的作者字段不一致。二开时需在采集数据进入匿名/脱敏存储前增加项目专用持久化适配，只保留命中评论作者的：平台用户 ID、昵称、主页链接。不得把头像、签名、IP 属地、粉丝量或其他字段额外写入项目数据库或应用日志。主页链接无法从采集结果或受支持的创作者查询取得时记录为空并提示，不猜造链接。

### 2.4 许可证边界

- MediaCrawler 采集核心：NON-COMMERCIAL LEARNING LICENSE 1.1，仅限非商业学习研究，禁止大规模采集及造成平台干扰；保留版权与许可证声明。
- 上游 WebUI：GPL-3.0，保留其许可证和来源声明。
- 当前个人学习/非商业研究定位按上述限制执行。若未来用途改变，需先重新核对授权；商业使用需取得权利人书面许可。

## 3. 总体架构

### 3.1 架构图

浏览器
  └─ HTTPS + 单管理员登录
      └─ 反向代理
          └─ React/Vite WebUI + FastAPI API
              ├─ PostgreSQL：任务、执行、内容、评论、快照、规则和命中记录
              ├─ 单实例采集 Worker：调度、串行队列、MediaCrawler 子进程
              │   └─ MediaCrawler → 抖音 / 小红书
              └─ 配置的云端模型 API：规则转译和语义判定

浏览器不直接访问数据库、采集 Worker 或平台接口。API 与 Worker 通过 PostgreSQL 任务与结果记录协作。只有反向代理的 HTTPS 端口对公网开放。

### 3.2 本地与云端拓扑

本地开发：Docker Compose 启动 PostgreSQL；前端、API 和 Worker 使用上游代码与锁文件进行本机开发，或以 Compose 服务运行。云端使用同样的应用服务边界，通过环境配置连接 PostgreSQL。Docker CLI 已在开发机可用。

云端单机服务：

- reverse-proxy：TLS 终止，只公开 HTTPS。
- web-api：React/Vite 静态资源和 FastAPI，同源访问。
- crawler-worker：持有平台登录态的单实例调度与采集进程。
- PostgreSQL：仅服务器私网可访问，数据目录持久化。
- 浏览器登录资料：持久化私有卷，只挂载给 Worker。

首期采用单服务器、单调度器、单 Worker，不部署多副本。需要扩容时再设计分布式任务租约/领导者选举，避免同一计划被重复执行。

## 4. 核心工作流

### 4.1 创建和执行采集任务

1. 管理员登录，选择平台和来源模式。
2. 关键词模式录入一个或多个关键词；链接模式录入平台支持的笔记/视频链接或 ID。
3. 配置每次运行的采集上限、手动/间隔/Cron 调度和已批准的筛选规则版本。
4. API 验证输入，写入 collection_tasks；手动运行或调度触发时生成 task_runs 记录并进入全局串行队列。
5. Worker 调用 MediaCrawler；将内容和评论按平台 ID 幂等去重写入数据库。
6. 关键词规则优先判定；若任务配置了 AI 规则，则仅对通过关键词阶段的评论进行语义判定。
7. 对命中评论的作者补充平台用户 ID、昵称和主页链接；其他作者资料不补充。每次任务运行写入评论快照。
8. UI 展示结果、命中规则、运行日志摘要和每次运行的变化；用户可检索并导出 CSV/Excel。

### 4.2 AI 规则生成与启用

1. 用户输入自然语言筛选描述。
2. 配置的云端模型 API 将描述转为受限 JSON 规则草稿。
3. 服务端按 JSON Schema 校验并生成预览；预览包含生成条件、样例评论和匹配理由。
4. 用户明确批准后生成不可变规则版本；任务只引用已批准版本。
5. 模型判定仅处理通过关键词过滤的评论；关键词与语义规则同时配置时采用 AND 关系。未设置包含词时不增加包含词限制，排除词命中始终淘汰。
6. 模型错误时保留评论记录，语义状态标记为待处理/失败；用户可手动重试，不静默当作命中。

评论文本发送到用户选择的云端模型服务；作者用户 ID、昵称和主页链接不发送给模型。模型返回值不能执行为 SQL、代码或网络工具调用。

## 5. 数据模型

| 表 | 关键字段/约束 | 说明 |
|---|---|---|
| platform_accounts | id、platform、login_method、status、secret_ref | 每平台最多一个账号；凭据/浏览器配置只由服务端访问。 |
| collection_tasks | id、platform、source_mode、keywords/url_list、limits、schedule_type/config、enabled、approved_rule_version_id | 一个任务对应一个平台和一种输入模式。 |
| task_runs | id、task_id、trigger_type、status、started_at、finished_at、counts、error_code、error_summary | 手动与计划执行均留下运行记录。 |
| contents | platform、external_content_id、title、url、first_seen_at | UNIQUE(platform, external_content_id)。 |
| authors | platform、platform_user_id、nickname、profile_url、updated_at | 只保存用户确认的三个作者字段；UNIQUE(platform, platform_user_id)。 |
| comments | platform、external_comment_id、content_id、author_id nullable、body、comment_time、matched_state | UNIQUE(platform, external_comment_id)。采集记录可保留，作者字段只对命中评论补充。 |
| comment_snapshots | comment_id、task_run_id、like_count、reply_count、author_id/nickname/profile_url、observed_at | 每次采集观察写一行；UNIQUE(comment_id, task_run_id)。 |
| filter_rule_versions | id、natural_language、rule_json、model/provider、status、created_at、approved_at | 草稿与批准版分开；批准后不可原位改写。 |
| comment_rule_matches | comment_id、rule_version_id、matched、reason、evaluated_at | 支持评论列表展示命中规则和判定依据。 |

评论 ID 和内容 ID 使用平台 ID；空 ID 的记录不进入去重主表并在运行统计中计为无效记录。数据库迁移使用 Alembic；时间戳统一存 UTC，页面按 Asia/Shanghai 显示。

## 6. API 契约范围

所有业务 API 除登录/健康探针外要求已认证会话；返回分页、排序和统一错误结构。详细 OpenAPI 契约见 `docs/api/openapi.yaml`；实现阶段如需变更接口，须同步更新契约与本规格。

| 方法/路径 | 用途 |
|---|---|
| POST /api/auth/login | 管理员登录并创建安全会话。 |
| POST /api/auth/logout | 注销会话。 |
| GET /api/auth/me | 返回当前会话状态，不返回密码或密钥。 |
| GET /api/accounts | 平台账号状态。 |
| POST /api/accounts/{platform}/login | 启动 MediaCrawler 支持的授权流程并读取状态。 |
| GET/POST /api/tasks | 任务列表与创建。 |
| GET/PATCH/DELETE /api/tasks/{id} | 任务详情、配置更新与停用/删除计划。删除任务不级联删除已采集评论。 |
| POST /api/tasks/{id}/run | 手动加入执行队列。 |
| POST /api/tasks/{id}/pause 或 resume | 暂停/恢复未来计划触发。 |
| POST /api/runs/{id}/cancel | 请求取消当前执行。 |
| GET /api/runs | 搜索运行记录。 |
| GET /api/comments | 按平台、任务、时间、文本、作者和规则命中状态分页检索。 |
| GET /api/comments/{id}/snapshots | 查看该评论历次快照。 |
| POST /api/filter-rules/drafts | 由 AI 生成规则草稿。 |
| POST /api/filter-rules/{id}/preview | 生成规则预览。 |
| POST /api/filter-rules/{id}/approve | 用户批准并固化规则版本。 |
| GET /api/exports/comments?format=csv 或 xlsx | 按当前筛选条件导出。 |

## 7. 调度、并发与错误策略

- 计划类型：manual-only、interval、cron；支持任务手动立即执行。
- interval 使用正整数分钟/小时；初始最小间隔为 60 分钟，可按平台配置提高；只有经人工小范围验证后才可调整下限。Cron 按 Asia/Shanghai 解析。
- 所有平台任务进入全局串行队列，避免账号并发和资源尖峰；平台间也先串行运行。
- 同一任务运行中再次到期时最多保留一个待执行项；服务中断期间的多个过期触发合并为一次，不补发洪峰。
- 启动时从 PostgreSQL 恢复已启用计划；将上次运行中状态的 task_runs 标记为 interrupted，保留已写入结果。
- 网络临时错误有限重试；登录失效、验证挑战、限流、账号限制、平台拒绝访问不自动重试、不自动切换代理或尝试绕过。
- 部分成功保留已采集结果并明确标记 partial；取消通过协作停止信号进行；手动重试创建新 task_run。
- 日志记录任务 ID、状态、计数和脱敏错误码；不记录 Cookie、Token、完整请求头、模型 Key 或不必要的作者数据。

## 8. 安全与隐私

- 单管理员账号，无公开注册；初始密码使用安全方式设置，数据库仅保存 Argon2id 哈希。
- 会话 Cookie 使用 Secure、HttpOnly、SameSite；对状态变更请求实施 CSRF 防护；登录接口限速。
- 生产环境同源部署，限制 CORS；FastAPI 文档页需登录保护或生产关闭。
- Cookie、会话资料和 AI Key 只由服务端持有，密钥通过环境变量/秘密管理器注入；敏感存储加密且 API 不回显。
- 反向代理只公开 HTTPS；数据库、Worker、内部 API 和浏览器调试端口不对公网监听。
- 模型 Base URL 限制 HTTPS；解析 DNS 并阻止 loopback、私有网段和云元数据 IP，禁用跳转到受限地址，降低 SSRF 风险。
- 所有来自评论和平台响应的数据视为不可信输入；前端按文本转义显示，模型输出以严格结构校验。
- 作者仅保存 platform_user_id、nickname、profile_url。非命中评论作者资料不补充；原始采集评论本身保留以支持复核和改规则。内容链接和主页链接保存为规范化链接；当前请求所需的临时查询令牌仅用于采集过程，不持久化。
- 数据库每日加密备份；不自动过期删除采集数据。恢复过程需在隔离环境验证后执行。

## 9. 验证策略与验收标准

### 9.1 自动验证

- JSONL 固定样例验证抖音/小红书字段标准化、URL 解析、空字段和匿名化差异适配。
- PostgreSQL 集成验证任务状态机、唯一键去重、每次运行快照和事务边界。
- Scheduler 验证 interval/Cron、Asia/Shanghai 时区、重启恢复、重叠合并和取消。
- AI 使用 Mock API 验证规则草稿结构、预览确认、版本不可变、模型失败状态和作者字段不出站。
- Web/API 验证登录保护、无注册入口、密钥不回显、CSV/Excel 字段正确和分页筛选。
- 本地端到端验收关键词任务、链接任务、手动执行、两种定时、筛选确认、评论查询和导出。

### 9.2 真实平台验收

真实抖音/小红书验证在用户控制的账号和受控环境中手动执行，使用小范围任务。真实平台请求不进入 CI；出现验证、限流或账号状态异常即停止。测试结果只说明当时账号/网络/平台状态，不保证长期稳定。

### 9.3 验收标准

1. 两个平台分别可配置一个账号；登录态、Cookie 和密钥不通过 API 或日志泄露。
2. 关键词与指定内容链接都能创建任务；不支持的链接给出明确校验错误。
3. 手动、interval 和 Cron 均可执行；服务重启后计划恢复且不会批量补跑。
4. 同平台评论按评论 ID 去重；同一评论多次采集产生独立快照，列表能查看点赞、回复数和作者字段变化。
5. 关键词规则与 AI 规则可同时使用；AI 规则预览后批准才生效，命中评论保存规则版本和判定依据。
6. 作者资料只保存批准的三字段，且仅对命中评论作者补充；缺失主页链接时安全留空。
7. 管理员可查看、搜索和管理任务及评论，导出 CSV 与 Excel。
8. 未认证请求不能读取业务数据；公网服务只开放 HTTPS 管理入口；平台访问限制不会触发绕过行为。
9. 本地开发与验证使用与云端相同的 PostgreSQL 主版本和服务拓扑。

## 10. 风险登记

| 风险 | 影响 | 处理方式 |
|---|---|---|
| 平台接口、页面或账号限制变化 | 任务失败或采集字段缺失 | 保留 MediaCrawler 为单一采集适配层；运行可观测；遇到限制暂停并人工处理。 |
| 上游默认匿名化作者 ID | 无法满足用户字段 | 在合规许可范围内做最小定制适配，只保留三个已批准字段，并审查日志。 |
| MediaCrawler 非商业许可证 | 未来用途变化会超授权范围 | 当前限定学习研究；用途变更前重新审查并取得必要授权。 |
| 模型服务接收评论文本 | 评论文本离开本机 | 用户配置服务商；只发送必要评论和任务上下文；不发送作者资料。 |
| 单调度器实例 | API/Worker 高可用性有限 | 首期单机；数据库恢复计划；扩大部署前引入调度锁和多 Worker 设计。 |
| 定时任务持续请求 | 账号或平台受影响 | 单实例全局串行、限制任务上限和频率、挑战时立即暂停、不绕过平台控制。 |
| 上游 WebUI 与采集核心许可证不同 | 分发方式影响义务 | 保留两套许可证和版权；任何对外分发前执行许可证审查。 |

## 11. 架构决策记录

| ADR | 决策 | 理由 |
|---|---|---|
| ADR-001 | 以 MediaCrawler 上游 commit 68d9ef1 为二开底座 | 双平台采集、WebUI/API 已存在，社区与维护活跃度高。 |
| ADR-002 | 复用上游 React/Vite 与 FastAPI 边界 | 减少平台接口集成重复工作；新增业务模块保持边界清晰。 |
| ADR-003 | 本地/云端使用 PostgreSQL 18 系列 | 环境一致，任务状态、运行历史和快照保持事务一致。 |
| ADR-004 | APScheduler 3.11 系列与单 Worker | 单用户、每个平台一个账号；支持 interval/Cron，部署操作简单。 |
| ADR-005 | 云端公网访问采用单管理员账号密码 | 满足用户选择；无注册与多租户范围。 |
| ADR-006 | AI 筛选规则人工预览批准并版本化 | 防止模型生成的条件未经确认即影响采集结果。 |
| ADR-007 | 只保留三项作者公开字段 | 与用户明确选择一致，控制个人信息范围。 |

## 12. 许可证与来源

- MediaCrawler: https://github.com/NanmiCoder/MediaCrawler
- MediaCrawler 上游 API: https://github.com/NanmiCoder/MediaCrawler/blob/68d9ef1c1da22eab75940dfd7cec259907006538/api/main.py
- MediaCrawler 上游依赖: https://github.com/NanmiCoder/MediaCrawler/blob/68d9ef1c1da22eab75940dfd7cec259907006538/pyproject.toml
- MediaCrawler 核心许可证: https://github.com/NanmiCoder/MediaCrawler/blob/main/LICENSE
- MediaCrawler WebUI 许可证: https://github.com/NanmiCoder/MediaCrawler/blob/main/webui/LICENSE
- APScheduler 3.x 用户指南: https://apscheduler.readthedocs.io/en/3.x/userguide.html
- PostgreSQL 发布说明: https://www.postgresql.org/docs/current/release.html
- FastAPI 发布说明: https://fastapi.tiangolo.com/release-notes/
- 调度参考分支: https://github.com/njueeRay/MediaCrawler
- 本地单用户工作台参考: https://github.com/hyperMoss/geiwokehu

## 13. 设计审阅状态

需求基线、源码底座、云端访问方式、PostgreSQL 方案以及四个架构设计部分已在对话中逐节确认。本文件完成自审后提交，等待用户检查全文。收到文档审阅批准后，下一步是编写实施计划；在计划及后续阶段获准前不开始功能实现。
