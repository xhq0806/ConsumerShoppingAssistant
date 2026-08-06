# 开发指南

## 目录约定

- `backend/src/app/api`：HTTP 路由、middleware、ProblemDetails。
- `backend/src/app/core`：配置、日志、通用错误和 URL 安全。
- `backend/src/app/infrastructure`：数据库等技术基础设施。
- `backend/src/app/providers`：Commerce 与 LLM 外部能力契约和适配器。
- `backend/tests/unit`：纯逻辑单元测试。
- `backend/tests/contract`：Provider 与 LLM 共享契约。
- `backend/tests/integration`：PostgreSQL/Testcontainers 等集成测试。
- `frontend/src`：Vue SPA。
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

当前开发基线不接受真实淘宝 Cookie、Authorization、账号或登录态。真实 LLM 供应商也尚未启用。

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
当前 head 为 `0005`。Repository 不自行提交事务，由应用用例或 UnitOfWork 控制提交与回滚。

## M1-B 对比 API

```text
POST /api/v1/comparisons
POST /api/v1/comparisons/{comparison_id}/parse
GET  /api/v1/comparisons/{comparison_id}
POST /api/v1/comparisons/{comparison_id}/confirm-products
```

- 创建接口在事务外规范化 URL，并支持不保存原始键的创建幂等。
- 解析接口同步调用 Fixture Provider；Provider 调用期间不持有数据库写事务。
- 详情接口只返回白名单字段、最新商品快照、SKU 和脱敏事件。
- 确认接口必须覆盖全部候选商品，并在基础类别可比性检查后进入维度确认阶段。
- API 尚无用户身份与任务归属控制，只能用于本地开发，不得直接公网开放。

## 前端质量命令

```bash
cd frontend
npm ci
npm run typecheck
npm run test -- --run
npm run build
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

## 淘宝生产发布门禁

`docs/spikes/taobao-data-provider.md` 当前状态为 blocked。在取得应用审批、具体接口权限、数据处理条款和书面合规结论前：

- T09 不得实施；
- 不得开放真实淘宝链接解析；
- 不得压测或采集真实淘宝数据；
- 只能使用 Fixture 做内部开发和测试。
