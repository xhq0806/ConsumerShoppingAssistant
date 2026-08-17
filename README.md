# Consumer Shopping Assistant

面向普通消费者的智能购物决策助手。用户将在后续里程碑中提交 2～3 个候选商品，系统依据商品事实、品牌资料、近期评论和用户偏好生成可解释、可追溯的比较报告。

## 当前状态：M1-D 动态维度推荐与维度确认闭环

当前版本已经完成：

- M0：FastAPI、Celery、PostgreSQL、Redis、Vue 和 Docker Compose 工程底座；
- M1-A：16 张业务表、领域规则、Repository 与 `0001 -> 0004` 数据模型迁移；
- M1-B：创建对比草稿、Fixture 商品解析、任务详情查询、SKU 确认和基础可比性检查；
- M1-C：商品链接输入、解析与确认页面，以及预算、使用场景、关注点和禁忌项的保存与恢复；
- M1-D：受控通用/手机维度种子、确定性推荐、维度增删排序、刷新恢复和 queued 状态推进；
- ProblemDetails、trace ID、URL 安全、创建幂等和事务回滚；
- Fixture Commerce Provider、Fake LLM Gateway 与脱敏审计；
- 前后端完整测试、PostgreSQL 16 迁移生命周期、响应式页面和 Docker Compose 本地质量门禁。

当前提供以下开发基线 API：

```text
POST /api/v1/comparisons
POST /api/v1/comparisons/{comparison_id}/parse
GET  /api/v1/comparisons/{comparison_id}
POST /api/v1/comparisons/{comparison_id}/confirm-products
PUT  /api/v1/comparisons/{comparison_id}/preferences
POST /api/v1/comparisons/{comparison_id}/dimensions/recommendations
GET  /api/v1/comparisons/{comparison_id}/dimensions
POST /api/v1/comparisons/{comparison_id}/dimensions/confirm
```

Web 入口提供 `/`、`/comparisons/:id/confirm`、`/comparisons/:id/preferences` 和
`/comparisons/:id/dimensions` 四步流程。尚未实现评论分析、Celery/LangGraph 业务编排、
报告页面、用户鉴权和真实淘宝 Provider。当前 API 与页面只用于本地开发和 Fixture 验证，
不应直接作为公网生产服务。

## 合规声明

真实淘宝数据接入当前为 **blocked**。项目没有实现、也不允许实现绕过淘宝登录、验证码、反爬、访问控制或平台风控的采集能力。未获得正式授权和合规批准前，只能使用合成 Fixture 数据进行内部开发、自动化测试和演示。

不得将淘宝 Cookie、账号、登录态、API Key、真实评论或其他敏感信息提交到仓库、日志、数据库、Prompt 或 Fixture。

## 环境要求

- Docker Desktop 与 Docker Compose v2；
- Python 3.12；
- Node.js 22 LTS；
- 本地开发可使用 Git Bash、WSL 或兼容终端。

## Docker Compose 启动

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml config
docker compose -f docker/docker-compose.yml up --build -d
docker compose -f docker/docker-compose.yml exec -T api alembic upgrade head
docker compose -f docker/docker-compose.yml ps
```

入口：

- Web：<http://localhost:5173>
- API 文档：<http://localhost:8000/docs>
- 存活检查：<http://localhost:8000/health/live>
- 就绪检查：<http://localhost:8000/health/ready>

停止服务：

```bash
docker compose -f docker/docker-compose.yml down
```

删除本地数据库与 Redis 卷：

```bash
docker compose -f docker/docker-compose.yml down -v
```

该命令会删除本地开发数据，请仅在确认后执行。

## 后端开发

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -m "not integration"
python -m pytest -m integration tests/integration/db
python -m pytest
alembic upgrade head
alembic current
alembic check
```

## 前端开发

```bash
cd frontend
npm install
npm run dev
npm run typecheck
npm run test -- --run
npm run build
```

## 默认开发适配器

```text
COMMERCE_PROVIDER=fixture
LLM_PROVIDER=fake
```

Fixture 数据全部为内部合成样本，不来自真实用户或真实淘宝商品。Fake LLM 仅用于验证结构化输出、超时、重试和审计契约。

这是个人项目，当前以本地可复现质量门禁作为验收依据，不要求提供远端 CI 成功记录。

Windows 下可一次执行完整门禁：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify-local.ps1
```

更完整的开发说明见 [`docs/development.md`](docs/development.md)，M1-D 验收见
[`docs/m1d-verification.md`](docs/m1d-verification.md)，淘宝接入结论见
[`docs/spikes/taobao-data-provider.md`](docs/spikes/taobao-data-provider.md)。
