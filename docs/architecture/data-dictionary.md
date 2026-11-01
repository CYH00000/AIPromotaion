# 数据字典

本文定义业务数据库的逻辑字段边界。实现时须与 MediaCrawler 固定版本的现有表结构做差异评估；不得直接覆盖上游模型或迁移。所有时间戳以 UTC 保存，页面转换为 `Asia/Shanghai`。数据库中的平台 ID 作为不透明字符串处理。

## 实体与约束

| 实体 | 关键字段 | 约束与用途 |
|---|---|---|
| `platform_accounts` | `platform`, `status`, `secret_ref`, `checked_at` | 每个平台最多一条活动账号配置。账号密码、Cookie 和浏览器资料由秘密/私有存储管理；数据库只保存引用和非敏感状态。 |
| `collection_tasks` | `platform`, `source_mode`, `source_config`, `limits`, `schedule`, `filter_config`, `state` | 一个任务只属于一个平台，来源模式只能是关键词或指定链接。计划配置可恢复；任务停用不删除已采数据。 |
| `task_runs` | `task_id`, `trigger_type`, `status`, `config_snapshot`, `counts`, `error_code`, `safe_summary`, timestamps | 手动、interval、Cron 各次触发都形成记录。状态变更受状态机约束；错误摘要脱敏。 |
| `contents` | `platform`, `external_content_id`, `title`, `canonical_url`, `first_seen_at` | 唯一键 `(platform, external_content_id)`。持久化链接去掉临时令牌和非稳定查询参数。 |
| `authors` | `platform`, `platform_user_id`, `nickname`, `profile_url`, `updated_at` | 唯一键 `(platform, platform_user_id)`。仅允许这三个作者字段；字段缺失时为空，不推断。 |
| `comments` | `platform`, `external_comment_id`, `content_id`, `author_id`, `body`, `comment_time`, match state | 唯一键 `(platform, external_comment_id)`。评论正文按原始文本保存以便搜索和重新筛选；不包含二级评论正文。 |
| `comment_snapshots` | `comment_id`, `task_run_id`, `like_count`, `reply_count`, author snapshot, `observed_at` | 唯一键 `(comment_id, task_run_id)`。每次采集均记录观测值；保留获批的作者字段变化。 |
| `filter_rule_versions` | `natural_language`, `rule_json`, `provider/model`, `status`, timestamps | 草稿必须经过预览和管理员批准；批准后的版本不可原位编辑。 |
| `comment_rule_matches` | `comment_id`, `rule_version_id`, `matched`, `reason`, `evaluated_at` | 保存规则版本和判定结果，供结果筛选与审计；理由长度受限并以文本显示。 |
| `admin_sessions` | session digest, created/expiry/revoked timestamps | 仅保存不可逆会话标识摘要及生命周期字段，不保存明文会话令牌。 |

## 数据最小化与完整性规则

- 作者白名单严格限定为平台用户 ID、昵称、主页链接。未命中评论作者不做主页补充；作者信息不能获取时保存空值。
- 模型请求只包含必要评论文本与规则上下文，不包含作者字段、Cookie、平台账号状态或数据库 ID。
- 内容链接和主页链接进入数据库前做平台识别和规范化，去除临时签名/追踪参数；任何不支持链接明确报错，不猜造链接。
- 无平台评论 ID 的评论不进入去重主表，计入运行的无效记录数量；不得用正文哈希替代平台 ID 作为评论身份。
- 删除/停用任务不级联删除评论、快照或运行记录。当前设计不自动过期删除采集数据。
- CSV/XLSX 导出只提供评论主记录、最新观测值及已批准的作者字段；对表格公式前缀做转义。
- ORM/数据库迁移需为唯一键、外键和非负计数建立约束；重复采集使用幂等写入并在同一事务中记录快照。

## 数据库迁移审查

新增字段时说明用途、数据来源、敏感等级、保留策略、索引和回滚方式。迁移不得把上游匿名化数据误当作获批作者字段；如需在上游匿名化前适配，须在代码审查中验证只将白名单字段送入业务数据库，且不会进入日志或上游通用数据库模型。
