# M1-A 业务数据模型与领域规则

> 归档日期：2026-08-06
> 版本：v0.2.0-m1a
> 原始变更：`changes/archive/2026-08-06-m1a-business-data-models/`
> 系统基线：`SYSTEM-SPEC.md`
> 验收报告：`docs/m1a-verification.md`

## 精简行为

M1-A 在 M0 工程底座上实现 T03、T04、T05 的数据与领域规则基线。系统可在 PostgreSQL 16 中通过 Alembic 建立 16 张业务表，并通过领域函数与 Repository 边界保存和校验任务、商品、品牌、维度、评论、指标、报告、追问和模型运行审计数据。

本里程碑实现的是数据结构、关系、持久化 seam 和规则，不是购物比较端到端业务。数据库中存在报告、指标和评论模型，不表示报告生成、指标算法或评论分析已经实现。

## 关键关系

| 聚合/目录 | 关系与职责 |
|---|---|
| 对比任务 | 任务 1:N 候选商品、事件、任务维度、指标、报告、追问、模型运行。 |
| 候选商品 | 候选商品 1:N 商品快照、SKU、原始评论；同一任务按 position 唯一。 |
| 评论分析 | 原始评论 1:N 注解；每个注解引用已注册维度，证据必须是评论正文连续子串。 |
| 报告 | 任务 1:N 版本报告，报告 1:N claim；可发布 claim 必须有可解析来源。 |
| 品牌目录 | 品牌 1:N 字段级来源；冲突来源均保留，未知或冲突字段不用于推荐。 |
| 维度目录 | 维度定义 1:N 任务维度、评论注解和指标；稳定 code 必须先解析为目录记录。 |
| 删除边界 | 删除任务清理其私有子图；共享品牌与维度目录不随任务级联删除。 |

## 约束与安全边界

- 数据库负责主外键、非空、唯一组合、范围 CHECK、查询索引和删除关系；领域层负责状态转换、目录解析、证据与来源有效性、报告发布门禁。
- 评论窗口仅允许 30/60 天；评分为 1～5；进度为 0～100；置信度为 0～1；`model_runs.attempts >= 1`。
- 候选 URL 入库复用 `NormalizedProductUrl`；商品、SKU、评论和来源映射复用既有不可变 Commerce DTO，不建立不兼容 DTO。
- 原始评论只持久化必要字段和白名单来源，不保存 raw payload。JSON、事件和审计不得包含 Cookie、Authorization、API Key、登录态、完整 Prompt、完整模型响应或未经脱敏的 Provider payload。
- 统计数量、比例、价格换算、趋势、样本量和置信度必须由后续确定性程序计算，LLM 不是真源。
- Repository 不自行 commit；事务由 `UnitOfWork` 或调用方控制。

## 迁移

| Revision | 表数 | 表 |
|---|---:|---|
| `0002` / T03 | 5 | `comparison_tasks`、`comparison_products`、`product_snapshots`、`product_skus`、`task_events` |
| `0003` / T04 | 4 | `brand_profiles`、`brand_sources`、`dimension_definitions`、`task_dimensions` |
| `0004` / T05 | 7 | `raw_reviews`、`review_annotations`、`analysis_metrics`、`comparison_reports`、`report_claims`、`followup_messages`、`model_runs` |

迁移链为 `0001 -> 0002 -> 0003 -> 0004`，当前 head 为 `0004`。已在 PostgreSQL 16 空库完成 upgrade/current/check、downgrade 到 `0001`、重新 upgrade 和 check，最终确认 16 张业务表且无未记录 schema 差异。

## 关键代码索引

| 路径 | 职责 |
|---|---|
| `backend/src/app/domain/comparisons/` | 任务状态、阶段、进度、评论窗口和候选规则 |
| `backend/src/app/domain/products/` | 安全 URL、价格、SKU 与来源规则 |
| `backend/src/app/domain/brands/` | 品牌名称、核验状态、字段来源与冲突规则 |
| `backend/src/app/domain/dimensions/` | 维度 code、来源类型、目录解析和排序规则 |
| `backend/src/app/domain/reviews/` | 评分、情感、置信度和连续原文证据规则 |
| `backend/src/app/domain/metrics/` | 指标非空来源规则 |
| `backend/src/app/domain/reports/` | 报告版本、claim 来源解析与发布门禁 |
| `backend/src/app/domain/model_runs/` | 模型运行状态、计数和 attempts 规则 |
| `backend/src/app/infrastructure/db/models/` | 16 张 SQLAlchemy ORM 业务表 |
| `backend/src/app/infrastructure/db/comparison_repository.py` | T03 聚合持久化 |
| `backend/src/app/infrastructure/db/catalog_repository.py` | T04 品牌与维度目录持久化 |
| `backend/src/app/infrastructure/db/analysis_repository.py` | 评论、注解与指标持久化 |
| `backend/src/app/infrastructure/db/report_repository.py` | 报告、claim 与追问持久化 |
| `backend/src/app/infrastructure/db/model_run_repository.py` | 模型运行 Repository 与 SQLAlchemy LLM audit sink |
| `backend/alembic/versions/0002_add_t03_comparison_models.py` | T03 迁移 |
| `backend/alembic/versions/0003_add_t04_catalog_models.py` | T04 迁移 |
| `backend/alembic/versions/0004_add_t05_analysis_models.py` | T05 迁移 |
| `backend/tests/unit/domain/` | 领域规则单元测试 |
| `backend/tests/integration/db/` | PostgreSQL 结构、约束、Repository 和迁移测试 |

## 测试证据

- Python `3.12.13`；
- Ruff lint：PASS；
- Ruff format check：`80 files`；
- mypy strict：`58 files`，PASS；
- pytest：`122 passed`；
- PostgreSQL 16 空库迁移生命周期：upgrade/current/check、downgrade `0001`、re-upgrade/current/check 全部 PASS；
- 最终业务表数量：16；Alembic head：`0004`。

精确验收记录见 `docs/m1a-verification.md`。

## Out of scope

- 商品比较业务 API、Application Service、授权与访问控制用例；
- Celery 业务任务、LangGraph 工作流、进度推送和保留期 Worker；
- 商品解析、SKU 确认、可比性判断、维度推荐、评论清洗/注解执行；
- 指标计算算法、报告生成、图表、报告追问业务与管理端；
- 商品比较前端页面；
- 真实淘宝 Provider、真实 LLM Provider 和生产数据回填。

## Concern

结论为 **PASS_WITH_CONCERNS**。唯一 concern 是测试依赖产生 `testcontainers.postgres` 弃用警告；它不影响本次 122 项测试、PostgreSQL 16 迁移生命周期或 16 表结论，后续应按 testcontainers 新 API 清理警告。
