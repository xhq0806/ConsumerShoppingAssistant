# M0 工程基础

> 归档日期：2026-08-05
> 原始 spec：`changes/archive/2026-08-05-m0-engineering-foundation/spec.md`
> 系统基线：`SYSTEM-SPEC.md`
> 验收报告：`docs/m0-verification.md`

## 功能描述

M0 为 Consumer Shopping Assistant 建立可运行、可测试、可替换且受合规边界约束的工程底座。当前系统可以在合成 Fixture Commerce Provider 与 Fake LLM 下启动 FastAPI、Celery Worker、Vue Web、PostgreSQL 和 Redis，并提供统一错误、健康检查、异步数据库、迁移、URL 安全、Provider 契约、LLM Gateway 与基础 CI。M0 不提供实际购物比较业务。

## 核心流程

1. 使用 `docker/docker-compose.yml` 以 `consumer-shopping-assistant` 项目名启动 PostgreSQL、Redis、API、Worker 和 Web。
2. API 加载 Pydantic Settings，注册 trace middleware、ProblemDetails handler 和健康检查路由。
3. `/health/live` 只验证进程；`/health/ready` 检查 PostgreSQL 与 Redis。
4. 数据库变更通过 Alembic 执行；当前 `0001` 是空迁移基线。
5. 商品 URL 先经过协议、host、DNS/IP、端口和商品 ID 校验，再生成 `NormalizedProductUrl`。
6. Fixture Commerce Provider 读取固定合成 JSON，输出统一商品、SKU、评论和错误 DTO。
7. Fake LLM 经 `LLMGateway` 执行 Pydantic 结构化调用、超时、重试和脱敏审计。
8. CI 执行后端 lint/type/test/migration、前端 typecheck/test/build 和 Compose 配置检查。

## 边界约束

- Python 固定为 `>=3.12,<3.13`。
- 默认只使用 `COMMERCE_PROVIDER=fixture` 与 `LLM_PROVIDER=fake`。
- M0 不实现商品比较 API、业务数据表、LangGraph 工作流、报告和管理端。
- PostgreSQL 是未来业务真源；Redis 不作为业务状态真源。
- Provider 不直接接收未经校验的原始 URL。
- Fixture 只能使用合成数据，不得包含真实淘宝评论、Cookie、订单或个人信息。
- LLM 审计不保存完整 Prompt、评论、响应正文或密钥。
- 真实淘宝数据接入为 blocked；不得绕过登录、验证码、反爬、访问控制或平台风控。
- 数据库 Schema 变化必须通过 Alembic。
- Compose 项目名固定为 `consumer-shopping-assistant`。

## 代码索引

### 关键文件

| 文件路径 | 职责 |
|---|---|
| `backend/src/app/main.py` | FastAPI 应用工厂、生命周期、middleware 与路由装配 |
| `backend/src/app/core/config.py` | Pydantic Settings、Provider/LLM/数据库配置解析 |
| `backend/src/app/api/health.py` | live/ready 健康检查 |
| `backend/src/app/api/exception_handlers.py` | ProblemDetails 异常映射 |
| `backend/src/app/api/middleware.py` | 服务端 trace ID 生成与响应头 |
| `backend/src/app/infrastructure/db/` | Async Engine、Session、UnitOfWork、Repository 基线 |
| `backend/alembic/` | 数据库迁移环境与 `0001` 空迁移 |
| `backend/src/app/core/url_security.py` | URL 协议、host、DNS/IP 与 SSRF 安全规则 |
| `backend/src/app/providers/commerce/` | Commerce Protocol、DTO 与 URL 规范化 |
| `backend/src/app/providers/fixture/` | 合成商品和评论 Provider |
| `backend/src/app/providers/llm/` | Fake model 工厂、结构化 Gateway 与审计 |
| `backend/src/app/workers/celery_app.py` | Celery Worker 基线和 smoke task |
| `frontend/src/views/HomeView.vue` | M0 状态首页 |
| `docker/docker-compose.yml` | 五服务本地编排和独立项目名 |
| `.github/workflows/ci.yml` | 后端、数据库、前端和 Compose 基础 CI |

### 外部依赖

| 包/服务 | 用途 | 版本基线 |
|---|---|---|
| FastAPI/Uvicorn | API | FastAPI 0.115+ |
| Pydantic/Pydantic Settings | DTO 与配置 | 2.10+ |
| SQLAlchemy/Alembic | 异步数据库与迁移 | SQLAlchemy 2.x，Alembic 1.14+ |
| PostgreSQL | 数据库 | 16 |
| Redis/Celery | Broker、Worker 和缓存基础 | Redis 7，Celery 5.4+ |
| LangChain Core | Fake model 和消息抽象 | 0.3+ |
| Vue/Vite/Pinia/Router | Web 工程 | Vue 3.5+ |
| Testcontainers | PostgreSQL 集成测试 | 4.9+ |

### 当前 HTTP 接口

| 接口 | 方法 | 说明 |
|---|---|---|
| `/health/live` | GET | API 进程存活，不检查依赖 |
| `/health/ready` | GET | 检查 PostgreSQL 与 Redis；失败返回 503 ProblemDetails |
