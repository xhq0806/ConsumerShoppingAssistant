# M1-B 对比草稿与商品确认流程

> 归档日期：2026-08-06
> 原始 spec：`changes/archive/2026-08-06-comparison-draft-confirmation/spec.md`
> 验收报告：`docs/m1b-verification.md`

## 功能描述

M1-B 将既有淘宝 URL 安全校验、Fixture Commerce Provider、任务数据模型和
Repository 组合为首个可验证业务闭环。调用方可以创建包含 2～3 个候选商品的对比草稿，
同步解析合成商品数据，查询任务聚合详情，确认全部商品的 SKU，并在基础类别可比性检查
通过后进入维度确认阶段。

该里程碑只提供后端开发基线，不包含用户鉴权、业务前端、评论分析、异步任务编排或真实
淘宝数据接入。

## 核心流程

1. 创建请求提交 2～3 个商品 URL、30/60 天评论窗口和可选 `Idempotency-Key`。
2. 应用服务在数据库事务外完成 URL 安全校验、规范化和重复候选检查。
3. 短事务原子创建 `draft` 任务、候选商品和脱敏事件；相同幂等键与相同载荷返回同一任务。
4. `draft` 任务进入 `parsing` 后，在事务外按候选顺序调用 Fixture Provider。
5. 全部解析成功时，单个事务保存所有商品快照和 SKU，并进入
   `awaiting_product_confirmation`；任一 Provider 失败时任务进入 `failed`，不保存半套结果。
6. 详情查询按商品位置和事件时间稳定排序，只返回白名单字段与最新商品快照。
7. 商品确认请求必须恰好覆盖任务内全部候选；有 SKU 的商品必须选择合法且可选的 SKU，
   无 SKU 商品必须提交空选择。
8. 已知类别不一致时拒绝推进；类别信息缺失时记录受控警告并允许进入
   `awaiting_dimension_confirmation`。
9. 只有已成功进入维度确认状态且提交内容与当前选择一致时，重复确认才作为幂等重放返回。

## 边界约束

- API 位于 `/api/v1/comparisons`，仅作为后续鉴权接入前的开发基线，不得直接公网开放。
- 解析同步使用合成 Fixture，不调用真实淘宝网络，也不使用 Cookie、账号、Token 或登录态。
- Provider 调用期间不得持有数据库写事务；解析结果必须全部提交或全部不提交。
- 幂等键去除首尾空白后长度为 8～128，只保存不可逆摘要，不保存原始键。
- 数据库不保存原始提交 URL、完整 Provider payload、敏感 query、凭据或内部堆栈。
- M1-B 不获取评论，不实现用户偏好、动态维度、品牌采集、指标、报告、追问、Celery、
  LangGraph 或业务前端。
- `failed` 任务不允许重新解析；调用方需要创建新任务。

## 代码索引

### 关键文件

| 文件路径 | 职责 |
|---|---|
| `backend/src/app/api/comparisons.py` | 创建、解析、详情和确认 HTTP 路由及响应映射 |
| `backend/src/app/api/schemas/comparisons.py` | M1-B 请求和响应白名单 Schema |
| `backend/src/app/api/dependencies.py` | Fixture Provider、UnitOfWork 和应用服务依赖组装 |
| `backend/src/app/application/comparisons.py` | 草稿创建、解析、查询、确认和事务编排 |
| `backend/src/app/domain/comparisons/__init__.py` | 幂等、确认集合和基础可比性纯领域规则 |
| `backend/src/app/infrastructure/db/comparison_repository.py` | 聚合锁定、幂等查询、快照/SKU 和事件持久化 |
| `backend/src/app/infrastructure/db/models/comparison.py` | 对比任务幂等字段和 ORM 状态门禁 |
| `backend/alembic/versions/0005_add_m1b_comparison_idempotency.py` | M1-B 幂等字段、CHECK 和部分唯一索引迁移 |

### 接口定义

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/v1/comparisons` | POST | 创建对比草稿或返回创建幂等重放结果 |
| `/api/v1/comparisons/{comparison_id}/parse` | POST | 使用 Fixture 解析全部候选商品 |
| `/api/v1/comparisons/{comparison_id}` | GET | 查询任务、候选、最新快照、SKU 和事件 |
| `/api/v1/comparisons/{comparison_id}/confirm-products` | POST | 原子确认全部商品/SKU 并执行基础可比性检查 |

### 外部依赖

| 包/服务 | 用途 | 备注 |
|---|---|---|
| FastAPI / Pydantic | HTTP 契约和输入输出校验 | 沿用 M0 基线 |
| SQLAlchemy / Alembic | 聚合持久化、行锁和迁移 | 当前 head 为 `0005` |
| PostgreSQL 16 | 业务状态持久化真源 | 集成测试使用 Testcontainers |
| Fixture Commerce Provider | 合成商品与 SKU 解析 | 不执行外部网络请求 |
