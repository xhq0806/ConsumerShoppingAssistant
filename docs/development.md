# 开发指南

## 目录约定

- `backend/src/app/api`：HTTP 路由、middleware、ProblemDetails。
- `backend/src/app/core`：配置、日志、通用错误和 URL 安全。
- `backend/src/app/infrastructure`：数据库等技术基础设施。
- `backend/src/app/providers`：Commerce 与 LLM 外部能力契约和适配器。
- `backend/tests/unit`：纯逻辑单元测试。
- `backend/tests/contract`：Provider 与 LLM 共享契约。
- `backend/tests/integration`：PostgreSQL/Testcontainers 等集成测试。
- `frontend/src/api`：统一请求、ProblemDetails 和 Comparison API 类型。
- `frontend/src/stores`：Pinia 对比流程状态。
- `frontend/src/views/comparisons`：商品输入、商品确认、购买偏好、动态维度和任务进度页面。
- `docs/spikes`：高风险技术与合规预研。

## Windows 开发前置条件

建议安装 Docker Desktop，并确认：

```bash
docker version
docker compose version
python --version
node --version
```

Python 必须为 3.12。数据库集成测试使用 Testcontainers，需要 Docker daemon 正常运行。

## 环境变量

从根目录 `.env.example` 复制 `.env`。示例文件不得包含真实密钥。默认只允许：

```text
COMMERCE_PROVIDER=fixture
LLM_PROVIDER=fake
```

当前开发基线不接受真实淘宝 Cookie、Authorization、账号或登录态。DeepSeek Adapter 已
实现，但默认 `LLM_PROVIDER=fake`，未配置本地 API Key 时不会连接真实模型。

## 后端质量命令

```bash
cd backend
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -m "not integration"
python -m pytest -m integration tests/integration/db
python -m pytest
```

快速套件不访问 Docker；数据库套件使用 Testcontainers PostgreSQL 16。完整回归可直接执行
`python -m pytest`。

本项目为个人项目，当前以这些本地命令作为交付和归档门禁，不要求远端 CI 运行记录。

Windows 下也可以从项目根目录执行完整门禁：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify-local.ps1
```

该脚本要求后端和前端依赖已安装，并要求 Docker Desktop 可用于 PostgreSQL Testcontainers。

## 数据库迁移

```bash
cd backend
alembic upgrade head
alembic current
alembic check
```

`0001` 是 M0 空迁移基线；M1-A 通过 `0002`～`0004` 创建 16 张 T03/T04/T05
业务表；M1-B 通过 `0005` 增加创建幂等摘要、请求指纹、成对 CHECK 和部分唯一索引。
M1-D 通过 `0006` 写入通用和 Fixture 手机品类维度种子，不修改 Schema。当前 head 为
`0006`。Repository 不自行提交事务，由应用用例或 UnitOfWork 控制提交与回滚。

## M1-G 对比 API、Worker 与页面

```text
POST /api/v1/comparisons
POST /api/v1/comparisons/{comparison_id}/parse
GET  /api/v1/comparisons/{comparison_id}
POST /api/v1/comparisons/{comparison_id}/confirm-products
PUT  /api/v1/comparisons/{comparison_id}/preferences
POST /api/v1/comparisons/{comparison_id}/dimensions/recommendations
GET  /api/v1/comparisons/{comparison_id}/dimensions
POST /api/v1/comparisons/{comparison_id}/dimensions/confirm
POST /api/v1/comparisons/{comparison_id}/analysis/start
POST /api/v1/comparisons/{comparison_id}/analysis/retry
GET  /api/v1/comparisons/{comparison_id}/analysis/progress
GET  /api/v1/comparisons/{comparison_id}/report
```

- 创建接口在事务外规范化 URL，并支持不保存原始键的创建幂等。
- 解析接口同步调用 Fixture Provider；Provider 调用期间不持有数据库写事务。
- 详情接口只返回白名单字段、最新商品快照、SKU 和脱敏事件。
- 确认接口必须覆盖全部候选商品，并在基础类别可比性检查后进入维度确认阶段。
- 偏好接口整体替换评论窗口、预算、使用场景、关注点和禁忌项；只有
  `awaiting_dimension_confirmation` 状态允许保存。
- 偏好复用 `comparison_tasks.preferences` JSONB，不新增数据库迁移。
- 维度推荐仅使用已注册目录、共同品类、最新商品事实和受控关注点同义词，不调用 LLM。
- 首次生成会持久化选中与未选中的全部候选；重复生成不会覆盖既有候选。
- 确认请求按有序 code 整体保存，零维度被拒绝；成功后任务依次进入
  `ready_for_analysis` 和 `queued`。
- 进度页调用 start API 投递 Celery；重复消息通过任务根行锁和 queued 状态门禁安全忽略。
- Worker 在事务外获取 Fixture 评论，全部商品成功后才原子保存清洗后的 `raw_reviews`。
- 评论执行 NFKC、空白收敛、窗口过滤、受控无意义文本过滤和商品内稳定正文去重。
- 评论保存后进入 `processing/45`，Worker 随后以最多 20 条为一批调用 LLM analysis profile。
- 模型只使用已选维度，应用层拒绝批次外 ID、未知维度、重复关系和非连续原文证据。
- 每批提交注解、模型审计和已处理 review IDs；retry 从断点继续且不重新获取评论。
- Python 重建商品级与任务级计数、比例、覆盖率和置信度，最终推进到 `processing/75`。
- Provider unavailable/rate limit，以及 LLM timeout/rate limit/unavailable/invalid output 可 retry。
- processing/75 后创建 version=1 generating 报告并推进 reporting/80。
- report profile 只选择解释、claim 和来源；完整商品事实与指标值由 Python 构造。
- claim 来源在应用层对照 source catalog，并在 Repository 层再次校验当前任务归属。
- 数据缺失或 report 模型失败时发布 partial 报告并进入 partially_completed/100。
- 无数据警告时发布 completed 报告并进入 completed/100。
- API 尚无用户身份与任务归属控制，只能用于本地开发，不得直接公网开放。

前端路由：

```text
/                                      商品链接输入与解析
/comparisons/:id/confirm               商品事实与 SKU 确认
/comparisons/:id/preferences           评论范围与购买偏好
/comparisons/:id/dimensions            动态维度调整与确认
/comparisons/:id/progress              评论采集、智能注解与指标进度
/comparisons/:id/report                决策摘要、差异、完整对比与来源证据
```

- 页面恢复以路由中的任务 ID 和服务端详情为真源，不依赖 Pinia 内存状态。
- Vite 开发环境将 `/api` 代理到 `localhost:8000`。
- Nginx 容器将 `/api/` 代理到 `api:8000`，并使用 SPA fallback 支持深层路由刷新。
- 原始商品链接仅存在于创建前的表单内存中，不写入浏览器持久化。
- 维度页支持重点/其他可选、搜索、增删、拖拽、顺序按钮、理由和数据风险。
- 进度页自动启动 queued 或恢复 processing<100 的任务并每秒轮询；终态或 failed 时停止。
- 报告页只查询当前任务最新已发布报告，刷新恢复不依赖 Pinia 内存。

Compose 包含一次性 `migrate` 服务，API 和 Worker 仅在迁移成功后启动。Celery 同步 task
每次在自身事件循环内创建并释放 asyncpg engine，避免连续任务复用已关闭事件循环连接。

## 前端质量命令

```bash
cd frontend
npm ci
npm run typecheck
npm run test -- --run
npm run build
```

M1-G 的浏览器验收覆盖完整六步流程、真实 Celery/DeepSeek 调用、确定性 fallback、报告刷新
恢复、桌面端和 `390x844` 移动端布局。验收截图位于：

```text
docs/assets/m1g-report-desktop.png
docs/assets/m1g-report-mobile.png
```

## 新 Commerce Provider 规则

1. 实现 `CommerceDataProvider` Protocol。
2. 复用 `NormalizedProductUrl`、商品/评论 DTO 和统一 Provider 错误。
3. 原始 URL 必须先经过 `url_security.py` 与 `url_normalizer.py`。
4. HTTP 重定向必须逐跳重新校验，禁止自动跟随未知地址。
5. 新实现必须通过 `tests/contract/providers` 共享契约。
6. 未经 T07 正式授权与合规批准，不得创建或启用真实淘宝 Provider。

## Fixture 数据规则

- 只能使用合成或经批准的不可逆脱敏数据；
- 禁止复制真实商品详情、真实评论、用户名、手机号、地址、订单号、Cookie 或 Token；
- Fixture ID 只能映射到打包文件，不能允许用户输入任意本地路径；
- 应覆盖多 SKU、字段缺失、空评论、30/60 天、重复、模板文本、prompt injection、限流、超时和无效响应。

## 新 LLM Adapter 规则

- 业务代码只调用 `LLMGateway`，禁止直接导入具体供应商 SDK；
- 密钥只从环境变量或 Secret Manager 读取；
- 审计只记录 purpose、模型、耗时、token、状态、错误码、trace ID、重试次数和 prompt version；
- 禁止记录完整 Prompt、评论、响应正文、Cookie、Authorization 或 API Key；
- Adapter 必须通过结构化输出、超时、重试、失败和审计契约测试。

### DeepSeek 配置

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=由本地开发者填写
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_ANALYSIS_MODEL=deepseek-v4-flash
DEEPSEEK_REPORT_MODEL=deepseek-v4-pro
DEEPSEEK_ANALYSIS_THINKING=false
DEEPSEEK_REPORT_THINKING=true
DEEPSEEK_REPORT_REASONING_EFFORT=high
DEEPSEEK_REPORT_TIMEOUT_SECONDS=120
DEEPSEEK_REPORT_MAX_RETRIES=0
```

- analysis profile 使用 `/chat/completions`、`response_format=json_object` 和非思考模式。
- report profile 使用 V4 Pro、思考模式、high reasoning effort、120 秒单次超时和 0 次重试。
- Adapter 自动增加只输出 JSON 的系统约束，但业务 Prompt 仍需声明具体字段和含义。
- DeepSeek 空 content、无效 JSON 或 Pydantic 校验失败继续由 Gateway 重试。
- 400/422 无效请求、401/403 鉴权和 402 额度不足不重试；429、5xx、连接错误和超时映射为受控 LLM 错误。
- Adapter 不保存 `reasoning_content`，审计只记录 provider/model/token/时延/状态。
- M1-F 评论注解通过 analysis profile 接入；M1-G 报告通过 report profile 接入。
- report 输出无效或超时时，系统记录错误 model run 并发布确定性 partial 基础报告。

配置完成后的最小连通性检查：

```bash
python -m app.providers.llm.deepseek_smoke
```

该命令会产生一次最小真实 API 调用，只输出非敏感摘要。

## 淘宝生产发布门禁

`docs/spikes/taobao-data-provider.md` 当前状态为 blocked。在取得应用审批、具体接口权限、数据处理条款和书面合规结论前：

- T09 不得实施；
- 不得开放真实淘宝链接解析；
- 不得压测或采集真实淘宝数据；
- 只能使用 Fixture 做内部开发和测试。
