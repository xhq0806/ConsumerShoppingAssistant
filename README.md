# Consumer Shopping Assistant

面向普通消费者的智能购物决策助手。用户将在后续里程碑中提交 2～3 个候选商品，系统依据商品事实、品牌资料、近期评论和用户偏好生成可解释、可追溯的比较报告。

## 当前状态：M0 工程基础

当前版本仅提供工程底座：

- FastAPI API 与健康检查；
- Celery Worker；
- PostgreSQL、Redis 与 Docker Compose；
- Vue 3 + TypeScript 前端骨架；
- SQLAlchemy Async、Alembic 和 Testcontainers 基线；
- ProblemDetails 与 trace ID；
- 淘宝 URL 安全校验；
- 合成 Fixture Commerce Provider；
- Fake LLM Gateway 与脱敏审计。

尚未实现真实淘宝 Provider、商品对比业务 API、业务数据表、LangGraph 分析流程和报告页面。

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
docker compose config
docker compose up --build -d
docker compose ps
```

入口：

- Web：<http://localhost:5173>
- API 文档：<http://localhost:8000/docs>
- 存活检查：<http://localhost:8000/health/live>
- 就绪检查：<http://localhost:8000/health/ready>

停止服务：

```bash
docker compose down
```

删除本地数据库与 Redis 卷：

```bash
docker compose down -v
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

更完整的开发说明见 [`docs/development.md`](docs/development.md)，淘宝接入结论见 [`docs/spikes/taobao-data-provider.md`](docs/spikes/taobao-data-provider.md)。
