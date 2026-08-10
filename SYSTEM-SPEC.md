# Consumer Shopping Assistant — 系统行为规格

> 最后更新：2026-08-10
> 当前版本：v0.4.0-m1c
> 维护方式：仅记录已经实现并经过验证的系统行为；计划能力不得提前写入本文件
> M0 验收：`docs/m0-verification.md`（PASS_WITH_CONCERNS）
> M1-A 验收：`docs/m1a-verification.md`（PASS_WITH_CONCERNS）
> M1-B 验收：`docs/m1b-verification.md`（PASS）
> M1-C 验收：`docs/m1c-verification.md`（PASS）
> 验收方式：个人项目以可复现的本地完整质量门禁作为交付证据，不要求远端 CI 成功记录
> 验收证据：M0 见 `docs/m0-verification.md`；M1-A 见 `docs/m1a-verification.md`；M1-B 见 `docs/m1b-verification.md`；M1-C 见 `docs/m1c-verification.md`

## 1. 功能清单

| 功能 | 版本 | 状态 | 添加日期 | 关联规格 |
|---|---|---|---|---|
| 全核运行骨架 | v0.1.0-m0 | ✅ 已实现 | 2026-08-05 | `docs/specs/m0-engineering-foundation.md` |
| 健康检查与统一错误 | v0.1.0-m0 | ✅ 已实现 | 2026-08-05 | `docs/specs/m0-engineering-foundation.md` |
| 异步数据库与迁移基线 | v0.1.0-m0 | ✅ 已实现 | 2026-08-05 | `docs/specs/m0-engineering-foundation.md` |
| T03 对比任务与商品数据模型 | v0.2.0-m1a | ✅ 已实现 | 2026-08-06 | `docs/specs/m1a-business-data-models.md` |
| T04 品牌与维度目录模型 | v0.2.0-m1a | ✅ 已实现 | 2026-08-06 | `docs/specs/m1a-business-data-models.md` |
| T05 评论、指标、报告与模型审计模型 | v0.2.0-m1a | ✅ 已实现 | 2026-08-06 | `docs/specs/m1a-business-data-models.md` |
| T11 对比草稿、Fixture 解析与详情查询 | v0.3.0-m1b | ✅ 已实现 | 2026-08-06 | `docs/specs/comparison-draft-confirmation.md` |
| T12 商品/SKU 确认与基础可比性 | v0.3.0-m1b | ✅ 已实现 | 2026-08-06 | `docs/specs/comparison-draft-confirmation.md` |
| T26 商品输入、解析与确认前端 | v0.4.0-m1c | ✅ 已实现 | 2026-08-10 | `docs/specs/m1c-shopping-input-preferences.md` |
| T13 用户偏好保存与恢复 | v0.4.0-m1c | ✅ 已实现 | 2026-08-10 | `docs/specs/m1c-shopping-input-preferences.md` |
| 淘宝商品 URL 安全 | v0.1.0-m0 | ✅ 已实现 | 2026-08-05 | `docs/specs/m0-engineering-foundation.md` |
| Commerce Provider 与 Fixture | v0.1.0-m0 | ✅ 已实现 | 2026-08-05 | `docs/specs/m0-engineering-foundation.md` |
| 供应商中立 LLM Gateway | v0.1.0-m0 | ✅ 已实现 | 2026-08-05 | `docs/specs/m0-engineering-foundation.md` |
| 淘宝生产接入门禁 | v0.1.0-m0 | 🚫 Blocked | 2026-08-05 | `docs/spikes/taobao-data-provider.md` |
| 基础 CI 与开发文档 | v0.1.0-m0 | ✅ 已实现 | 2026-08-05 | `docs/specs/m0-engineering-foundation.md` |

## 2. 系统定位与当前边界

当前系统是购物决策助手的 M1-C 本地开发基线，不是完整购物比较产品。系统在 M0 运行底座、M1-A 数据模型和 M1-B Comparison API 之上，已经具备 T11/T12/T26/T13 的首个可操作闭环：输入 2～3 个候选商品、使用 Fixture Provider 解析商品、确认 SKU，并保存和恢复评论窗口、预算、使用场景、关注点和禁忌项。

当前迁移链为 `0001 -> 0002 -> 0003 -> 0004 -> 0005`，PostgreSQL 仍包含 16 张业务表；`0005` 为 `comparison_tasks` 增加创建幂等摘要和请求指纹约束。以下行为仍未实现：

- 品牌资料采集、维度种子、动态维度推荐和维度确认接口；
- 评论清洗、注解执行和指标计算算法；
- LangGraph 工作流、Celery 业务任务、任务进度推送和保留期清理；
- 报告生成、图表、报告追问业务和管理端；
- 用户身份、任务归属、多租户权限和匿名访问凭证；
- 真实淘宝生产数据 Provider；
- 真实 LLM 供应商适配器。

上述能力必须通过后续里程碑实现并验收后，才能合并到本文件。

## 3. 全核运行骨架

### 3.1 运行服务

Docker Compose 当前定义五个目标服务：

| 服务 | 当前行为 |
|---|---|
| `postgres` | 使用 PostgreSQL 16，保存 Alembic 迁移状态并参与 readiness 检查；`0005` head 定义 16 张业务表和 M1-B 创建幂等约束；M1-B Comparison API 通过短事务写入任务、候选、快照、SKU 和事件；容器内不暴露宿主端口 |
| `redis` | 使用 Redis 7；Celery 配置将其不同 DB 用作 broker/result backend，并参与 readiness 检查；容器内不暴露宿主端口 |
| `api` | 使用 Python 3.12 运行 FastAPI/Uvicorn，提供 M1-C Comparison 与偏好 API，开发环境暴露宿主端口 8000 |
| `worker` | 与 API 共享后端代码和镜像，运行 Celery Worker；不暴露 HTTP 端口 |
| `web` | 构建 Vue 3 SPA，通过 Nginx 暴露宿主端口 5173，并代理 `/api` 与支持 history fallback |

Compose 项目名固定为：

```text
consumer-shopping-assistant
```

Compose 文件与环境文件关系：

```text
Compose：docker/docker-compose.yml
env_file：../.env（相对于 docker/）
```

标准操作入口是项目根目录下的：

```bash
docker compose -f docker/docker-compose.yml <command>
```

### 3.2 模块边界

- API 和 Worker 共享 `backend/src/app` 中的配置、错误、数据库、领域规则和 Provider 契约。
- API 负责健康检查、统一错误以及 M1-C 对比草稿、解析、详情、商品确认和偏好更新请求；Worker 当前只提供基础 Celery 运行能力和无业务副作用的 smoke task，尚未编排分析业务。
- `app.domain` 定义任务状态、商品、品牌、维度、评论、指标、报告 claim 和模型运行的纯领域校验；不依赖 API、Celery、LangGraph 或供应商 SDK。
- `app.infrastructure.db.models` 定义 16 张业务表；按 comparison、catalog、analysis、report、model run 划分的 Repository 负责查询和持久化，但不自行提交事务。
- PostgreSQL 是业务持久化真源；Redis 不得成为任务、指标或报告的唯一持久状态。
- Web 提供商品输入、商品/SKU 确认和购买偏好三步流程；任务恢复以路由 ID 和服务端详情为真源。

### 3.3 默认适配器

开发环境默认配置：

```text
COMMERCE_PROVIDER=fixture
LLM_PROVIDER=fake
```

未显式变更并通过对应验收前，系统不得默认连接真实淘宝数据源或真实 LLM 服务。

## 4. 配置行为

### 4.1 配置来源

后端使用 Pydantic Settings 读取环境变量；`.env.example` 只允许包含无敏感占位值。密钥、Cookie、Authorization 和用户登录态不得写入仓库。

### 4.2 已定义配置

当前核心配置包括：

- 应用环境、Debug、API host/port；
- PostgreSQL async/sync URL；
- Redis URL；
- Celery broker/result backend；
- Commerce Provider；
- LLM Provider、模型、超时和重试次数；
- 淘宝允许域名。

`TAOBAO_ALLOWED_HOSTS` 使用逗号分隔字符串，例如：

```text
item.taobao.com,detail.tmall.com
```

系统使用 `NoDecode` 禁止 Pydantic 对该 tuple 字段预先执行 JSON 解码，再由 validator 去除空白、转换小写并生成 host 元组。

## 5. 健康检查与统一错误

### 5.1 存活检查

```http
GET /health/live
```

正常响应：

```json
{"status":"ok"}
```

行为约束：

- 仅表示 API 进程存活；
- 不依赖 PostgreSQL 或 Redis；
- PostgreSQL 或 Redis 停止时仍返回 HTTP 200。

### 5.2 就绪检查

```http
GET /health/ready
```

正常行为：

- 执行 PostgreSQL `SELECT 1`；
- 执行 Redis `PING`；
- 两项均成功时返回 HTTP 200 和 `{"status":"ready"}`。

依赖故障行为：

- PostgreSQL 或 Redis 任一不可用时返回 HTTP 503；
- 响应媒体类型为 `application/problem+json`；
- 返回 `PROVIDER_UNAVAILABLE`，且不泄露连接串和内部堆栈；
- 依赖恢复后再次返回 HTTP 200。

### 5.3 Trace ID

- 服务端为每个 HTTP 请求生成新的 trace ID；
- trace ID 写入 `X-Trace-Id` 响应头；
- 错误响应体的 `trace_id` 必须与响应头一致；
- 系统不直接信任客户端提供的任意 trace ID。

### 5.4 ProblemDetails

统一错误模型字段：

```text
type
title
status
code
detail
trace_id
field_errors
metadata
```

当前错误映射覆盖：

- 请求参数校验错误；
- 领域冲突；
- Provider 不可用、限流、资源不存在和无效响应；
- URL 安全拒绝；
- LLM 超时和结构化输出无效；
- HTTP 404/405；
- 未捕获异常。

未捕获异常统一返回 `INTERNAL_ERROR`，不得向客户端返回内部异常文本或堆栈。

## 6. 数据库与迁移基线

### 6.1 数据库访问

- 使用 SQLAlchemy 2.x Async Engine 和 async session factory；
- Engine 启用连接健康检查；
- 应用关闭时释放 Engine；
- Repository 只负责查询与持久化操作，不自行提交事务；
- `UnitOfWork` 在成功退出时提交，在异常退出时回滚，并始终关闭 Session。

### 6.2 ORM 与业务表基线

统一 `DeclarativeBase` 和约束命名约定承载 16 张业务表：

- T03：`comparison_tasks`、`comparison_products`、`product_snapshots`、`product_skus`、`task_events`；
- T04：`brand_profiles`、`brand_sources`、`dimension_definitions`、`task_dimensions`；
- T05：`raw_reviews`、`review_annotations`、`analysis_metrics`、`comparison_reports`、`report_claims`、`followup_messages`、`model_runs`。

任务是私有数据子图的删除根；商品、评论、注解、指标、报告、claim、追问和模型运行按受控关系删除。品牌与维度是共享目录，任务删除不得级联删除；仍被引用的目录记录受外键保护。

结构性不变量由数据库外键、唯一约束、CHECK 和索引保障；状态转换、已注册维度、评论原文证据、来源引用解析和报告发布门禁由领域层保障。

### 6.3 Alembic 基线

当前迁移版本：

```text
0005 (head)
```

迁移链为 `0001 -> 0002 -> 0003 -> 0004 -> 0005`：`0001` 是 M0 空基线，`0002`、`0003`、`0004` 分别创建 T03、T04、T05 模型；`0005` 为创建请求增加不可逆幂等摘要、请求指纹、成对 CHECK 和非空摘要部分唯一索引。容器镜像必须包含 `alembic.ini` 与 `alembic/`。

已在 PostgreSQL 16 空库验证：

- `alembic upgrade head`、`alembic current`、`alembic check`；
- head 为 `0005`，业务表数量保持 16；
- M1-B 生命周期覆盖 `0005 -> 0004 -> 0005`；
- 完整生命周期覆盖 `alembic downgrade 0001` 后重新 `upgrade head`；
- 重新升级后再次执行 `current` 与 `check`。

## 7. 淘宝商品 URL 安全

### 7.1 支持范围

当前允许 host：

```text
item.taobao.com
detail.tmall.com
```

白名单使用精确 host 匹配，不使用模糊后缀判断。

### 7.2 拒绝规则

系统拒绝：

- HTTP/HTTPS 之外的协议；
- 缺失 host、无效端口和非 80/443 端口；
- 含 username/password 的 URL；
- 非白名单 host、后缀欺骗和 user-info 混淆；
- 尾随点域名；
- IP 字面量商品链接；
- DNS 解析到 loopback、private、link-local、unspecified、multicast、reserved、CGNAT、metadata IP 或 IPv4-mapped IPv6；
- 缺少唯一数字商品 ID 的淘宝 URL。

### 7.3 规范化结果

安全校验通过后生成不可变 `NormalizedProductUrl`，包含：

- canonical URL；
- platform=`taobao`；
- host；
- external product ID；
- SHA-256 URL fingerprint。

规范化过程移除 fragment 和非允许查询参数，仅保留商品识别所需的 `id`。后续 Commerce Provider 请求使用 `NormalizedProductUrl`，不直接使用原始 URL。

## 8. Commerce Provider 与 Fixture

### 8.1 Provider 契约

```python
class CommerceDataProvider(Protocol):
    async def normalize_url(self, url: str) -> NormalizedProductUrl: ...
    async def fetch_product(self, request: ProductRequest) -> ProductProviderResult: ...
    async def fetch_reviews(self, request: ReviewFetchRequest) -> ReviewProviderResult: ...
```

DTO 使用不可变 Pydantic 模型，当前覆盖：

- 规范化商品 URL；
- 来源引用；
- 商品、SKU 和字段缺失；
- 评论、评分、SKU 文本；
- 近 30/60 天请求；
- 实际评论覆盖范围、获取数量和 warnings。

`ReviewProviderResult.fetched_count` 必须等于实际 `reviews` 数量。

### 8.2 Fixture 行为

`FixtureCommerceDataProvider`：

- 只从打包的固定 JSON 读取合成数据；
- 不执行外部网络请求；
- 不允许用户输入任意本地文件路径；
- 支持正常商品、多 SKU、字段缺失、空评论、30/60 天、重复评论、Prompt Injection 普通文本、商品不存在、限流和超时场景；
- 将受控错误映射为统一 Provider 错误。

Fixture 数据不得包含真实淘宝商品、真实评论、账号、Cookie、订单号或可识别个人信息。

## 9. LLM Gateway

### 9.1 当前供应商边界

M0 只启用 `fake` LLM Provider。模型工厂不创建真实供应商客户端；业务模块不得直接依赖具体模型供应商 SDK。

### 9.2 结构化调用

`LLMGateway.invoke_structured`：

- 接收 purpose、LangChain messages、trace ID、Prompt version、timeout 和最大重试次数；
- 使用调用方提供的 Pydantic response model 校验响应；
- 支持字符串 JSON 和字典响应内容；
- 返回校验后的对象、provider、model、token usage、latency、attempt count 和 audit event ID。

### 9.3 超时与重试

- 单次调用受 `timeout_seconds` 限制；
- 超时映射为 `LLM_TIMEOUT`；
- JSON、类型或 Pydantic 校验失败映射为 `LLM_STRUCTURED_OUTPUT_INVALID`；
- 总尝试次数为首次调用加 `max_retries`；配置约束为 timeout `>0且<=120` 秒、重试 `0..5`，默认分别为 10 秒和 2 次重试；
- 重试耗尽后记录失败审计并抛出统一错误。

### 9.4 审计

系统提供内存审计、结构化日志审计和 `model_runs` SQLAlchemy 审计 sink。审计记录：

- purpose、provider、model；
- trace ID 和 Prompt version；
- 成功/失败状态、错误码；
- latency、attempts 和 token usage。

审计不得记录完整 Prompt、完整评论、模型响应正文、Cookie、Authorization 或 API Key。`model_runs` 只保存 purpose、provider、model、Prompt version、token、时延、attempts、状态、错误码和必要关联；首次 Gateway 调用的 attempts 至少为 1。测试继续通过内存 sink 断言审计字段和正文脱敏，持久化 sink 复用同一 `LLMAuditSink` Protocol。

## 10. 前端基线

当前前端已经集成：

- Vue 3、TypeScript、Vite；
- Pinia、Vue Router；
- Ant Design Vue；
- ECharts；
- Vitest 和 Vue Test Utils。

当前路由：

```text
/                                      商品链接输入、任务创建和 Fixture 解析
/comparisons/:id/confirm               商品事实与 SKU 确认
/comparisons/:id/preferences           评论窗口与购买偏好
```

- 页面通过统一 `src/api/request.ts` 解析 JSON、超时和 ProblemDetails。
- Pinia store 统一编排创建、解析、详情恢复、商品确认和偏好更新。
- 路由中的任务 ID 是页面恢复真源；localStorage 只保存最近任务 ID，不保存原始商品链接。
- Vite 将 `/api` 代理到本地 API；Nginx 容器代理 `/api/` 并为深层路由提供 SPA fallback。
- Fixture 图片不可用时显示本地占位视觉，不发起外部 `.invalid` 图片请求。

## 11. 测试与交付基线

### 11.1 后端

当前质量门禁：

- Ruff lint；
- Ruff format check；
- mypy strict；
- Pytest 单元、API 和 Provider/LLM 契约测试；
- Testcontainers PostgreSQL 集成测试；
- Alembic upgrade/current/check。

M1-C 本地完整验收为 149 项后端测试全部通过；Ruff、format 和 mypy 同时通过，Alembic head
保持 `0005` 且无 metadata drift。

### 11.2 前端

当前质量门禁：

- TypeScript/Vue typecheck；
- Vitest；
- Vite production build。

M1-C 前端 typecheck、3 个 Vitest 文件共 8 项测试和 production build 全部通过。业务页面已
采用路由懒加载；Ant Design Vue 全局导入仍使主 chunk 约 1.53 MB，属于非阻断构建警告。
浏览器已验证桌面端和 `390x844` 移动端偏好保存、刷新恢复、无横向溢出和控制台零错误。

### 11.3 本地交付与 CI 配置

仓库已包含 GitHub Actions 基础工作流配置，覆盖：

- Python 3.12 后端质量检查；
- PostgreSQL 16 migration 和数据库测试；
- Node.js 22 前端检查、测试和构建；
- Docker Compose 配置校验。

该仓库当前按个人项目维护，不要求 GitHub Actions 远端运行作为验收前提。本地 Ruff、format、mypy、Pytest、Testcontainers PostgreSQL、Alembic、前端 typecheck/test/build、Compose 和浏览器验收是当前交付门禁。M1-C 的执行环境、命令和结果见 `docs/m1c-verification.md`。

## 12. 淘宝生产接入门禁

当前状态：

```text
blocked
```

在取得正式应用审批、具体接口权限、评论数据处理条款和书面合规结论前：

- 不实现或启用生产 `TaobaoDataProvider`；
- 不开放真实淘宝商品和评论分析；
- 不使用登录态、Cookie、验证码绕过、代理池、浏览器隐蔽采集或反爬规避；
- 不将未授权页面抓取描述为开放 API；
- 不把真实评论复制进 Fixture 或测试资产。

Fixture 模式可以继续用于 M1/M2 内部开发和自动化测试。

## 13. 当前数据与安全不变量

1. Python 运行版本保持 `>=3.12,<3.13`。
2. API 与 Worker 共享后端代码和核心契约，但以独立进程运行。
3. PostgreSQL 已有 16 张 M1-A 业务表并作为持久化真源；Redis 不成为任务、指标或报告的唯一持久状态。
4. `/health/live` 不依赖 PostgreSQL 和 Redis。
5. `/health/ready` 必须同时验证 PostgreSQL 和 Redis。
6. 所有 API 错误继续使用 ProblemDetails，并包含 `code`、`detail`、`trace_id`。
7. 商品 URL 必须先通过安全校验和规范化，Provider 不直接使用原始 URL。
8. Fixture 与未来真实 Provider 复用 Commerce DTO 和契约测试。
9. 统计数字由确定性程序计算，LLM 不成为统计真源。
10. LLM 调用继续通过供应商中立 Gateway，且审计不保存敏感正文和凭据。
11. 真实淘宝 Provider 继续受 T07 合规门禁约束。
12. 数据库 Schema 变化必须通过 Alembic，迁移后 `alembic check` 不得存在未记录差异。
13. Compose 项目名保持 `consumer-shopping-assistant`，避免与其他项目共享命名空间。
14. `.env`、Cookie、Authorization、API Key 和真实个人数据不得提交到仓库。
15. M1-B 创建幂等只保存摘要和请求指纹，不保存原始 `Idempotency-Key`。
16. M1-B Provider 调用不得位于数据库写事务内，解析结果必须全部提交或全部不提交。
17. M1-B API 尚无用户身份和任务归属控制，不得直接作为公网生产接口。
18. M1-C 偏好只允许在 `awaiting_dimension_confirmation` 状态整体替换；相同内容可幂等保存。
19. M1-C 原始商品链接不得写入浏览器持久化；页面恢复必须通过任务 ID 查询服务端。
20. M1-C 偏好事件不得保存用户文本正文，只允许记录评论窗口和条目数量。

## 14. M1-A 领域与 Repository 边界

### 14.1 已验证领域规则

- 对比任务状态只能按显式状态图转换；评论窗口仅允许 30 或 60 天，进度限制为 0～100，候选商品数量与重复项受领域校验。
- 候选商品只接受既有 `NormalizedProductUrl` 安全边界；价格、SKU 选择和 `SourceReference` 白名单映射受领域校验。
- 品牌标准名、字段级来源和冲突来源可表达；未知或冲突品牌事实不得凭模型常识补齐后用于推荐。
- 维度 code 必须规范化并解析为已注册目录；`rankable` 与 `affects_recommendation` 独立，品牌成立年份不影响推荐。
- 评论评分、情感、置信度和原文连续子串证据受校验；同一评论可以关联多个已注册维度。
- 指标来源引用必须非空；统计数量、比例、价格换算、趋势、样本量和置信度仍须由后续确定性算法计算，LLM 不是真源。
- 报告版本和 claim 来源受校验；无有效来源的 claim 不得进入可发布报告。模型运行 attempts 至少为 1。

### 14.2 Repository 与事务边界

- `ComparisonRepository` 管理任务、候选商品、快照、SKU 和事件的持久化入口。
- `CatalogRepository` 管理品牌、字段来源、维度目录和任务维度。
- `AnalysisRepository` 管理评论、注解和指标；`ReportRepository` 管理版本报告、claim 与追问；`ModelRunRepository` 和 `SQLAlchemyLLMAuditSink` 管理模型审计。
- DTO 入库 seam 只接受既有 Commerce DTO 和安全来源映射，不接受任意 raw payload。
- Repository 只执行查询、add/flush 等持久化操作，不自行 commit；事务由 `UnitOfWork` 或调用方控制。

### 14.3 安全边界与未实现能力

- JSON、事件、评论、来源和模型审计字段不得保存 Cookie、Authorization、API Key、用户登录态、完整 Prompt、完整模型响应或未经白名单过滤的 Provider payload。
- 外部商品、评论和模型文本始终是不可信数据，持久化不赋予其指令或工具调用权限。
- M1-A 没有新增业务 API、Celery 业务编排、LangGraph 工作流、分析算法、业务前端、真实淘宝 Provider 或真实 LLM 适配器；16 张表和 Repository 的存在不表示这些端到端能力已经实现。
- M1-C 已在上述基线之上提供商品输入、商品确认与偏好页面，但仍未实现分析编排、动态维度、报告或生产外部 Provider。

## 15. M1-B 对比草稿与商品确认

### 15.1 HTTP 契约

当前提供：

```text
POST /api/v1/comparisons
POST /api/v1/comparisons/{comparison_id}/parse
GET  /api/v1/comparisons/{comparison_id}
POST /api/v1/comparisons/{comparison_id}/confirm-products
```

- 请求和响应 Schema 禁止额外字段，并使用显式白名单映射。
- 创建接口返回 HTTP 201；查询、解析和确认成功返回 HTTP 200。
- 输入错误、状态冲突、Provider 错误和资源不存在继续使用统一 ProblemDetails。
- 响应不包含原始提交 URL、canonical URL、完整 Provider payload、敏感凭据或内部堆栈。

### 15.2 创建与幂等

- 创建请求只接受 2～3 个候选商品和 30/60 天评论窗口。
- URL 在数据库事务外完成安全校验和规范化；规范化后重复商品或安全指纹重复时拒绝创建。
- 成功创建 `draft` 任务、按输入顺序保存候选商品并记录脱敏事件。
- 可选 `Idempotency-Key` 去除首尾空白后长度必须为 8～128。
- 数据库只保存 SHA-256 幂等摘要和请求指纹；相同键与相同载荷返回同一任务，相同键与不同载荷返回冲突。
- 部分唯一索引处理并发相同键创建；历史 M1-A 任务允许两个幂等字段同时为空。

### 15.3 Fixture 商品解析

- 只有 `draft` 任务可首次启动解析。
- 系统先提交 `parsing` 状态，再在事务外按候选顺序调用 Fixture Provider。
- 全部候选成功时，单个事务保存所有最新快照和 SKU，并进入 `awaiting_product_confirmation`。
- 任一受控 Provider 错误使任务进入 `failed`，失败候选标记为 `failed`，并记录受控错误码和脱敏事件。
- 解析失败不会保存本次调用产生的半套快照或 SKU；`failed` 任务不允许重新解析。

### 15.4 详情与商品确认

- 详情查询只返回未删除任务；商品按 `position` 升序，事件按创建时间升序。
- 每个商品返回最新快照、SKU、解析状态和当前已选 SKU。
- 确认请求必须恰好覆盖任务内全部候选商品，不得重复或包含任务外商品。
- 有 SKU 的商品必须选择一个存在、归属正确且可选的 SKU；无 SKU 商品必须提交空选择。
- 已知类别经 Unicode NFKC、大小写折叠和空白归一化后不一致时拒绝推进。
- 类别缺失不阻断确认，但返回并持久化受控警告。
- 成功确认后任务进入 `awaiting_dimension_confirmation`。
- 只有处于 `awaiting_dimension_confirmation` 且全部选择一致时，重复确认才作为幂等重放；其他状态返回冲突。

### 15.5 边界

- M1-B 同步使用合成 Fixture，不连接真实淘宝或真实 LLM。
- M1-B 不获取评论，不实现用户偏好、动态维度、评论分析、指标、报告、追问、Celery、LangGraph 或业务前端。
- M1-B 不包含用户身份、任务归属和多租户权限，仅作为本地开发基线。

## 16. M1-C 商品输入与用户偏好闭环

### 16.1 HTTP 与偏好契约

M1-C 在 M1-B 接口之外新增：

```text
PUT /api/v1/comparisons/{comparison_id}/preferences
```

- 请求整体替换 `review_window_days`、预算和偏好文本列表，禁止额外字段。
- 预算使用 Decimal，允许只填写上限；金额范围为 0～1,000,000，上限不得低于下限。
- 使用场景为 1～5 项，关注点为 1～8 项，禁忌项为 0～8 项。
- 文本执行 trim、Unicode NFKC、空值拒绝、稳定去重和单项 80 字限制。
- 只有 `awaiting_dimension_confirmation` 任务允许保存；相同规范化内容可幂等重放。
- 偏好复用 `comparison_tasks.preferences` JSONB，迁移 head 保持 `0005`。
- 更新事件只记录评论窗口和各列表数量，不记录用户输入正文。

### 16.2 Web 流程与恢复

1. 根页面输入 2～3 个 Fixture 商品链接并创建、解析任务。
2. 确认页查询最新详情，展示商品事实与 SKU，提交全部商品选择。
3. 偏好页查询详情并回填评论窗口、预算和偏好列表。
4. 保存成功后仍停留在维度确认阶段，并显示下一里程碑边界。
5. 确认页和偏好页可直接刷新；恢复不依赖 Pinia 内存状态。

### 16.3 运行代理与边界

- 前端只通过相对 `/api` 访问后端；Vite 和 Nginx 分别提供开发与容器代理。
- Nginx 使用 `try_files` 支持 Vue history 深层路由刷新。
- 原始商品链接只存在于创建前表单内存，不进入 localStorage。
- 无效 Fixture 图片显示本地占位视觉，不执行真实网络请求。
- 当前无身份、任务归属和访问凭证控制，只能用于本地开发。
- M1-C 不实现动态维度、评论分析、异步编排、报告或真实淘宝 Provider。
