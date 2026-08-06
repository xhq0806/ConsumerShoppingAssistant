# M1-A 数据模型验收报告

> 验收日期：2026-08-06
> 版本：v0.2.0-m1a
> 归档规格：`changes/archive/2026-08-06-m1a-business-data-models/spec.md`
> 归档设计：`changes/archive/2026-08-06-m1a-business-data-models/design.md`
> 归档任务：`changes/archive/2026-08-06-m1a-business-data-models/tasks.md`
> 结论：**PASS_WITH_CONCERNS**

## 验收范围

验收 M1-A 的 T03 对比任务与商品模型、T04 品牌与维度目录、T05 评论/指标/报告/模型审计模型，包括领域规则、Repository、Alembic 迁移、数据库约束、删除边界和安全持久化边界。

不验收 API、Celery 业务编排、LangGraph、业务算法、前端、真实淘宝或真实 LLM；这些能力在 M1-A 未实现。

## 精确证据

| 项目 | 结果 |
|---|---|
| Python | `3.12.13` |
| Ruff | PASS |
| Ruff format | `80 files`，PASS |
| mypy strict | `58 files`，PASS |
| pytest | `122 passed` |
| PostgreSQL | `16` |
| 空库 upgrade/current/check | PASS，head=`0004`，`alembic check` 无差异 |
| downgrade | `0004 -> 0001`，PASS |
| re-upgrade/current/check | PASS，head=`0004`，`alembic check` 无差异 |
| 业务表 | `16` 张 |

迁移链：

```text
0001 -> 0002 -> 0003 -> 0004 (head)
```

业务表分布：T03 5 张、T04 4 张、T05 7 张，共 16 张。

## 已验证行为

- 数据库约束拒绝非法枚举、范围、唯一组合和外键引用。
- 领域规则拒绝非法任务状态转换、未知维度、无效评论证据、空指标来源、无来源或来源不可解析的报告 claim。
- 多快照、多 SKU、多主题注解、多报告版本和冲突品牌来源可以被表达。
- 任务私有子图可按删除关系清理；共享品牌和维度目录不会被任务删除误删，仍有引用时受保护。
- Commerce DTO 入库 seam 与 LLM audit seam 被复用；持久化边界不保存 raw Provider payload、完整 Prompt、完整模型响应或凭据。

## Concern

唯一 concern：测试输出包含 `testcontainers.postgres` 弃用警告。该警告不影响测试执行、PostgreSQL 16 容器可用性、Alembic 往返迁移或 schema 检查，因此不阻塞归档；后续应升级到 testcontainers 推荐的新导入/API 并消除警告。

## 最终结论

**PASS_WITH_CONCERNS — 允许将 M1-A 文档收口并归档。**

M1-A 的领域、ORM、Repository、16 张业务表和 `0004` 迁移 head 已通过给定质量与 PostgreSQL 16 验收。除上述弃用警告外无其他 concern；本结论不扩大到尚未实现的 API、编排、算法、前端或真实外部 Provider。
