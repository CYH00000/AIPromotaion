# 项目文档中心

本目录集中保存抖音与小红书评论采集工作台的项目文档。GitHub 浏览 `docs/` 时默认显示本页；根目录只保留 GitHub 标准入口和许可证文件。

## 开始阅读

- [项目范围与当前状态](project-overview.md)
- [实施路线图](architecture/roadmap.md)
- [后续计划与未完成能力](architecture/backlog.md)
- [开发规范与设计门禁](development/standards.md)
- [测试与验收计划](testing/test-and-acceptance-plan.md)

## 架构与数据

- [架构决策记录](architecture/decisions.md)
- [数据字典](architecture/data-dictionary.md)
- [AI 语义筛选规则](architecture/ai-filter-rules.md)
- [安全威胁模型](security/threat-model.md)

## 接口契约

- [当前本地 API 契约](api/openapi.yaml)
- [云端目标 API 契约](api/target-openapi.yaml)

新增或修改业务接口时，必须同步更新 OpenAPI、数据字典和对应设计文档。接口字段使用英文标识，前端展示使用中文。

## 功能设计

- [抖音与小红书评论采集系统设计](superpowers/specs/2026-10-28-douyin-xhs-comment-collector-design.md)
- [AI 筛选容错设计](superpowers/specs/2026-11-11-ai-filter-resilience-design.md)
- [平台账号管理设计](superpowers/specs/2026-11-11-platform-account-management-design.md)
- [运行状态观测设计](superpowers/specs/2026-11-11-run-runtime-observability-design.md)
- [任务内容筛选设计](superpowers/specs/2026-11-11-task-content-filters-design.md)
- [抖音真实地域筛选与评论者省级属地设计](superpowers/specs/2026-11-14-douyin-location-and-comment-ip-design.md)

功能设计获得确认后，先完成接口与数据库设计并再次确认，之后才编写实施计划或进入编码。

## 实施计划

### 基础与采集

- [上游集成与基础设施](superpowers/plans/2026-10-28-upstream-integration-and-foundation.md)
- [采集数据管线](superpowers/plans/2026-10-28-collection-data-pipeline.md)
- [调度与 Worker](superpowers/plans/2026-10-28-scheduling-and-worker.md)
- [筛选与 AI](superpowers/plans/2026-10-28-filtering-and-ai.md)

### 管理与平台能力

- [认证与账号安全](superpowers/plans/2026-10-28-auth-and-account-security.md)
- [管理界面与导出](superpowers/plans/2026-10-28-management-ui-and-export.md)
- [平台账号管理](superpowers/plans/2026-11-11-platform-account-management.md)
- [任务内容筛选](superpowers/plans/2026-11-11-task-content-filters.md)
- [运行状态观测](superpowers/plans/2026-11-11-run-runtime-observability.md)
- [AI 筛选容错](superpowers/plans/2026-11-11-ai-filter-resilience.md)

### 部署

- [云环境加固与部署](superpowers/plans/2026-10-28-cloud-hardening-and-deployment.md)
- [云端部署说明](deployment/cloud-deployment.md)

## GitHub 标准入口

- [项目首页](../README.md)
- [贡献指南](../CONTRIBUTING.md)
- [变更日志](../CHANGELOG.md)
- [第三方许可证与来源](../LICENSES.md)

## 文档维护规则

- 项目功能、架构、接口、数据库、部署和测试文档统一保存在 `docs/`；README、贡献指南、变更日志和许可证保留在仓库根目录，作为 GitHub 标准入口。
- 新增文档后必须在本索引登记，并检查中文名称、相对链接和文档状态。
- 文档不得包含 API Key、服务器凭据、Cookie、登录态、生产数据库信息或真实个人信息。
- 设计文档、OpenAPI、数据字典、迁移脚本和实现必须使用一致的术语与字段语义。
