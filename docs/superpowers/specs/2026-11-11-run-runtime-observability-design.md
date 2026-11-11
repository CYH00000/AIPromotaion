# 任务运行时可观测性设计规格

- 日期：2026-11-11
- 状态：已确认；待编写实施计划
- 项目目录：D:\codex_project
- 范围：本地 MVP 增量（运行状态、进度、心跳、卡死提示、日志与停止入口）

## 1. 背景与问题

当前采集任务运行期间，`CollectionRun` 只有 `running` 状态，最终计数要等子进程退出并完成入库后才写入。评论在运行中只写入 `data/project_runs/<run_id>/` 下的 JSONL 暂存文件，业务库还不会出现结果。因此界面上会出现「一直运行中、零条命中」，无法区分正在采集、正在 AI 筛选、还是已经卡死。

2026-11-11 的实测：一个抖音任务运行约 8 分钟，暂存 JSONL 已有 1244 条评论和 20 条内容，采集日志仍在输出，但 UI 只显示 `running`，评论总数为 1（上一次运行的旧数据）。

## 2. 目标

- 运行中能看到当前阶段、已暂存的内容/评论数量、最近活动时间；
- 能区分采集中、AI 筛选中、入库中、卡死；
- 能在运行详情里查看最近采集日志并主动停止；
- 不改变采集和筛选的业务语义，不引入增量入库。

## 3. 非目标

- 边采集边入库；本次仍然在采集结束后统一筛选入库。
- 按平台并行；作为下一个独立增量。
- 多 Worker、多实例或云端任务编排。
- 保存完整采集日志到数据库；日志仍由 `crawler_manager` 的内存环形缓冲提供。

## 4. 数据模型

为 `collector_runs` 增加三个字段，使用 Alembic 迁移：

| 字段 | 类型 | 用途 |
|---|---|---|
| `phase` | String(24)，默认 `queued` | 当前阶段 |
| `progress` | JSON，默认 `{}` | 暂存数量、卡死标志等运行中数据 |
| `last_activity_at` | DateTime(timezone=True)，可空 | 最近一次文件增长或日志输出时间 |

阶段取值：

- `queued`：排队；
- `starting`：已领取，正在启动子进程；
- `crawling`：子进程运行中；
- `filtering`：采集结束，正在执行关键词/AI 语义筛选；
- `ingesting`：正在写评论与快照；
- `finalizing`：收尾；
- `completed`：成功或部分完成；
- `failed`：失败；
- `cancelled`：取消。

`progress` 结构：

```json
{
  "staged_contents": 20,
  "staged_comments": 1244,
  "stalled": false,
  "last_log_id": 318
}
```

`status` 仍表示运行生命周期（`queued/running/succeeded/partial/failed/cancelled/interrupted`）；`phase` 表示运行中的细粒度阶段，避免改变现有状态机。

## 5. 进度采集

### 5.1 JSONL 增量计数

新增 `api/services/run_progress.py`，提供：

- `JsonlLineCounter`：按文件路径记录已读偏移和累计行数，只读取新增字节；文件变短时重置该文件计数；末尾没有换行的未完成行不计入。
- `snapshot_counts(directory)`：返回 `staged_contents` 和 `staged_comments`，按文件名中的 `contents` / `comments` 分类。
- `is_stalled(last_activity_at, now, timeout_seconds)`：判断是否超过阈值没有活动。

### 5.2 Worker 进度循环

`collection_worker._execute_run` 在启动采集子进程后启动一个后台任务，每 3 秒：

- 重新计算暂存文件数量；
- 记录 `crawler_manager._log_id` 是否增长；
- 文件或日志有变化时更新 `last_activity_at`；
- 将 `phase` 设为 `crawling`，写入 `progress`；
- 如果进程仍在运行且超过 `COLLECTOR_STALL_TIMEOUT_SECONDS`（默认 180 秒）没有任何变化，写入 `progress.stalled=true`。

子进程退出后停止该任务，依次把 `phase` 设为 `filtering`、`ingesting`、`finalizing`，最终由 `_finish_run` 写入 `completed`/`failed`/`cancelled`。

卡死只做提示，不自动杀进程；管理员可以在运行详情中主动停止。

## 6. API 与界面

- `GET /api/runs` 已返回 run 的全部列，新增字段自动出现在响应中。
- 复用现有 `GET /api/crawler/logs?limit=N` 获取最近日志。
- 复用现有 `POST /api/runs/{run_id}/cancel` 停止运行。
- 前端 `CollectionRun` 类型增加 `phase`、`progress`、`last_activity_at`。
- 任务列表「最近运行」显示阶段和暂存数量，例如：`采集中 · 1244 条 / 20 条内容 · 10 秒前有活动`。
- 点击「运行详情」打开对话框，展示阶段、已运行时长、暂存数量、最终命中/过滤数、最近 50 条日志和「停止运行」按钮。
- 卡死时显示醒目的「无活动」提示，但不自动停止。

## 7. 安全与边界

- 进度字段不包含 Cookie、账号信息或原始请求头。
- 日志仍来自现有采集进程输出；前端按纯文本渲染，不执行 HTML。
- 进度更新失败不应中断采集；错误只记录在服务日志。
- 不修改暂存目录的清理规则；运行结束后仍删除暂存目录。

## 8. 测试与验收

- 单元测试：JSONL 增量计数（追加、截断、未完成行），卡死阈值判断。
- API 序列化：run 响应包含 `phase`、`progress`、`last_activity_at`。
- 手工验收：启动一个任务，任务列表能看到暂存数量持续增长；运行详情能看到日志和停止按钮；停止后状态变为 `cancelled`。
- 前端 `tsc` 与 `vite build` 通过。
- 迁移可 `alembic upgrade head` 和回滚。

## 9. 风险

- 进度轮询会增加少量数据库写入（约每 3 秒一次）；单用户本地场景可接受，后续可拉长间隔或改为内存聚合。
- 平台日志频率低时，`last_activity_at` 可能滞后；文件增长和日志任一变化都算活动。
- 本次不做增量入库，运行中仍然看不到最终命中结果，只能看到暂存数量；界面文案必须明确这一点。
