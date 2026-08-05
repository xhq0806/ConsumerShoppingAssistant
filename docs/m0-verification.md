# M0 验证记录

> 验证日期：2026-07-16
> 结论：M0 实现已完成；静态、单元、契约、前端构建和 Compose 配置验证通过。受本机运行环境限制，Python 3.12、Testcontainers、迁移实跑和全栈容器健康检查仍待补验。

## 已通过

### 后端

- `ruff check .`：通过。
- `ruff format --check .`：通过。
- `mypy src`：通过，34 个源文件无类型错误。
- `pytest -m "not integration"`：24 个测试通过，1 个 Docker 集成测试按 marker 排除。
- 覆盖内容：ProblemDetails、trace ID、未知异常脱敏、淘宝 URL 白名单、SSRF 边界、Fixture Provider、prompt injection 普通文本、LLM 结构化输出、重试和脱敏审计。

本机执行测试时使用 Python 3.11.9；项目配置、CI 和镜像已锁定 Python 3.12。

### 前端

- `npm run typecheck`：通过。
- `npm run test -- --run`：1 个测试通过。
- `npm run build`：通过。
- 构建产生大 chunk 警告，属于 M0 非阻塞项；业务页面扩展时应采用按路由懒加载和手动分包。
- `npm audit` 报告 1 个 moderate severity 问题，尚未使用可能引入破坏性升级的 `npm audit fix --force`；后续依赖维护任务处理。

### Compose

- `docker compose config`：通过，API、Worker、Web、PostgreSQL、Redis 配置可解析。
- 临时 `.env` 已在验证后删除，仓库只保留 `.env.example`。

## 未执行及原因

| 验证项 | 状态 | 原因 | 补验方式 |
|---|---|---|---|
| Python 3.12 容器内后端全检查 | 未执行 | Docker Desktop Linux daemon 未运行 | 启动 Docker Desktop 后重新运行 CI 等效命令 |
| Testcontainers PostgreSQL 测试 | 未执行 | Docker daemon 不可用 | `python -m pytest -m integration tests/integration/db` |
| Alembic 对真实 PostgreSQL upgrade/current/check | 未执行 | Docker daemon 不可用，未启动 PostgreSQL | 启动 Compose 后执行迁移命令 |
| API、Worker、Web 全栈启动 | 未执行 | Docker daemon 不可用 | `docker compose up --build -d` |
| `/health/live`、`/health/ready` | 未执行 | API 与依赖容器未启动 | 启动 Compose 后访问 8000 端口 |

## 待补验命令

```bash
cd /e/BaiduNetdiskDownload/langChain-learn/ConsumerShoppingAssitant
cp .env.example .env
docker compose up --build -d
docker compose ps
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

```bash
cd backend
python -m pytest -m integration tests/integration/db
alembic upgrade head
alembic current
alembic check
```

## 合规门禁

T07 状态为 `blocked`：尚未取得正式淘宝数据接口授权和合规批准。T09 与真实淘宝生产发布不得开始；Fixture 内部开发可继续。
