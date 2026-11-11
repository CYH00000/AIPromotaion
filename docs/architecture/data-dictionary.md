# 数据字典（本地 MVP）

业务表由 `migrations/` 中的 Alembic 迁移创建，统一使用 `collector_` 前缀，和 MediaCrawler 上游 ORM 元数据隔离。所有时间戳使用带时区的 UTC；Cron 计划按 `Asia/Shanghai` 解释。

## 表与字段

| 表 | 关键字段 | 约束与用途 |
|---|---|---|
| `collector_tasks` | 平台、来源模式/值、包含/排除关键词、内容/评论上限、内容排序、发布时间范围、计划、状态、下次执行时间 | 关键词任务可选择综合/最新/最多点赞排序，以及不限/一天/一周/半年发布时间；指定链接模式按链接采集。任务停用只停止未来计划，不删除运行和评论。URL 在保存前去掉查询令牌。 |
| `collector_filter_rules` | 规则 ID、谱系 ID/版本、父版本、自然语言意图、受限 JSON 定义、模型名、draft/approved 状态、批准时间 | 草稿不能绑定任务；批准后字段只读。编辑产生新的子版本。 |
| `collector_runs` | `task_id`, `trigger_type`, `status`, `config_snapshot`, `counts`, `error_code`, `safe_summary` | 每次手动或计划执行一行；任务配置在开始时快照；运行状态包括 queued/running/succeeded/partial/failed/cancelled/interrupted。 |
| `collector_comments` | 平台评论 ID、内容 ID/标题/链接、正文、评论时间、命中关键词、作者三字段 | 唯一键 `(platform, external_comment_id)`；无稳定平台评论 ID 的记录跳过。作者字段只包含平台用户 ID、昵称和主页 URL。 |
| `collector_comment_snapshots` | `comment_id`, `run_id`, 点赞数、回复数、作者字段快照、命中关键词、规则 ID/版本、筛选理由、观测时间 | 唯一键 `(comment_id, run_id)`；重复入库更新该次快照，不产生重复行。 |
| `collector_admin_sessions` | 会话摘要、CSRF 摘要、创建/过期/撤销时间 | 不存明文会话令牌；单管理员会话最长 12 小时。 |

## 数据最小化与完整性

- 上游 MediaCrawler 的输出先写入每次运行独立的 JSONL 暂存目录；完成筛选和事务入库后立即删除暂存目录。
- 业务库仅存命中包含/排除及已批准 AI 语义规则的评论及获批作者字段；不采集头像、签名、IP 属地、粉丝量或二级评论正文。语义服务失败的评论不入库。
- 评论以平台评论 ID 去重；点赞数和回复数保存在每次运行快照。
- URL 仅保留受支持平台的 HTTPS 主机与路径，移除查询参数和临时签名令牌。
- CSV/XLSX 导出仅包含评论、内容标题/链接、最新互动数、作者白名单字段、命中词、语义规则版本/理由和最近观测时间；公式前缀会被转义。
- 会话 Cookie 和模型密钥不写入日志或数据库明文。模型密钥保存在服务端 `.env`/部署密钥；API 只返回已配置状态。

## 尚未单独规范化的目标实体

完整设计曾规划 `contents`、`authors` 和 `comment_rule_matches`。本地 MVP 将内容与作者字段内嵌在 `collector_comments`，规则版本保存于 `collector_filter_rules`，规则匹配信息写入每次运行快照。
