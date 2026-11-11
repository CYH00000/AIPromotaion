# 平台账号管理页面设计规格

- 日期：2026-11-11
- 状态：已确认；待编写实施计划
- 项目目录：D:\codex_project
- 范围：本地 MVP 增量（选项 A：扫码登录 + 状态展示 + 解绑）

## 1. 背景与目标

当前抖音与小红书的登录态保存在 `browser_data/<platform>_user_data_dir`；启用 CDP 模式时保存在 `browser_data/cdp_<platform>_user_data_dir`。登录只能在采集任务运行时被动触发扫码，管理员无法查看或主动管理登录态。

本增量在管理界面新增「账号管理」视图，让管理员能够：

- 查看抖音和小红书各自是否已有本地登录态，以及最近登录时间；
- 主动触发一次扫码登录，使用与采集任务完全相同的浏览器和配置目录；
- 解绑账号，删除对应平台的本地登录态。

## 2. 范围

### 2.1 本次实现

- 后端新增账号状态查询、启动扫码登录、解绑接口。
- 采集器新增 `--login_only` 模式，完成登录后直接退出，不执行采集。
- 前端采集工作台新增「账号管理」标签页与平台卡片。
- 登录过程中展示运行状态并轮询刷新；解绑需要二次确认。

### 2.2 非目标

- 粘贴 Cookie 登录；后续可作为独立增量。
- 把二维码图片内嵌到网页中；本次沿用上游可见浏览器扫码。
- 多账号、多租户或云端账号管理。
- 新增持久化账号表；本次以本地浏览器配置目录作为状态来源。

## 3. 现状与约束

- 采集任务由 `collection_worker` 以子进程方式调用 `main.py`，`crawler_manager` 只允许一个采集进程同时存在。
- `collection_worker` 当前固定使用 `LoginTypeEnum.QRCODE` 且 `headless=False`。
- 上游 `start()` 在登录后立即进入采集，没有「只登录」的退出点。
- 浏览器配置目录由 `config.USER_DATA_DIR` 与 `config.PLATFORM` 决定；CDP 模式使用 `cdp_` 前缀。
- `browser_data/` 已被 Git 忽略，不会进入版本库。
- 平台「登录态是否仍然有效」无法廉价探测；本规格只保证「是否配置过」和「本次登录是否写入新的登录标记」。真实有效性由任务运行时的平台登录检查体现。

## 4. 总体设计

### 4.1 后端组件

- `api/services/account_service.py`
  - `profile_dir(platform)`：按当前配置解析平台浏览器配置目录，结果必须位于项目 `browser_data/` 下。
  - `login_marker_path(platform)`：登录成功标记文件路径 `browser_data/.login_state/<platform>.json`。
  - `account_status()`：返回抖音、小红书的配置状态、最近登录时间和登录尝试状态。
  - `start_login(platform)`：校验无采集或登录进程运行后，以 `--login_only` 启动可见浏览器子进程。
  - `unbind(platform)`：校验路径与进程状态后删除平台配置目录和登录标记；目录不存在时保持幂等成功。
- `api/routers/accounts.py`
  - 提供下列接口，全部要求管理员会话；写操作额外要求 CSRF。
- `cmd_arg`、`main.py`、`media_platform/douyin/core.py`、`media_platform/xhs/core.py`
  - 增加 `--login_only` 参数与 `config.LOGIN_ONLY`。
  - 平台 `start()` 在登录检查完成后判断 `config.LOGIN_ONLY`，若为真则关闭浏览器上下文并返回，不进入搜索/详情/创作者流程。
  - 返回前写入登录标记文件，内容为本次完成校验的 UTC 时间。标记文件是本次登录是否成功的可靠依据，不依赖浏览器配置目录的修改时间。

### 4.2 状态与数据流

1. 页面加载时调用 `GET /api/accounts`，展示两个平台的状态。
2. 管理员点击「登录/重新登录」，前端调用 `POST /api/accounts/{platform}/login`。
3. 后端确认当前没有采集或登录进程，启动 `python main.py --platform <p> --lt qrcode --login_only true --headless false`。
4. 可见浏览器打开并显示二维码，管理员扫码完成登录；登录态写入对应配置目录。
5. 登录检查通过后，采集器写入登录标记文件；子进程退出后，后端根据「标记文件是否在本次登录开始后写入」判断成功或失败，并更新内存中的尝试状态。
6. 前端在登录运行期间轮询 `GET /api/accounts`，状态变为成功/失败后停止轮询并提示。
7. 管理员点击「解绑」并确认后，前端调用 `DELETE /api/accounts/{platform}`，后端删除配置目录。

如果启动时平台已经处于有效登录状态，登录子进程会直接完成校验并写入标记，不会再次弹出二维码。界面文案需使用「登录 / 验证登录态」，避免让管理员误以为必然出现新的扫码。

登录尝试状态只保存在服务进程内存中：

- `idle`：没有进行中的登录尝试；
- `running`：登录子进程已启动；
- `succeeded`：登录标记在本次登录开始后写入；
- `failed`：子进程结束但登录标记未更新，或启动失败。

服务重启后尝试状态回到 `idle`，平台配置状态仍由文件系统正确恢复。

## 5. API 契约

### 5.1 查询账号状态

`GET /api/accounts`

```json
{
  "items": [
    {
      "platform": "dy",
      "label": "抖音",
      "configured": true,
      "profile_mode": "cdp",
      "last_login_at": "2026-11-01T22:37:03Z",
      "login_state": "idle",
      "login_started_at": null,
      "login_error": null
    },
    {
      "platform": "xhs",
      "label": "小红书",
      "configured": false,
      "profile_mode": "cdp",
      "last_login_at": null,
      "login_state": "idle",
      "login_started_at": null,
      "login_error": null
    }
  ]
}
```

`profile_mode` 表示当前采集配置实际使用的浏览器配置目录类型：`cdp` 对应 `browser_data/cdp_<platform>_user_data_dir`，`standard` 对应 `browser_data/<platform>_user_data_dir`。切换 `ENABLE_CDP_MODE` 后，账号状态会随实际使用的目录变化。

### 5.2 启动扫码登录

`POST /api/accounts/{platform}/login`

- `platform` 仅允许 `dy`、`xhs`；其他值返回 400。
- 成功启动返回 202：`{"platform": "dy", "status": "started"}`。
- 已有采集或登录进程运行返回 409，错误信息说明需要等待当前任务结束。

### 5.3 解绑账号

`DELETE /api/accounts/{platform}`

- 成功返回 204；目录不存在同样返回 204。
- 平台不合法返回 400。
- 有采集或登录进程运行返回 409。

## 6. 安全与错误处理

- 所有接口要求管理员会话；POST/DELETE 要求 CSRF。
- 接口不返回 Cookie、浏览器完整路径或平台会话内容。
- 删除前将目标路径解析为绝对路径，并确认其父目录为项目 `browser_data/`，目标目录名必须属于平台白名单。
- 采集进程或登录进程运行时拒绝解绑，避免删除正在使用的浏览器配置。
- 登录期间 Worker 暂停领取新的采集运行；登录结束后恢复。由 `collection_worker` 在领取运行前检查账号服务暴露的忙碌标记。已在运行的采集进程存在时拒绝启动登录。
- 登录失败只返回稳定的安全摘要，不返回平台的原始错误正文或请求头。
- 未配置账号不影响创建任务；任务运行时仍按现有流程要求登录。

## 7. 测试与验收

自动验证：

- 路径解析：标准模式与 CDP 模式分别解析到正确目录，非法平台被拒绝。
- 状态检测：使用临时目录验证 `configured`、`last_login_at` 与空状态；登录标记优先于目录时间。
- 解绑安全：拒绝 `browser_data/` 之外的目标；允许删除白名单目录；目录不存在时幂等成功。
- 忙碌保护：采集或登录进程运行时，登录与解绑返回 409。
- 前端执行 `tsc` 与 `vite build`。

手工验收：

- 抖音、小红书各触发一次扫码登录，浏览器打开并显示二维码。
- 扫码完成后状态由未配置变为已配置，最近更新时间更新。
- 解绑后状态回到未配置，配置目录被删除。
- 登录期间「账号管理」页显示运行中，成功后提示完成。

## 8. 风险

- 平台登录页面、二维码选择器或风控策略变化会使扫码流程失效；继续依赖上游采集器，不另写一套平台客户端。
- 「目录存在」不等于登录仍然有效；页面文案明确说明状态是本地配置状态。
- CDP 模式下登录复用本机浏览器配置，可能与用户手动操作浏览器互相影响；单实例约束下先保持现状。
- 登录子进程最长等待约 10 分钟；前端轮询需有明确的运行中提示和离开页面的兜底。
