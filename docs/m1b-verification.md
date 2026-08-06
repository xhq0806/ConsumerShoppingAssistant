# M1-B 对比草稿与商品确认流程验收报告

> 验收日期：2026-08-06
> 版本：v0.3.0-m1b
> 原始规格：`changes/archive/2026-08-06-comparison-draft-confirmation/spec.md`
> 结论：**PASS**

## 验收范围

本次验收覆盖 T11 对比草稿与 T12 商品确认，包括：

- 创建 2～3 个候选商品的对比草稿；
- URL 安全规范化、重复候选拒绝和创建幂等；
- Fixture 商品解析、快照/SKU 原子持久化和失败留痕；
- 聚合详情查询和响应字段白名单；
- 完整商品/SKU 确认、基础类别可比性和确认幂等；
- `0005` 幂等迁移、数据库约束和迁移生命周期；
- ProblemDetails、事务回滚和既有 M0/M1-A 回归。

不验收用户偏好、动态维度、品牌资料、评论分析、Celery/LangGraph、报告、业务前端、
用户鉴权、真实淘宝 Provider 或真实 LLM Provider。

## 审查修复

归档前审查发现并修复：

1. 草稿或失败任务的全部空 SKU 选择可能被误判为重复确认。修复后只有
   `awaiting_dimension_confirmation` 状态且选择完全一致时才允许确认幂等重放。
2. 两个数据库测试缺少 `integration` 标记，导致快速测试命令仍可能启动 Docker。
   修复后快速套件和数据库套件可以稳定分离。
3. Testcontainers 使用弃用导入。已切换到 `testcontainers.community.postgres`。

## 本地验收证据

本项目为个人项目，不以远端 CI 运行记录作为当前验收前提。以下命令均于
2026-08-06 在本地 Windows、Python 3.12.13、Docker Desktop 29.6.1 和 PostgreSQL 16
Testcontainers 环境执行。

| 检查 | 结果 |
|---|---|
| Ruff lint | PASS |
| Ruff format check | PASS |
| mypy strict | PASS，64 个源文件 |
| Pytest 快速套件 | PASS，104 passed，32 deselected |
| Pytest PostgreSQL 集成套件 | PASS，32 passed |
| Pytest 完整套件 | PASS，136 passed |
| Alembic upgrade/check | PASS，head=`0005`，无 metadata drift |
| Alembic downgrade/re-upgrade | PASS，`0005 -> 0004 -> 0005` |
| 前端 typecheck | PASS |
| 前端 Vitest | PASS，1 passed |
| 前端 production build | PASS |

标准本地门禁：

```bash
cd backend
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -m "not integration"
python -m pytest -m integration tests/integration/db
python -m pytest

cd ../frontend
npm run typecheck
npm run test -- --run
npm run build
```

## 已验证行为

- 相同幂等键和相同载荷只创建一个任务；不同载荷返回冲突。
- 规范化后重复候选不会创建任务。
- Provider 调用不占用数据库写事务。
- 解析成功时全部候选快照和 SKU 原子保存；解析失败不留下半套结果。
- 草稿、解析中、失败等非法状态不能通过空 SKU 请求绕过确认门禁。
- SKU 未知、跨商品、不可选、遗漏或重复时，任务状态和全部选择保持不变。
- 已知类别不一致时拒绝推进；类别缺失时记录警告并进入维度确认。
- API 响应不包含 canonical URL、原始 Provider payload 或敏感凭据。
- `0005` 可升级、回退并重新升级，数据库约束与 ORM metadata 一致。

## 已知限制

- 前端仍只有状态首页，没有商品输入和 SKU 确认页面。
- API 尚无用户身份、任务归属和多租户权限，只能作为本地开发基线。
- 商品解析同步执行 Fixture，不代表后续真实 Provider 的性能和可用性。
- 前端构建仍有大 chunk 警告，后续业务页面需要路由懒加载和依赖按需导入。

## 最终结论

**PASS**

M1-B 的代码、迁移、事务边界和本地质量门禁均已通过验收，可以归档并进入 M1 后续的
用户偏好、维度种子、动态维度和输入确认页面开发。该结论不扩大到明确列为范围外的生产
数据接入、鉴权、评论分析、异步编排或报告能力。
