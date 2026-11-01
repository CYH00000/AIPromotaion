# 许可证与来源清单

## 上游 MediaCrawler

仓库：https://github.com/NanmiCoder/MediaCrawler
固定设计基线：68d9ef1c1da22eab75940dfd7cec259907006538

- 采集核心根许可证：NON-COMMERCIAL LEARNING LICENSE 1.1。仅限非商业学习与研究，禁止大规模采集或干扰平台运行；保留许可证和版权声明。未经权利人书面同意不得商业使用。
- WebUI 目录许可证：GPL-3.0。保留 GPL 文本、来源和变更记录；对外分发时复核 GPL 义务。
- 上游不同子目录或第三方依赖可能存在各自声明；实现前扫描依赖许可证并更新清单。

## 设计参考项目

- njueeRay/MediaCrawler：https://github.com/njueeRay/MediaCrawler
  仅用于调度架构研究；当前没有计划复制其独立新增代码。
- hyperMoss/geiwokehu：https://github.com/hyperMoss/geiwokehu
  仅用于产品流程参考；仓库没有明确项目级许可证声明，不复制其代码。
- Aswellle/WeMediaCrawler：https://github.com/Aswellle/WeMediaCrawler
  仅用于 WebUI/上游同步模式参考；其采集核心继续受 MediaCrawler 非商业学习许可证约束。

## 项目新增代码

新增代码的许可证与分发方式需在实施前确认，并不得将 MediaCrawler 的非商业许可误写成宽松商业许可。设计文档阶段不新增任何可执行源码。

## 审查门禁

每次引入依赖或复制/修改上游文件前，检查对应 LICENSE/NOTICE 和版权头；任何后续商业用途、公开分发或对外服务方式改变都需要重新审查授权边界。
