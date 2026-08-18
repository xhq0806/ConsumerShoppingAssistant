# 功能 Spec 索引

> AI 归档自动维护，记录本项目沉淀的功能规格。
> 编码前先查阅相关 spec，避免重复探索。

| 功能 | 文件 | 归档日期 | 涉及模块 |
|---|---|---|---|
| M0 工程基础 | [m0-engineering-foundation.md](m0-engineering-foundation.md) | 2026-08-05 | FastAPI、Commerce Provider、LLM Gateway |
| M1-A 业务数据模型与领域规则 | [m1a-business-data-models.md](m1a-business-data-models.md) | 2026-08-06 | T03/T04/T05、16 表、领域规则、Repository |
| M1-B 对比草稿与商品确认流程 | [comparison-draft-confirmation.md](comparison-draft-confirmation.md) | 2026-08-06 | Comparison API、Application Service、幂等与 SKU 确认 |
| M1-C 商品输入与用户偏好闭环 | [m1c-shopping-input-preferences.md](m1c-shopping-input-preferences.md) | 2026-08-10 | T26 前端流程、T13 用户偏好、Pinia、Vite/Nginx 代理 |
| M1-D 动态维度推荐与确认闭环 | [m1d-dynamic-dimensions.md](m1d-dynamic-dimensions.md) | 2026-08-11 | 维度种子、确定性推荐、任务维度 API、Vue 确认页 |
| M1-E 异步评论采集与进度闭环 | [m1e-async-review-ingestion.md](m1e-async-review-ingestion.md) | 2026-08-17 | Compose migrate、Celery Worker、评论清洗、进度 API/页面 |
| DeepSeek LLM 配置与 Adapter | [deepseek-llm-adapter.md](deepseek-llm-adapter.md) | 2026-08-17 | Chat Completions、analysis/report profile、JSON、thinking、脱敏审计 |
| M1-F 评论智能注解与指标计算闭环 | [m1f-review-annotation-metrics.md](m1f-review-annotation-metrics.md) | 2026-08-17 | DeepSeek analysis、评论证据注解、断点恢复、确定性指标、processing/75 |
| M1-G 报告生成与任务完成闭环 | [m1g-report-completion.md](m1g-report-completion.md) | 2026-08-18 | report profile、claim 来源、partial fallback、报告 API/页面、任务终态 |
