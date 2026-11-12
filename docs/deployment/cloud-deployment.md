# 私有云部署与运维说明

> 当前交付物是面向 Ubuntu 24.04 单机、Docker Compose 和 Tailscale 的私有云部署包。它已经在 Windows Docker 隔离环境中完成容器、登录、noVNC、持久化和加密备份恢复验证，但尚未在用户的真实云服务器上执行远程验收，因此不能提前宣称公网生产环境已经上线。

## 当前拓扑

- 一个 `app` 容器运行 FastAPI、单实例调度器、Playwright Chromium、Xvfb、x11vnc 和 noVNC。
- 一个独立的 PostgreSQL 18 容器保存任务、运行、评论和账号会话等结构化数据。
- 数据库只连接内部网络 `collector_private`；应用额外连接 `collector_egress`，用于访问抖音、小红书和已配置的 AI 服务。
- 应用端口和 noVNC 端口只发布到宿主机 `127.0.0.1`，不绑定公网网卡。
- Tailscale Serve 把宿主机回环端口发布为仅 Tailscale 网络可访问的 HTTPS 地址。
- `browser_data`、`project_data` 和 `postgres_data` 使用三个持久卷。
- 容器使用 UID/GID `10001:10001` 运行，并启用 `no-new-privileges`、有界日志和健康检查。

现有真实域名在本阶段保留不用。Tailscale Serve 使用 Tailscale 自动签发的私有 HTTPS 域名，不要求网站域名解析到云服务器。后续如确需公网域名访问，应单独评审反向代理、TLS、登录防护、限流和公网攻击面，不能直接把当前回环端口改成 `0.0.0.0`。

## 服务器前提

- Ubuntu 24.04，建议至少 4 核 CPU、8 GB 内存和 20 GB 可用磁盘。
- 已安装 Docker Engine、Docker Compose 插件、Git、Python 3、OpenSSL 和 Tailscale。
- 使用非 root 的部署账号；该账号能够执行 `docker compose`，但不是无人值守的 root 服务账号。
- 服务器能够访问 GitHub、容器镜像仓库、抖音、小红书、Tailscale 控制面和实际使用的 AI API。
- 真实验收前，必须先确认平台账号授权范围、采集频率和内容使用方式符合平台规则及适用法律。

## 1. 准备代码与生产配置

将经审查的分支或提交检出到固定目录，例如 `/opt/collector`：

```bash
cd /opt/collector
cp deploy/.env.production.example deploy/.env.production
chmod 600 deploy/.env.production
```

在 `deploy/.env.production` 中填写数据库密码、管理员用户名和密码、noVNC 密码。管理员密码至少 16 个字符，noVNC 密码至少 12 个字符；不要继续保留任何 `replace-with` 占位值。聊天、截图、Issue 和 Git 提交中都不要出现真实密码。

为加密备份创建独立口令文件，不能与数据库或管理员密码相同：

```bash
sudo install -d -m 700 -o "$USER" -g "$USER" /etc/collector
umask 077
openssl rand -base64 32 > /etc/collector/backup-passphrase
chmod 600 /etc/collector/backup-passphrase
```

确认 `deploy/.env.production` 中的 `BACKUP_PASSPHRASE_FILE` 指向该绝对路径。生产校验会拒绝示例密码、非 HTTPS 的 AI 地址、Secure Cookie 未启用以及启用 CDP 的配置。

## 2. 检查宿主机

先完成 `tailscale up`，再加入 Tailscale 网络，然后运行：

```bash
cd /opt/collector
bash deploy/prepare.sh
```

此脚本只检查 Ubuntu 版本、Docker、Compose、Tailscale、配置、权限和磁盘空间，不安装或修改系统软件。它不会输出秘密值。

## 3. 部署服务

```bash
cd /opt/collector
bash deploy/deploy.sh
```

脚本会构建以当前提交命名的应用镜像、启动 PostgreSQL、执行 Alembic 迁移、启动应用并等待 `/health/ready`。应用、浏览器运行时和 noVNC 都由同一个容器入口监督；任一关键子进程异常退出时，容器会整体重启，避免出现“网页还在但采集运行时已经死亡”的假健康状态。

部署成功后，工作台和 noVNC 仍然只能在服务器本机回环地址访问。继续配置私有 HTTPS：

```bash
cd /opt/collector
bash deploy/setup-tailscale.sh
bash deploy/status.sh
```

`Tailscale Serve` 将提供：

- 工作台：`https://<Tailscale 主机名>/`
- noVNC：`https://<Tailscale 主机名>:8443/vnc.html`

noVNC 使用 `.env.production` 中的 `NOVNC_PASSWORD` 登录。打开 noVNC 后，在云端 Chromium 中完成获授权账号的扫码登录。浏览器资料保存在 `browser_data` 持久卷中，不会下载到管理员电脑。

## 4. 安全组与端口边界

云安全组只需对可信管理员 IP 开放 SSH，例如 22 端口；优先使用云厂商的会话管理或堡垒机。不要向公网开放以下端口：

- 80/443：当前不使用公网域名入口。
- 8080/6080：应用和 noVNC 只应绑定宿主机回环地址。
- 5432：PostgreSQL 只存在于 Compose 私有网络。
- 9222：生产环境禁用 CDP，调试端口不得开放。

Tailscale 依赖出站连接和其自身的 NAT 穿透；当前方案不要求为 Tailscale Serve 另行开放公网 443。若组织网络策略要求固定直连端口，应由网络管理员按 Tailscale 官方建议最小化放行，不能放行到 `0.0.0.0/0`。

在服务器检查监听地址：

```bash
ss -lntp
docker compose --env-file deploy/.env.production -f deploy/compose.prod.yml port app 8080
docker compose --env-file deploy/.env.production -f deploy/compose.prod.yml port app 6080
docker compose --env-file deploy/.env.production -f deploy/compose.prod.yml exec app id -u
```

前两个端口应显示 `127.0.0.1`，容器 UID 应为 `10001`。再从云服务器外部使用另一台电脑检查公网 IP：对 8080、6080、5432 和 9222 的连接都必须失败。真实域名在未配置公网入口前不应指向该服务。

## 5. 日常状态与日志

```bash
bash deploy/status.sh
bash deploy/logs.sh app
bash deploy/logs.sh app --follow
bash deploy/logs.sh postgres
```

日志命令只读取最近 200 行，避免一次输出无限增长。任务运行阶段、暂存数量、最近活动和停止操作应以前端“运行详情”为准；本包的容器健康检查只代表 Web/API、数据库连接和容器主进程可用，不替代平台任务验收。

## 6. 加密备份

手动创建一致性备份：

```bash
cd /opt/collector
bash deploy/backup.sh
```

备份会短暂停止应用，使用 `pg_dump` 导出 PostgreSQL，并通过一次性容器归档 `browser_data` 和 `project_data`。所有产物使用 OpenSSL AES-256-CBC/PBKDF2 加密，目录为 `deploy/backups/<UTC 时间>/`，并生成 SHA-256 校验和与非秘密元数据。

每个备份应包含：

```text
postgres.dump.enc
browser_data.tar.gz.enc
project_data.tar.gz.enc
metadata.txt
SHA256SUMS
```

可在 Linux 服务器上校验：

```bash
cd deploy/backups/<时间目录>
sha256sum -c SHA256SUMS
```

建议每天执行一次，例如在部署账号的 crontab 中加入：

```cron
15 3 * * * cd /opt/collector && /usr/bin/env bash -lc 'bash deploy/backup.sh' >> /var/log/collector-backup.log 2>&1
```

备份口令文件必须与备份分开保管。完成本地备份后，应通过服务器已有的加密对象存储或异地备份工具同步整个时间目录；不要只把备份留在同一块云盘上，也不要把备份目录挂到 Web 根目录。

## 7. 恢复

恢复会清空当前 PostgreSQL schema、`browser_data` 和 `project_data`，必须显式确认：

```bash
cd /opt/collector
bash deploy/restore.sh --confirm /opt/collector/deploy/backups/<时间目录>
```

脚本先校验 SHA-256 和加密头，再停止应用、恢复数据库和两个数据卷、执行迁移、重新启动并检查就绪状态。恢复后应重新检查平台账号登录态、任务列表和最近运行。重要升级或迁移前，先用隔离测试环境演练恢复。

## 8. 升级与回滚

升级前确保工作区没有已跟踪文件未提交修改，再执行：

```bash
cd /opt/collector
bash deploy/upgrade.sh origin/main
```

`upgrade.sh` 会先创建加密备份，拉取远端、切换到目标提交、重新构建和部署。部署失败时会恢复原代码检出；数据库迁移是否可逆必须按具体迁移判断，必要时使用刚才的备份执行 `restore.sh`。

手工代码回滚至少需要切回上一个已验证提交并重新执行 `deploy.sh`。不要直接复用旧镜像而跳过数据库迁移检查。

## 9. 故障排查

- 应用未就绪：先运行 `bash deploy/logs.sh app`，检查配置校验、Alembic、Uvicorn、Xvfb、x11vnc 和 websockify 的错误。
- noVNC 打不开：确认 `status.sh` 中两个 Tailscale 路由存在，确认宿主机 `NOVNC_BIND_PORT`（生产默认 6080）只绑定回环地址，并检查 noVNC 密码。
- 扫码后登录态丢失：确认浏览器资料卷没有误删，检查容器和卷所属 UID；不要把浏览器资料写入普通临时目录。
- 任务长期无进展：查看前端运行阶段、最近活动和日志；健康探针只确认服务就绪，平台限流、验证码或账号失效应停止任务并人工处理。
- 恢复失败：保留原备份目录不要修改，先核对 `SHA256SUMS`、口令文件权限和容器镜像是否存在，再在隔离项目中验证。

## 10. 上线门禁

本地部署包验收不能替代真实服务器验收。切换到真实云服务器后至少完成：Tailscale 私有 HTTPS 可访问、noVNC 扫码登录成功、公网 8080/6080/5432/9222 均关闭、容器 UID 为 10001、备份与恢复演练成功，以及用户授权的单个平台小范围任务能真实运行。完成这些项目前，保持真实域名不对外提供入口。
